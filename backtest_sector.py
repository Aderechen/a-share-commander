"""主线板块交叉验证 — 高开3-6% × 主线行业成分股 vs 全市场
1. 东财clist拉全市场(主板+创业板, 带f100行业) 小分页循环
2. 主线行业=8/14涨停池聚合top（通信设备/汽车零部/元件）+ 已知加仓主线（光纤/稀土/半导体）
3. 拉成分股K线(腾讯2年) → 组内测高开3-6%×10日收益 vs 非主线组
"""
import subprocess, json, random, os, time
from collections import Counter

CACHE = os.path.expanduser('~/炒股/commander-model/data/kl_sector.json')

def fetch(url, timeout=15):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def get_all_with_sector():
    """全市场代码+行业 (小分页循环)"""
    rows = []
    for pn in range(1, 30):
        try:
            d = json.loads(fetch(f'https://push2.eastmoney.com/api/qt/clist/get?pn={pn}&pz=200&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:6,m:0+t:80,m:1+t:2&fields=f12,f14,f100'))
            diff = (d.get('data') or {}).get('diff') or []
            if not diff:
                break
            rows.extend(diff)
            time.sleep(0.25)
        except Exception:
            time.sleep(1)
            continue
    # 去重+过滤
    seen, out = set(), []
    for x in rows:
        c = x.get('f12', '')
        if c in seen or c.startswith(('688', '8', '4')):
            continue
        seen.add(c)
        out.append({'code': c, 'name': x.get('f14', ''), 'sector': x.get('f100', '?')})
    return out

MAIN_SECTORS = ['通信设备', '汽车零部', '元件', '小金属', '半导体', '通信服务', '光学光电']
# 8/14涨停池: 通信设备6家/汽车零部3家/元件3家 + 近期主线(光纤=通信设备/稀土=小金属/半导体)

def main():
    print('拉全市场行业分布...', flush=True)
    uni = get_all_with_sector()
    print(f'全市场: {len(uni)}只, 行业数: {len(Counter(x["sector"] for x in uni))}')
    c = Counter(x['sector'] for x in uni)
    print('行业top15:', c.most_common(15))

    main_codes = [x for x in uni if x['sector'] in MAIN_SECTORS]
    other = [x for x in uni if x['sector'] not in MAIN_SECTORS]
    print(f'主线行业成分: {len(main_codes)}只 | 非主线: {len(other)}只')

    # 采样: 主线全部(若>250则随机250), 非主线随机250
    random.seed(7)
    main_s = main_codes if len(main_codes) <= 250 else random.sample(main_codes, 250)
    other_s = random.sample(other, min(250, len(other)))
    pool = [(x['code'], x['name'], '主线' if x in set(tuple(m.items()) for m in main_s) else '非主线')
            for x in (main_s + other_s)]
    # 用code判断(对象引用问题直接重建)
    main_set = {x['code'] for x in main_s}
    pool = [(x['code'], x['name'], '主线' if x['code'] in main_set else '非主线') for x in (main_s + other_s)]
    print(f'回测池: 主线{sum(1 for p in pool if p[2]=="主线")} + 非主线{sum(1 for p in pool if p[2]!="主线")}')

    # 拉K线
    data = {}
    for i, (code, name, grp) in enumerate(pool):
        if code in data:
            continue
        prefix = 'sh' if code.startswith('6') else 'sz'
        try:
            d = json.loads(fetch(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,500,qfq'))
            node = d['data'][f'{prefix}{code}']
            kl = node.get('qfqday') or node.get('day')
            if len(kl) >= 200:
                data[code] = {'name': name, 'grp': grp, 'bars': [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in kl]}
            time.sleep(0.1)
        except Exception:
            pass
        if (i + 1) % 100 == 0:
            print(f'  拉取{i+1}, 有效{len(data)}', flush=True)
    with open(CACHE, 'w') as f:
        json.dump(data, f)
    print(f'有效: {len(data)}只')

    # 分主线/非主线测高开3-6%
    hold = 10
    res = {'主线': {'n': 0, 'sum': 0.0, 'win': 0}, '非主线': {'n': 0, 'sum': 0.0, 'win': 0},
           '全市场': {'n': 0, 'sum': 0.0, 'win': 0}}
    for code, s in data.items():
        bars = s['bars']
        grp = s['grp'] if s['grp'] == '主线' else '非主线'
        for i in range(1, len(bars) - hold - 2):
            gap = (bars[i][1] / bars[i-1][2] - 1) * 100
            if not (3 <= gap < 6):
                continue
            fwd = (bars[i+hold][2] / bars[i][1] - 1) * 100
            for g in (grp, '全市场'):
                res[g]['n'] += 1; res[g]['sum'] += fwd
                if fwd > 0: res[g]['win'] += 1
    print('=' * 80)
    print('【高开3-6% × 10日 | 主线行业 vs 非主线 vs 全市场】')
    for g, r in res.items():
        if r['n']:
            print(f"{g}: n={r['n']} 平均{r['sum']/r['n']:+.2f}% 胜率{r['win']/r['n']*100:.1f}%")

if __name__ == '__main__':
    main()