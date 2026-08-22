"""calibration.py — 实盘校准跟踪 (Issue #3)
对比: 每日 integrated_scan 信号(落盘 data/signals.jsonl) vs 后续实际大盘涨跌
指标:
  1. 闸门命中率: gate=进攻/半仓 时, 未来N日大盘上涨比例 (验证"进攻信号是否真该进攻")
  2. 估值否决有效性: 估值否决触发日 vs 未触发日, 未来5日大盘平均收益差
  3. 主线延续: 信号日top行业 vs 未来该行业表现(简化: 用大盘代理)
数据源: 腾讯上证指数日K(稳定); 信号来自 signal_logger
用法: python3 calibration.py [lookforward=5]
"""
import sys, os, subprocess, json, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from signal_logger import load_signals

IDX_CACHE = os.path.join(HERE, 'data', 'idx_daily.json')

def load_index():
    """上证指数日K, 返回 {YYYYMMDD: close}"""
    if os.path.exists(IDX_CACHE):
        with open(IDX_CACHE) as f:
            return json.load(f)
    try:
        r = subprocess.run(['curl','-s','--max-time','20',
            'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,500,qfq'],
            capture_output=True, timeout=25)
        d = json.loads(r.stdout.decode())
        node = d['data']['sh000001']
        kl = node.get('qfqday') or node.get('day')
        out = {}
        for x in kl:
            dt = x[0].replace('-','')[:8]
            out[dt] = float(x[2])  # 收盘
        with open(IDX_CACHE,'w') as f:
            json.dump(out, f)
        return out
    except Exception as e:
        print("指数拉取失败:", e)
        return {}

def main(lookfwd=5):
    signals = load_signals()
    if not signals:
        print("无信号记录, 请先运行 integrated_scan 落盘信号")
        return
    idx = load_index()
    if not idx:
        print("指数数据缺失, 校准中止")
        return
    dates = sorted(idx.keys())
    date2close = idx

    def fwd_ret(date_str):
        """信号日后 lookfwd 日大盘收益%, None=数据不足"""
        if date_str not in date2close:
            return None
        i = dates.index(date_str)
        if i + lookfwd >= len(dates):
            return None
        return (date2close[dates[i+lookfwd]] / date2close[date_str] - 1) * 100

    print(f"=== 实盘校准 (信号→未来{lookfwd}日大盘) ===")
    print(f"信号样本: {len(signals)}条, 指数覆盖: {dates[0]}~{dates[-1]}\n")

    # 1. 闸门命中率
    print("【1. 闸门信号 → 未来大盘上涨比例】")
    for gate in ('进攻','半仓','防守'):
        subset = [s for s in signals if s['gate'] == gate]
        rets = [fwd_ret(s['date']) for s in subset]
        rets = [r for r in rets if r is not None]
        if rets:
            up = sum(1 for r in rets if r > 0)
            print(f"  {gate}: n={len(rets)} 未来{lookfwd}日上涨{up/len(rets)*100:.0f}% "
                  f"平均{sum(rets)/len(rets):+.2f}%")
        else:
            print(f"  {gate}: 无足够后续数据")

    # 2. 估值否决有效性
    print("\n【2. 估值否决触发 vs 未触发 (未来大盘平均收益)】")
    for flag in (True, False):
        subset = [s for s in signals if ('估值否决=是' in s.get('notes','')) == flag]
        rets = [fwd_ret(s['date']) for s in subset]
        rets = [r for r in rets if r is not None]
        if rets:
            print(f"  估值否决{'触发' if flag else '未触发'}: n={len(rets)} 平均{sum(rets)/len(rets):+.2f}%")
        else:
            print(f"  估值否决{'触发' if flag else '未触发'}: 无样本")

    # 3. 样本期总览
    print("\n【3. 信号明细】")
    for s in signals[-10:]:
        r = fwd_ret(s['date'])
        print(f"  {s['date']} gate={s['gate']} macro={s['macro_grade']} "
              f"估值风险={s.get('valuation_risk')} 未来{lookfwd}日={r if r is None else f'{r:+.2f}%'}")

if __name__ == '__main__':
    lf = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    main(lf)
