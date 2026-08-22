"""signal_logger.py — 每日扫描信号落盘 (实盘校准跟踪 Issue #3)
作用: integrated_scan 输出后调用, 把当日信号写入 data/signals.jsonl
      (一行一条JSON, 便于后续 calibration 读取)
字段: date, gate(最终闸门), base_gate, macro_grade, top_sectors,
      valuation_risk, capacity_overload, s7_triggered, notes
后续: calibration.py 按 date 匹配未来N日大盘涨跌, 算命中率
注意: 不含持仓个股买卖指令(避免过度拟合个人持仓), 仅记录市场级信号
"""
import os, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SIGNAL_FILE = os.path.join(HERE, 'data', 'signals.jsonl')

def log_signal(date_str, gate, base_gate, macro_grade, top_sectors,
              valuation_risk, capacity_overload, s7_triggered, notes=''):
    """追加一条信号记录。幂等: 同日已存在则覆盖。"""
    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    rec = {
        'date': date_str,
        'gate': gate,
        'base_gate': base_gate,
        'macro_grade': macro_grade,
        'top_sectors': top_sectors[:3],
        'valuation_risk': valuation_risk,
        'capacity_overload': capacity_overload,
        's7_triggered': s7_triggered,
        'notes': notes,
        'logged_at': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    # 读现有, 去重同日
    existing = []
    if os.path.exists(SIGNAL_FILE):
        with open(SIGNAL_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try: existing.append(json.loads(line))
                    except: pass
    existing = [e for e in existing if e.get('date') != date_str]
    existing.append(rec)
    existing.sort(key=lambda x: x['date'])
    with open(SIGNAL_FILE, 'w') as f:
        for e in existing:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    return rec

def load_signals():
    if not os.path.exists(SIGNAL_FILE):
        return []
    out = []
    with open(SIGNAL_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except: pass
    return out

if __name__ == '__main__':
    # 演示
    r = log_signal('20260821', '半仓', '进攻', '中性偏压',
                  [('通信设备',6),('化学制药',4),('专用设备',4)],
                  8, False, False, '估值否决触发')
    print('写入:', r)
    print('现有记录数:', len(load_signals()))
