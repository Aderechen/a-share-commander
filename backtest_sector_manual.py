"""主线板块交叉验证 v2 — 手工对照组(东财限流降级)
主线池: 2026年8月热门主线行业龙头 (通信设备/光纤/稀土小金属/元件PCB/半导体)
非主线池: 防御性蓝筹 (银行/白酒/地产/煤炭/电力/家电)
验证: 高开3-6% × 10日收益 在两组间的差异
"""
import subprocess, json, os, time

CACHE = os.path.expanduser('~/炒股/commander-model/data/kl_sector_manual.json')

MAIN = {
    # 通信设备/光纤
    '600487': '亨通光电', '600105': '永鼎股份', '600522': '中天科技',
    '600498': '烽火通信', '603118': '共进股份', '603083': '剑桥科技',
    '600198': '大唐电信', '002491': '通鼎互联',
    # 稀土/小金属
    '600111': '北方稀土', '000831': '中国稀土', '600392': '盛和资源',
    '002428': '云南锗业', '000657': '中钨高新', '600549': '厦门钨业',
    '002378': '章源钨业', '000962': '东方钽业',
    # 元件/PCB
    '600183': '生益科技', '002463': '沪电股份', '002916': '深南电路',
    '002859': '洁美科技', '301377': '鼎泰高科',
    # 半导体/封测
    '002156': '通富微电', '002371': '北方华创', '002409': '雅克科技',
}
OTHER = {
    # 银行
    '600036': '招商银行', '601398': '工商银行', '601166': '兴业银行',
    # 白酒
    '600519': '贵州茅台', '000858': '五粮液', '000596': '古井贡酒',
    # 地产/基建
    '000002': '万科A', '600048': '保利发展', '601668': '中国建筑',
    # 煤炭
    '601088': '中国神华', '601225': '陕西煤业',
    # 电力
    '600900': '长江电力', '600795': '国电电力',
    # 家电/消费
    '000333': '美的集团', '000651': '格力电器', '600887': '伊利股份',
    # 油运/公用
    '601857': '中国石油', '600028': '中国石化', '601006': '大秦铁路',
}

def fetch(url, timeout=15):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def load_pool():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    data = {}
    for code, name in list(MAIN.items()) + list(OTHER.items()):
        prefix = 'sh' if code.startswith('6') else 'sz'
        try:
            d = json.loads(fetch(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,500,qfq'))
            node = d['data'][f'{prefix}{code}']
            kl = node.get('qfqday') or node.get('day')
            grp = '主线' if code in MAIN else '非主线'
            data[code] = {'name': name, 'grp': grp,
                          'bars': [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in kl]}
            print(f'  ✓ {name} [{grp}] {len(kl)}根', flush=True)
            time.sleep(0.12)
        except Exception as e:
            print(f'  ✗ {name} {e}', flush=True)
    with open(CACHE, 'w') as f:
        json.dump(data, f)
    return data

if __name__ == '__main__':
    data = load_pool()
    print(f'有效: {len(data)}只 (主线{sum(1 for s in data.values() if s["grp"]=="主线")}/非主线{sum(1 for s in data.values() if s["grp"]!="主线")})')
    print('=' * 80)
    print('【高开3-6% × 10日 | 主线行业 vs 非主线防御】')
    for gaps in [(3, 6), (2, 5), (0, 2), (-3, 0)]:
        res = {'主线': {'n': 0, 'sum': 0.0, 'win': 0}, '非主线': {'n': 0, 'sum': 0.0, 'win': 0}}
        hold = 10
        for code, s in data.items():
            bars = s['bars']
            grp = s['grp']
            for i in range(1, len(bars) - hold - 2):
                gap = (bars[i][1] / bars[i-1][2] - 1) * 100
                if not (gaps[0] <= gap < gaps[1]):
                    continue
                fwd = (bars[i+hold][2] / bars[i][1] - 1) * 100
                res[grp]['n'] += 1; res[grp]['sum'] += fwd
                if fwd > 0: res[grp]['win'] += 1
        label = f'高开{gaps[0]}-{gaps[1]}%'
        m, o = res['主线'], res['非主线']
        if m['n'] and o['n']:
            print(f"{label}: 主线 n={m['n']} 平均{m['sum']/m['n']:+.2f}% 胜率{m['win']/m['n']*100:.1f}% || 非主线 n={o['n']} 平均{o['sum']/o['n']:+.2f}% 胜率{o['win']/o['n']*100:.1f}%")