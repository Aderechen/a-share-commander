"""两年大样本回测 — 验证模型规则的真实准确率
数据: 腾讯日K 2024-07-24 ~ 2026-08-14 (500根/股)
回测1: 止损规则 v1盘中触发 vs v2收盘确认 (750+随机买入样本)
回测2: 进攻条件期望值 (高开3-6%打板 vs 低开低吸 vs 平开)
回测3: 市场环境 (放量上涨日 vs 缩量下跌日后5日收益)
"""
import subprocess, json, random, os, sys

CACHE = os.path.expanduser('~/炒股/commander-model/data/kl_2y.json')

STOCKS = {
    # 用户历史+当前持仓
    'sz301526':'国际复材','sz301217':'铜冠铜箔','sh600584':'长电科技','sz300209':'行云科技',
    'sz001232':'嘉立创','sz300364':'中文在线','sz300540':'蜀道装备','sz300058':'蓝色光标',
    'sz002409':'雅克科技','sz002407':'多氟多',
    # 主线活跃
    'sh600487':'亨通光电','sz300017':'网宿科技','sz000831':'中国稀土','sh600105':'永鼎股份',
    'sz002491':'通鼎互联','sh600288':'大恒科技','sh603005':'晶方科技','sz300346':'南大光电',
    # 权重/各风格
    'sh600519':'贵州茅台','sz300750':'宁德时代','sh600036':'招商银行','sz002594':'比亚迪',
    'sz300059':'东方财富','sh600030':'中信证券','sh601899':'紫金矿业','sh600111':'北方稀土',
    'sz002371':'北方华创','sz300124':'汇川技术','sh600038':'中直股份','sz002475':'立讯精密',
}

