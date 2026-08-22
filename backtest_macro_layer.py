"""backtest_macro_layer.py — 宏观分层回测 (Issue #2)
问题: 所有 backtest 只在技术信号上跑, 未把宏观环境作为分层变量。
      当前美元118.9极强, 正是该验证时段 —— 策略夏普可能在紧缩期被高估。
方法:
  1. 下载 FRED 美元指数(DTWEXBGS) 近2年日频序列, 存本地缓存
  2. 对 backtest_entry 的每个买入样本, 按其买入日匹配当时美元水平
  3. 分 regime: 紧缩(美元>=112) / 宽松(美元<112)
  4. 分环境输出: 高开3-6%打板档的胜率/平均收益/样本数
依赖: backtest_2y.load_kline_cache (复用2年K线)
"""
import sys, os, subprocess, json, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from backtest_2y import load_kline_cache

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS"
CACHE = os.path.expanduser('~/炒股/commander-model/data/usd_hist.json')

def load_usd_hist():
    """返回 {YYYY-MM-DD: 美元指数} 近2年"""
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    try:
        r = subprocess.run(['curl','-s','--max-time','30', FRED_CSV],
                          capture_output=True, timeout=35)
        raw = r.stdout.decode().strip().split('\n')[1:]
        out = {}
        for line in raw:
            if ',' in line:
                d, v = line.split(',')
                try: out[d] = float(v)
                except: pass
        with open(CACHE, 'w') as f:
            json.dump(out, f)
        return out
    except Exception as e:
        print("美元历史拉取失败:", e)
        return {}

def regime_on(date_str, usd):
    """date_str: YYYYMMDD -> 查前一日美元(避免当日未更新)"""
    dt = datetime.datetime.strptime(date_str, '%Y%m%d')
    for back in range(0, 5):
        d = (dt - datetime.timedelta(days=back)).strftime('%Y-%m-%d')
        if d in usd:
            return '紧缩(美元>=112)' if usd[d] >= 112 else '宽松(美元<112)'
    return '未知'

def backtest_entry_macro(data, usd, hold=2):
    """按 gap 分档 + 宏观 regime 分层"""
    buckets = {'高开3-6%(打板)': (3, 6), '高开2-5%': (2, 5),
               '低开-3~0(低吸)': (-3, 0), '平开0-2%': (0, 2)}
    # stats[bucket][regime] = {n, sum, win}
    stats = {b: {'紧缩(美元>=112)': {'n':0,'sum':0.0,'win':0},
                 '宽松(美元<112)': {'n':0,'sum':0.0,'win':0},
                 '未知': {'n':0,'sum':0.0,'win':0}} for b in buckets}
    for code, s in data.items():
        bars = s['bars']
        for i in range(1, len(bars) - hold - 1):
            date_str = bars[i][0].replace('-', '')[:8]
            gap = (bars[i][1] / bars[i-1][2] - 1) * 100
            for name, (lo, hi) in buckets.items():
                if lo <= gap < hi:
                    fwd = (bars[i+hold][2] / bars[i][1] - 1) * 100
                    rg = regime_on(date_str, usd)
                    cell = stats[name][rg]
                    cell['n'] += 1; cell['sum'] += fwd
                    if fwd > 0: cell['win'] += 1
                    break
    return stats

if __name__ == '__main__':
    print('加载K线...')
    data = load_kline_cache()
    print(f'{len(data)}只')
    print('下载美元历史...')
    usd = load_usd_hist()
    print(f'美元历史 {len(usd)} 个交易日')
    print('=' * 70)
    print('【宏观分层回测: 高开档位 × 美元regime → 后2日】')
    stats = backtest_entry_macro(data, usd)
    for b, regimes in stats.items():
        print(f'\n{b}:')
        for rg, c in regimes.items():
            if c['n'] > 50:
                print(f"  {rg}: n={c['n']} 平均{c['sum']/c['n']:+.2f}% 胜率{c['win']/c['n']*100:.1f}%")
            else:
                print(f"  {rg}: n={c['n']} (样本不足)")
