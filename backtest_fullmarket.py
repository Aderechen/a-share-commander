"""全市场扩展回测 — 300只样本消除风格偏差
流程: 东财clist拉沪深A股(排除科创/北交) → 随机抽300 → 腾讯K线2年 → 混合回测+量能确认
"""
import subprocess, json, random, os, time, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_opt import mixed_backtest, volume_confirm_stop

CACHE300 = os.path.expanduser('~/炒股/commander-model/data/kl_300.json')

def fetch(url, timeout=15):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def get_universe():
    """全市场代码(主板+创业板, 排除688/8开头/ST)"""
    codes = []
    for pn in (1, 2, 3, 4, 5):  # 每页1000条
        d = json.loads(fetch(f'https://push2.eastmoney.com/api/qt/clist/get?pn={pn}&pz=1000&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:6,m:0+t:80,m:1+t:2&fields=f12,f14'))
        diff = (d.get('data') or {}).get('diff') or []
        if not diff:
            break
        for x in diff:
            c = x.get('f12', '')
            n = x.get('f14', '')
            if c.startswith(('688', '8', '4')) or 'ST' in n.upper() or '退' in n:
                continue
            codes.append((c, n))
        time.sleep(0.3)
    return codes

def load_300():
    if os.path.exists(CACHE300):
        with open(CACHE300) as f:
            return json.load(f)
    uni = get_universe()
    print(f'全市场可买池: {len(uni)}只, 随机抽样300')
    random.seed(42)
    sample = random.sample(uni, 300)
    data = {}
    for i, (code, name) in enumerate(sample):
        prefix = 'sh' if code.startswith('6') else 'sz'
        try:
            d = json.loads(fetch(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,500,qfq'))
            node = d['data'][f'{prefix}{code}']
            kl = node.get('qfqday') or node.get('day')
            if len(kl) >= 200:
                data[code] = {'name': name, 'bars': [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in kl]}
            time.sleep(0.12)
        except Exception:
            pass
        if (i + 1) % 50 == 0:
            print(f'  已拉取{i+1}/300, 有效{len(data)}', flush=True)
    with open(CACHE300, 'w') as f:
        json.dump(data, f)
    return data

if __name__ == '__main__':
    print('=== 全市场扩展回测 (300样本) ===')
    data = load_300()
    print(f'有效标的: {len(data)}只 (2年日K)')
    print('=' * 80)
    print('【混合回测: 高开3-6%买入 × 止损线 × 10日】')
    mix = mixed_backtest(data)
    for sp, r in mix.items():
        label = '无止损(纯持有)' if sp is None else f'止损-{int(sp*100)}%'
        print(f'{label}: n={r["n"]} 平均{r["avg"]:+.2f}% 胜率{r["win"]}% 均最大回撤{r["maxdd"]}%')
    print('=' * 80)
    print('【量能确认止损: 破-12%时放量/缩量后续 (10日)】')
    vol = volume_confirm_stop(data)
    for k, v in vol.items():
        print(f'{k}: n={v["n"]} 触发后10日均{v["avg10d"]:+.2f}% 继续跌概率{v["继续跌"]}%')
