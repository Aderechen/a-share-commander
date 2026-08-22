"""positions_io.py — 从 a-share-state/positions.md 动态读取持仓
替代 daily_scan.py 中写死的 POSITIONS 列表, 调仓后自动同步, 不再失真。
解析约定: markdown 表格行 | 国际复材 | 301526 | 创业板 | 现价 | 成本 | 浮盈亏 | 权重 | 灾难线 | 状态 |
"""
import re, os

POS_MD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'a-share-state', 'positions.md')

def load_positions():
    """返回 list of dict: name, code, board, price, cost, pnl, weight, stop"""
    if not os.path.exists(POS_MD):
        return []
    txt = open(POS_MD, encoding='utf-8').read()
    out = []
    for line in txt.split('\n'):
        if not line.strip().startswith('|'):
            continue
        cols = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cols) < 8:
            continue
        # 跳过表头/分隔行
        if cols[0] in ('标的', '') or set(cols[1]) <= set('-: '):
            continue
        m = re.match(r'(\d{6})', cols[1])
        if not m:
            continue
        code = m.group(1)
        def num(x):
            try: return float(re.sub(r'[^\d.\-]','', x))
            except: return None
        out.append({
            'name': cols[0], 'code': code, 'board': cols[2],
            'price': num(cols[3]), 'cost': num(cols[4]),
            'pnl': cols[5], 'weight': num(cols[6]),
            'stop': num(cols[7]),
        })
    return out

if __name__ == '__main__':
    for p in load_positions():
        print(p)