def fetch(url, timeout=15):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def load_kline_cache():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    data = {}
    for code, name in STOCKS.items():
        try:
            d = json.loads(fetch(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,500,qfq'))
            node = d['data'][code]
            kl = node.get('qfqday') or node.get('day')
            bars = [[x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in kl]
            data[code] = {'name': name, 'bars': bars}
            print(f'  ✓ {name} {len(bars)}根', flush=True)
        except Exception as e:
            print(f'  ✗ {name} {e}', flush=True)
    with open(CACHE, 'w') as f:
        json.dump(data, f)
    return data

# ---------- 回测1: 止损规则 ----------
def backtest_stop(data, stop_pct=0.08, hold_days=5, sample_step=20):
    """随机买入点→设止损线→比较v1/v2触发与结果"""
    v1 = {'trig': 0, 'correct': 0, 'wrong': 0, 'avg_exec': 0, 'avg_hold': 0, 'avoid': 0, 'miss': 0}
    v2 = {'trig': 0, 'correct': 0, 'wrong': 0, 'avg_exec': 0, 'avg_hold': 0, 'avoid': 0, 'miss': 0}
    samples = 0
    for code, s in data.items():
        bars = s['bars']
        if len(bars) < 150:
            continue
        for i in range(80, len(bars) - hold_days - 3, sample_step):
            buy = bars[i][2]                       # 买入价=当日收盘
            stop = buy * (1 - stop_pct)            # 止损线
            samples += 1
            # 找窗口内触发
            trig_v1 = trig_v2 = None
            for j in range(i + 1, min(i + 1 + 40, len(bars) - hold_days - 1)):
                b = bars[j]
                if trig_v1 is None and b[4] < stop:   # v1: 盘中最低破线
                    trig_v1 = j
                if trig_v2 is None and b[2] < stop:   # v2: 收盘破线
                    trig_v2 = j
                if trig_v1 and trig_v2:
                    break
            for tag, trig in (('v1', trig_v1), ('v2', trig_v2)):
                stat = v1 if tag == 'v1' else v2
                if trig is None:
                    continue
                exec_px = bars[trig][2] if tag == 'v1' else bars[trig + 1][1]  # v1触发日收盘 / v2次日开盘
                hold = bars[min(trig + hold_days, len(bars) - 1)][2]
                stat['trig'] += 1
                stat['avg_exec'] += exec_px
                stat['avg_hold'] += hold
                if exec_px > hold:
                    stat['correct'] += 1
                    stat['avoid'] += (exec_px - hold)
                else:
                    stat['wrong'] += 1
                    stat['miss'] += (hold - exec_px)
    for stat in (v1, v2):
        if stat['trig']:
            stat['avg_exec'] /= stat['trig']
            stat['avg_hold'] /= stat['trig']
    return samples, v1, v2

# ---------- 回测2: 进攻条件期望值 ----------
def backtest_entry(data, hold=2):
    """按开盘涨幅分档, 统计各档买入hold日后的平均收益"""
    buckets = {'高开3-6%(打板)': (3, 6), '高开2-5%': (2, 5), '低开-3~0(低吸)': (-3, 0), '平开0-2%': (0, 2)}
    stats = {k: {'n': 0, 'sum': 0.0, 'win': 0} for k in buckets}
    for code, s in data.items():
        bars = s['bars']
        for i in range(1, len(bars) - hold - 1):
            gap = (bars[i][1] / bars[i - 1][2] - 1) * 100
            for name, (lo, hi) in buckets.items():
                if lo <= gap < hi:
                    fwd = (bars[i + hold][2] / bars[i][1] - 1) * 100
                    stats[name]['n'] += 1
                    stats[name]['sum'] += fwd
                    if fwd > 0:
                        stats[name]['win'] += 1
                    break
    return stats

# ---------- 回测3: 市场环境 ----------
def backtest_market(idx_bars, hold=5):
    """指数放量上涨日 vs 缩量下跌日 → 后5日收益"""
    env = {'放量上涨(进攻窗口)': [], '平量震荡': [], '缩量下跌(防守)': []}
    vols = [b[5] for b in idx_bars]
    avg_vol = sum(vols) / len(vols)
    for i in range(1, len(idx_bars) - hold - 1):
        chg = (idx_bars[i][2] / idx_bars[i - 1][2] - 1) * 100
        vratio = idx_bars[i][5] / avg_vol
        fwd = (idx_bars[i + hold][2] / idx_bars[i][2] - 1) * 100
        if chg > 1 and vratio > 1.2:
            env['放量上涨(进攻窗口)'].append(fwd)
        elif chg < -1 and vratio < 0.8:
            env['缩量下跌(防守)'].append(fwd)
        else:
            env['平量震荡'].append(fwd)
    out = {}
    for k, v in env.items():
        if v:
            out[k] = {'n': len(v), 'avg5d': round(sum(v) / len(v), 2),
                      'win_rate': round(sum(1 for x in v if x > 0) / len(v) * 100, 1)}
    return out

if __name__ == '__main__':
    print('拉取2年K线数据...')
    data = load_kline_cache()
    print(f'\n共{len(data)}只有效数据')
    print('=' * 80)
    print('【回测1: 止损规则 -8% | 触发后5日验证 | 随机买入点】')
    samples, v1, v2 = backtest_stop(data)
    print(f'总买入样本: {samples}')
    for tag, stat in (('v1盘中触发', v1), ('v2收盘确认', v2)):
        if stat['trig'] == 0:
            print(f'{tag}: 无触发'); continue
        correct_rate = stat['correct'] / stat['trig'] * 100
        wrong_rate = stat['wrong'] / stat['trig'] * 100
        print(f'{tag}: 触发{stat["trig"]}次 正确率{correct_rate:.1f}% 误伤率{wrong_rate:.1f}% | '
              f'执行均{stat["avg_exec"]:.2f} vs 5日收{stat["avg_hold"]:.2f} | '
              f'避免损失{stat["avoid"]:.2f}元 卖飞成本{stat["miss"]:.2f}元')
    print('=' * 80)
    print('【回测2: 进攻条件期望值 (买入后2日平均收益)】')
    estats = backtest_entry(data)
    for k, v in estats.items():
        if v['n'] > 100:
            print(f"{k}: n={v['n']} 平均{v['sum']/v['n']:+.2f}% 胜率{v['win']/v['n']*100:.1f}%")
    print('=' * 80)
    print('【回测3: 市场环境→后5日收益 (上证指数2年)】')
    idx = data.get('sh600519', {}).get('bars')
    if idx is None:
        # 用上证指数单独拉
        d = json.loads(fetch('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,500,qfq'))
        idx = d['data']['sh000001'].get('day') or d['data']['sh000001'].get('qfqday')
    mkt = backtest_market(idx)
    for k, v in mkt.items():
        print(f"{k}: n={v['n']} 后5日均{v['avg5d']:+.2f}% 上涨概率{v['win_rate']}%")
