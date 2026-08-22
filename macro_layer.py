"""macro_layer.py — 国际/宏观风险层 (模型v3 缺失的第7维)
数据源: FRED (美元指数/联邦利率/VIX/油价/美债利差) — 已验证稳定
作用: 把全球宏观变量映射到A股高估值成长股的压力, 在technical评分外
     增加"宏观闸门覆盖" — 强美元/高利率时强制降档, 不等技术面麻痹。
用法: from macro_layer import macro_state, macro_gate_override
"""
import urllib.request

FRED = {
    'FEDFUNDS':  '联邦基金目标利率(%)',
    'DTWEXBGS':  '美元指数(广义)',
    'VIXCLS':    'VIX恐慌指数',
    'WCOILWTICO':'WTI原油(美元/桶)',
    'T10Y2Y':    '美债10Y-2Y利差(%)',
}

def _latest(sid):
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid
        raw = urllib.request.urlopen(url, timeout=25).read().decode().strip().split('\n')
        for line in reversed(raw[1:]):
            if line.strip():
                d, v = line.split(',')
                return d, float(v)
    except Exception:
        return None, None
    return None, None

def macro_state():
    """返回宏观快照 + A股高估值组合的风险评级"""
    vals = {}
    for sid, label in FRED.items():
        d, v = _latest(sid)
        vals[sid] = {'label': label, 'date': d, 'val': v}
    usd   = vals['DTWEXBGS']['val']
    fed   = vals['FEDFUNDS']['val']
    vix   = vals['VIXCLS']['val']
    spread= vals['T10Y2Y']['val']
    # 风险评分: 针对"高PE成长/外资敏感"组合
    risk = 0; notes = []
    if usd is not None:
        if usd >= 118: risk += 3; notes.append(f"美元指数{usd:.1f} 极强→外资流出/人民币承压 +3")
        elif usd >= 112: risk += 1; notes.append(f"美元指数{usd:.1f} 偏强 +1")
        else: notes.append(f"美元指数{usd:.1f} 中性")
    if fed is not None:
        if fed >= 4.0: risk += 2; notes.append(f"联邦利率{fed:.2f}% 偏高→估值压制 +2")
        elif fed >= 3.0: risk += 1; notes.append(f"联邦利率{fed:.2f}% 中性偏高 +1")
    if vix is not None and vix < 16:
        risk += 1; notes.append(f"VIX{vix:.1f} 市场自满(无风险定价) +1")
    if spread is not None and spread < 0:
        risk += 2; notes.append(f"10Y-2Y利差{spread:.2f}% 倒挂→衰退预警 +2")
    grade = '🔴 高压' if risk >= 5 else ('🟡 中性偏压' if risk >= 3 else '🟢 温和')
    return {'vals': vals, 'risk_score': risk, 'grade': grade, 'notes': notes}

def macro_gate_override(technical_gate):
    """宏观覆盖: 高压时强制降到半仓/防守, 不让技术面麻痹"""
    m = macro_state()
    if m['risk_score'] >= 5 and technical_gate == '进攻':
        return '半仓', f"宏观{m['grade']}覆盖: 技术{technical_gate}→半仓"
    if m['risk_score'] >= 7:
        return '防守', f"宏观{m['grade']}覆盖: 技术{technical_gate}→防守"
    return technical_gate, f"宏观{m['grade']}无覆盖"

if __name__ == '__main__':
    m = macro_state()
    print(f"宏观风险: {m['grade']} (分{m['risk_score']})")
    for n in m['notes']: print(' -', n)
    print("vals:", {k: v['val'] for k, v in m['vals'].items()})
