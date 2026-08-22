"""模型优化回测 v3 — 混合回测/量能确认止损/止盈对比
复用 backtest_2y 的缓存数据 (30股×2年日K)
"""
import json, os
from backtest_2y import load_kline_cache

data = load_kline_cache()

def mixed_backtest(data, gap_lo=3, gap_hi=6, stop_pcts=(None, 0.08, 0.12, 0.15), hold=10):
    """高开3-6%买入 → 各止损线 → 持有至hold日或止损离场"""
    res = {}
    for sp in stop_pcts:
        res[sp] = {'n': 0, 'sum': 0.0, 'win': 0, 'maxdd': 0.0}
    for code, s in data.items():
        bars = s['bars']
        for i in range(1, len(bars) - hold - 2):
            gap = (bars[i][1] / bars[i-1][2] - 1) * 100
            if not (gap_lo <= gap < gap_hi):
                continue
            buy = bars[i][1]
            for sp in stop_pcts:
                r = res[sp]
                r['n'] += 1
                if sp is None:
                    exit_px = bars[i + hold][2]
                else:
                    stop = buy * (1 - sp)
                    exit_px = None; dd = 0
                    for j in range(i + 1, min(i + hold + 1, len(bars))):
                        dd = min(dd, bars[j][4] / buy - 1)
                        if bars[j][2] < stop:        # 收盘确认
                            exit_px = bars[j + 1][1] if j + 1 < len(bars) else bars[j][2]
                            break
                    if exit_px is None:
                        exit_px = bars[i + hold][2]
                    r['maxdd'] += dd
                pnl = (exit_px / buy - 1) * 100
                r['sum'] += pnl
                if pnl > 0: r['win'] += 1
    out = {}
    for sp, r in res.items():
        if r['n']:
            out[sp] = {'n': r['n'], 'avg': round(r['sum']/r['n'], 2),
                       'win': round(r['win']/r['n']*100, 1),
                       'maxdd': round(r['maxdd']/r['n']*100, 2) if r['maxdd'] else None}
    return out

def volume_confirm_stop(data, stop=0.12, hold=10):
    """止损触发日量能分组: 放量(>1.2x20日均量) vs 缩量(<0.8x) → 正确率"""
    groups = {'放量破位': [], '平量破位': [], '缩量破位': []}
    for code, s in data.items():
        bars = s['bars']
        for i in range(20, len(bars) - hold - 2):
            for j in range(i + 1, min(i + 1 + 40, len(bars) - hold - 1)):
                if bars[j][2] < bars[i][2] * (1 - stop):   # 收盘破-12%
                    avg_vol = sum(bars[jj][5] for jj in range(j - 20, j)) / 20
                    vr = bars[j][5] / avg_vol if avg_vol else 1
                    fwd = (bars[j + hold][2] / bars[j][2] - 1) * 100   # 触发后hold日
                    if vr > 1.2: groups['放量破位'].append(fwd)
                    elif vr < 0.8: groups['缩量破位'].append(fwd)
                    else: groups['平量破位'].append(fwd)
                    break
    out = {}
    for k, v in groups.items():
        if v:
            out[k] = {'n': len(v), 'avg10d': round(sum(v)/len(v), 2),
                      '继续跌': round(sum(1 for x in v if x < 0)/len(v)*100, 1)}
    return out

def take_profit_test(data, gap_lo=3, gap_hi=6, stop=0.12, hold=10, tps=(None, 0.08, 0.12, 0.15)):
    """高开3-6%买入 + 止损-12% + 止盈档位对比"""
    res = {}
    for tp in tps:
        res[tp] = {'n': 0, 'sum': 0.0, 'win': 0}
    for code, s in data.items():
        bars = s['bars']
        for i in range(1, len(bars) - hold - 2):
            gap = (bars[i][1] / bars[i-1][2] - 1) * 100
            if not (gap_lo <= gap < gap_hi): continue
            buy = bars[i][1]
            for tp in tps:
                r = res[tp]; r['n'] += 1
                exit_px = None
                for j in range(i + 1, min(i + hold + 1, len(bars))):
                    if bars[j][2] < buy * (1 - stop):      # 止损优先
                        exit_px = bars[j][2]; break
                    if tp and bars[j][2] > buy * (1 + tp):  # 止盈
                        exit_px = bars[j][2]; break
                if exit_px is None: exit_px = bars[i + hold][2]
                pnl = (exit_px / buy - 1) * 100
                r['sum'] += pnl
                if pnl > 0: r['win'] += 1
    return {tp: {'n': r['n'], 'avg': round(r['sum']/r['n'], 2), 'win': round(r['win']/r['n']*100, 1)} for tp, r in res.items()}

if __name__ == '__main__':
    print('=' * 80)
    print('【优化1: 混合回测 — 高开3-6%买入 × 止损线 × 持有10日】')
    print('=' * 80)
    mix = mixed_backtest(data)
    for sp, r in mix.items():
        label = '无止损(纯持有)' if sp is None else f'止损-{int(sp*100)}%'
        print(f'{label}: n={r["n"]} 平均{r["avg"]:+.2f}% 胜率{r["win"]}% 平均最大回撤{r["maxdd"]}%')

    print()
    print('=' * 80)
    print('【优化2: 量能确认止损 — 破位时放量/缩量的后续差异 (止损-12%, 10日)】')
    print('=' * 80)
    vol = volume_confirm_stop(data)
    for k, v in vol.items():
        print(f'{k}: n={v["n"]} 触发后10日均{v["avg10d"]:+.2f}% 继续跌概率{v["继续跌"]}%')

    print()
    print('=' * 80)
    print('【优化3: 止盈档位对比 — 高开3-6%买入 + 止损-12% + 止盈X%】')
    print('=' * 80)
    tp = take_profit_test(data)
    for k, v in tp.items():
        label = '无止盈' if k is None else f'止盈+{int(k*100)}%'
        print(f'{label}: n={v["n"]} 平均{v["avg"]:+.2f}% 胜率{v["win"]}%')
