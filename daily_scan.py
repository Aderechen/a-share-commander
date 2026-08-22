#!/usr/bin/env python3
"""daily_scan.py — 模型v3一键复盘扫描 (盘后运行)
输出: 市场评分(六维)/闸门/主线行业top3/持仓止损状态/进攻预案建议
用法: python3 daily_scan.py [YYYYMMDD]
"""
import sys, os, json, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from market_dimension import market_state, market_score

POSITIONS = [
    ('国际复材', '301526', 31.61, -15),   # 防灾难线
    ('铜冠铜箔', '301217', 104.59, -15),
    ('长电科技', '600584', 66.90, -15),
    ('蓝色光标', '300058', 12.84, -15),
]

def fetch(url, timeout=15):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def get_quotes():
    codes = [(('sh' if c.startswith('6') else 'sz') + c) for _, c, _, _ in POSITIONS]
    r = fetch('https://qt.gtimg.cn/q=' + ','.join(codes))
    out = {}
    for line in r.strip().split(';'):
        if '~' not in line:
            continue
        p = line.split('=', 1)[1].strip('"').split('~')
        if len(p) > 40:
            out[p[2]] = {'price': float(p[3]), 'prev': float(p[4]),
                         'pct': float(p[32]) if p[32] else 0, 'name': p[1]}
    return out

def main():
    ds = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime('%Y%m%d')
    print(f'# 📡 模型v3 复盘扫描 | {ds}')
    print()
    # 1. 市场评分
    try:
        s = market_state(ds)
        m = market_score(s)
        print(f'## 市场环境: 评分{m["score"]} | {m["regime"]} | 闸门: {m["gate"]}')
        print(f'- 涨停{m["limit_up"]} 跌停{m["limit_down"]} 炸板{m["broken"]} 封板率{m["seal_rate"]}% 高度{m["height"]}板')
        print(f'- 两市成交{m["turnover_yi"]:.0f}亿 涨跌比{m["updown_ratio"]}')
        sec = ', '.join(f'{x}({n}家)' for x, n in m['top_sectors'][:4]) if m['top_sectors'] else '无数据'
        print(f'- 主线行业: {sec}')
        print(f'- 闸门含义: {"可进攻(主线内打板)" if m["gate"]=="进攻" else "半仓(只做持仓/小仓试错)" if m["gate"]=="半仓" else "防守(现金为王)"}')
    except Exception as e:
        print(f'## 市场环境: 数据获取失败 ({e})')
    print()
    # 2. 持仓状态
    print('## 持仓监控 (-15%防灾难线)')
    try:
        q = get_quotes()
        for name, code, stop, pct in POSITIONS:
            if code not in q:
                print(f'- {name}: 无行情')
                continue
            px = q[code]
            flag = '🔴 破防灾难线' if px['price'] < stop else ('🟡 接近' if px['price'] < stop * 1.05 else '🟢 安全')
            print(f'- {name}({code}): {px["price"]:.2f} ({px["pct"]:+.2f}%) 灾难线{stop} {flag}')
    except Exception as e:
        print(f'- 行情获取失败 ({e})')
    print()
    # 3. 进攻预案框架
    print('## 进攻预案 (v3: 主线过滤第一优先)')
    print('- 条件1: 标的必须在主线行业top3-5 (见上)')
    print('- 条件2: 竞价高开3-6%才触发 (2年回测: 主线内+4.05%/53.1%)')
    print('- 条件3: 单笔≤10%, 单日最多一枪, 止损-15%')
    print('- 闸门为半仓/防守时: 预案降级(≤5%或取消)')

if __name__ == '__main__':
    main()
