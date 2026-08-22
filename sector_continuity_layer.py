"""sector_continuity_layer.py — 主线延续性检验层 (Issue #1)
问题: integrated_scan 用当日涨停池聚合主线, 存在单日噪音误导进攻风险。
解决: 拉取近 N 日涨停池, 统计 top 行业连续出现天数, 区分
      "强主线(连续≥2日)" vs "弱主线/一日游(仅当日)"
用法: continuity_check(dates) -> {行业: {出现天数, 涨停家数均值, 评级}}
复用: market_dimension.get_pools(date) 已支持任意 date_str
"""
import sys, os, datetime
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from market_dimension import get_pools

def _date_seq(n_days, end_date=None):
    """返回近 n_days 的 YYYYMMDD 列表(含周末占位, 非交易日池为空自动跳过)"""
    end = end_date or datetime.datetime.now()
    seq = []
    d = end
    while len(seq) < n_days:
        seq.append(d.strftime('%Y%m%d'))
        d -= datetime.timedelta(days=1)
    return seq[::-1]

def continuity_check(n_days=3, end_date=None):
    """返回 dict: 行业 -> {'days': 出现天数, 'avg_zt': 均值涨停家数, 'grade': 评级}"""
    dates = _date_seq(n_days, end_date)
    appear = defaultdict(list)  # 行业 -> [当日涨停家数, ...]
    for ds in dates:
        try:
            pools = get_pools(ds)
            zt = pools.get('zt') or []
        except Exception:
            continue
        # 当日行业计数
        from collections import Counter
        cnt = Counter((x.get('hybk') or '未知') for x in zt)
        for sec, c in cnt.items():
            appear[sec].append(c)
    res = {}
    for sec, lst in appear.items():
        days = len(lst)
        avg_zt = sum(lst) / days
        if days >= 2:
            grade = '🟢 强主线(连续)'
        elif days == 1:
            grade = '🟡 弱主线(一日游)'
        else:
            grade = '未知'
        res[sec] = {'days': days, 'avg_zt': round(avg_zt, 1), 'grade': grade}
    # 仅返回出现≥1日且按天数降序
    return dict(sorted(res.items(), key=lambda x: (-x[1]['days'], -x[1]['avg_zt'])))

if __name__ == '__main__':
    print("=== 近3日主线延续性 (演示) ===")
    r = continuity_check(3)
    for sec, v in list(r.items())[:12]:
        print(f"  {sec}: 出现{v['days']}日 日均涨停{v['avg_zt']}家 {v['grade']}")
