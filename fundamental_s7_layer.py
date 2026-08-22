"""fundamental_s7_layer.py — 中报S7基本面纠偏闭环 (模型v3 缺失的第11维)
来源: soul.md S7 "中报/业绩预告与买入逻辑核心假设偏差>20% → 清仓认错, 不等待"
逻辑:
  1. 输入: 个股中报财务(fundamental_score_layer.get_fundamental) + 买入时假设(用户/记忆提供)
  2. 计算 净利同比 / 营收同比 与假设偏差
  3. 偏差 > 20% → 触发S7清仓信号 (输出给指挥官决策)
  4. 减值/亏损关键词 → 直接高危
注意: 财务API限流时 get_fundamental 返回None → 本层降级(不误判)
买入假设来源: 暂由 positions.md 的"买入逻辑"列提供, 或调用方传入 assumptions dict
"""
from fundamental_score_layer import get_fundamental

# 默认假设(可被 positions.md / 调用方覆盖): 键=code, 值=预期净利同比下限(%)
# 例: 国际复材买入逻辑=玻纤涨价→预期净利转正/高增; 若实际同比<-20%即偏离
DEFAULT_ASSUMPTIONS = {
    '301526': {'expect_np_yoy': 0,    'note': '玻纤涨价→盈利改善预期'},
    '301217': {'expect_np_yoy': 0,    'note': '铜箔供需改善预期'},
    '600584': {'expect_np_yoy': 20,   'note': '封测AI链高增预期'},
    '300058': {'expect_np_yoy': 0,    'note': 'AI营销修复预期'},
}

def s7_check(code, assumptions=None):
    """返回 dict: triggered(bool), reason, detail"""
    asm = (assumptions or {}).get(code, DEFAULT_ASSUMPTIONS.get(code, {}))
    f = get_fundamental(code)
    if f is None:
        return {'code': code, 'triggered': False, 'reason': '财务数据缺失(限流), 降级不误判',
                'detail': None}
    np_yoy = f.get('净利同比')
    inc_yoy = f.get('收入同比')
    # 提取数值(akshare可能返回str带%)
    def to_num(x):
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        import re
        m = re.findall(r'-?\d+\.?\d*', str(x))
        return float(m[0]) if m else None
    np_yoy = to_num(np_yoy)
    inc_yoy = to_num(inc_yoy)
    expect = asm.get('expect_np_yoy', 0)
    # 偏差: (实际 - 预期) / |预期| ; 预期为0时看实际是否负
    flags = []
    if np_yoy is not None:
        if expect == 0:
            if np_yoy < -20:
                flags.append(f"净利同比{np_yoy}% 远低于改善预期(阈值-20%)")
        else:
            dev = (np_yoy - expect) / abs(expect) * 100
            if dev < -20:
                flags.append(f"净利同比{np_yoy}% vs 预期{expect}%, 偏差{dev:.0f}%<-20%")
    if inc_yoy is not None and inc_yoy < -20:
        flags.append(f"营收同比{inc_yoy}% 恶化")
    triggered = len(flags) > 0
    return {
        'code': code, 'triggered': triggered,
        'reason': '; '.join(flags) if flags else '中报与假设偏差在阈值内',
        'detail': {'np_yoy': np_yoy, 'inc_yoy': inc_yoy, 'expect': expect},
    }

def batch_check(codes, assumptions=None):
    return {c: s7_check(c, assumptions) for c in codes}

if __name__ == '__main__':
    for c in ['301526','301217','600584','300058']:
        r = s7_check(c)
        print(f"{c}: S7触发={r['triggered']} | {r['reason']}")
