"""sector_capacity_layer.py — 板块容量检验层 (零成本稳定源: 涨停池 amount 字段聚合)
替代原东财 push2 行业板块API(限流)。
逻辑:
  1. 拉当日涨停池(market_dimension.get_pools) → 每只涨停股含 hybk(行业) + amount(成交额元)
  2. 按行业聚合涨停股成交额
  3. 主线行业(来自市场层top_sectors)的 涨停股成交和 / 全市场成交 = 近似占比
  4. 占比 > 30% → 容量过载(钱涌进单板块, 接不住/易见顶)
降级: 涨停池失败 → 返回 None, 标注未知。
注: 仅统计涨停股成交(非全板块), 但主线判断足够 — 涨停股成交已占30%必是过度抱团。
"""
import sys, os, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from market_dimension import get_pools

def capacity_check(top_sectors, market_turnover_yi, date_str=None):
    """top_sectors: [(行业名, 涨停家数), ...]
    返回 list of {sector, 涨停家数, 成交额亿, 占比, 容量评级} 或 None(降级)"""
    try:
        pools = get_pools(date_str or datetime.datetime.now().strftime('%Y%m%d'))
    except Exception:
        return None
    zt = (pools or {}).get('zt') or []
    if not zt:
        return None
    # 按行业聚合涨停股成交额 (涨停池已含 amount 字段, 元)
    sec_amt = {}
    sec_cnt = {}
    for x in zt:
        sec = x.get('hybk') or '未知'
        amt = x.get('amount') or 0
        sec_amt[sec] = sec_amt.get(sec, 0) + amt / 1e8
        sec_cnt[sec] = sec_cnt.get(sec, 0) + 1
    if not sec_amt:
        return None
    res = []
    for name, zt_cnt in top_sectors[:3]:
        amt = sec_amt.get(name)
        if amt is None:
            res.append({'sector': name, 'zt': zt_cnt, 'amt': None, 'pct': None, 'grade': '未知(板块名不匹配)'})
            continue
        pct = amt / market_turnover_yi if market_turnover_yi else None
        if pct is None:
            grade = '未知'
        elif pct > 0.30:
            grade = '🔴 过载(>30%接不住)'
        elif pct < 0.08:
            grade = '🟢 充裕(<8%)'
        else:
            grade = '🟡 适中'
        res.append({'sector': name, 'zt': zt_cnt, 'amt': round(amt,0), 'pct': round(pct,3) if pct else None, 'grade': grade})
    return res

if __name__ == '__main__':
    top = [('通信设备',6),('化学制药',4),('专用设备',4)]
    res = capacity_check(top, 18793)
    if res is None:
        print("板块容量降级(涨停池失败)")
    else:
        for r in res:
            print(f"{r['sector']}: 涨停{r['zt']}家 成交{r['amt']}亿 占比{r['pct']} {r['grade']}")
