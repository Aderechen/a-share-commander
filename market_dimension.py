"""市场维度模块 — 大盘量能/广度/情绪/板块 → 市场评分与形态判定
数据源: 东财push2ex(涨停/跌停/炸板池) + 东财push2(指数/家数) + 腾讯(成交额)
评分: 0-100, >=40进攻窗口 / 20-40分歧半仓 / <20防守
"""
import json, datetime, time, subprocess
from collections import Counter

EM_UT = '7eea3edcaed734bea9cbfc24409ed989'  # 已验证可用的token

def fetch(url, timeout=12):
    """curl subprocess — 规避东财对python urllib的TLS指纹限制(rc:205/502)"""
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-A', 'Mozilla/5.0', url],
                       capture_output=True, timeout=timeout + 5)
    return r.stdout.decode('utf-8', 'ignore')

def get_pools(date_str):
    """涨停/跌停/炸板池 (重试3次, 防限流)"""
    out = {}
    for key, path in [('zt', 'getTopicZTPool'), ('dt', 'getTopicDTPool'), ('zb', 'getTopicZBPool')]:
        for attempt in range(3):
            try:
                d = json.loads(fetch(f'https://push2ex.eastmoney.com/{path}?ut={EM_UT}&dpt=wz.ztzt&Pageindex=0&pagesize=300&sort=fbt%3Aasc&date={date_str}'))
                pool = (d.get('data') or {}).get('pool') or []
                out[key] = pool
                break
            except Exception:
                time.sleep(1.2)
        else:
            out[key] = []
    return out

def top_sectors(pools_zt):
    """从涨停池聚合主线行业 top3"""
    c = Counter((x.get('hybk') or '未知') for x in pools_zt)
    return c.most_common(3)

def get_index_snapshot():
    """两市: 成交额(亿) + 涨跌家数。东财ulist → 降级腾讯指数成交额"""
    try:
        d = json.loads(fetch('https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001&fields=f6,f104,f105,f106'))
        diff = (d.get('data') or {}).get('diff') or []
        if diff:
            turnover = sum((x.get('f6') or 0) for x in diff) / 1e8
            up = sum((x.get('f104') or 0) for x in diff)
            down = sum((x.get('f105') or 0) for x in diff)
            return {'turnover': round(turnover, 0), 'up': up, 'down': down}
    except Exception:
        pass
    # 降级: 腾讯指数成交额(万) → 亿, 家数缺失
    try:
        r = subprocess.run(['curl', '-s', '--max-time', '10',
                            'https://qt.gtimg.cn/q=sh000001,sz399001'],
                           capture_output=True, timeout=15)
        txt = r.stdout.decode('gbk', 'ignore')
        tv = 0
        for line in txt.strip().split(';'):
            if '~' not in line:
                continue
            parts = line.split('=', 1)[1].strip('"').split('~')
            if len(parts) > 37 and parts[37]:
                tv += float(parts[37])
        return {'turnover': round(tv / 10000, 0), 'up': 0, 'down': 0}
    except Exception:
        return {'turnover': 0, 'up': 0, 'down': 0}

def market_state(date_str=None, override=None):
    """构建市场状态。date_str=YYYYMMDD; override可选覆盖(回测用)"""
    date_str = date_str or datetime.datetime.now().strftime('%Y%m%d')
    pools = get_pools(date_str)
    zt, dt, zb = pools['zt'], pools['dt'], pools['zb']
    height = max((x.get('lbc', 0) for x in zt), default=0)
    seal = len(zt) / (len(zt) + len(zb)) * 100 if (len(zt) + len(zb)) > 0 else 0
    idx = get_index_snapshot()
    if override:
        idx.update(override.get('idx', {}))
        if 'zt' in override: zt = override['zt']
        if 'dt' in override: dt = override['dt']
        if 'zb' in override: zb = override['zb']
        if 'height' in override: height = override['height']
        if 'seal' in override: seal = override['seal']
    return {
        'date': date_str,
        'limit_up': len(zt), 'limit_down': len(dt), 'broken': len(zb),
        'seal_rate': round(seal, 1), 'height': height,
        'turnover_yi': idx.get('turnover', 0), 'up': idx.get('up', 0), 'down': idx.get('down', 0),
        'updown_ratio': (round(idx.get('up', 0) / idx.get('down', 1), 2) if idx.get('down')
                         else (None if not idx.get('up') else 99)),
        'top_sectors': top_sectors(zt),
    }

def market_score(s):
    """0-100评分 + 形态 + 闸门 (阈值按2026年8月量级校准: 两市2.1-2.5万亿)"""
    score = 50.0
    notes = []
    # ① 量能 (两市成交额)
    tv = s['turnover_yi']
    if tv >= 25000: score += 10; notes.append(f'量能{tv/10000:.2f}万亿 放量+10')
    elif tv >= 21000: score += 3; notes.append(f'量能{tv/10000:.2f}万亿 平量+3')
    elif tv >= 18000: score -= 4; notes.append(f'量能{tv/10000:.2f}万亿 缩量-4')
    else: score -= 10; notes.append(f'量能{tv/10000:.2f}万亿 地量-10')
    # ② 广度 (涨跌比; 数据缺失时跳过)
    r = s['updown_ratio']
    if r is None:
        notes.append('涨跌家数数据缺失, 广度维度跳过')
    elif r >= 2: score += 12; notes.append(f'涨跌比{r} 广谱+12')
    elif r >= 1: score += 4; notes.append(f'涨跌比{r} 偏暖+4')
    elif r >= 0.5: score -= 6; notes.append(f'涨跌比{r} 分化-6')
    else: score -= 14; notes.append(f'涨跌比{r} 普跌-14')
    # ③ 情绪 (涨停/封板率)
    if s['limit_up'] >= 60: score += 8; notes.append(f'涨停{s["limit_up"]} 高热+8')
    elif s['limit_up'] >= 30: score += 3; notes.append(f'涨停{s["limit_up"]} 正常+3')
    else: score -= 8; notes.append(f'涨停{s["limit_up"]} 冰点-8')
    if s['seal_rate'] >= 70: score += 6; notes.append(f'封板率{s["seal_rate"]}% 强+6')
    elif s['seal_rate'] < 50: score -= 6; notes.append(f'封板率{s["seal_rate"]}% 弱-6')
    # ④ 亏钱效应 (跌停)
    if s['limit_down'] > 15: score -= 12; notes.append(f'跌停{s["limit_down"]} 恐慌-12')
    elif s['limit_down'] > 5: score -= 6; notes.append(f'跌停{s["limit_down"]} 扩散-6')
    # ⑤ 高度
    if s['height'] >= 6: score += 4; notes.append(f'高度{s["height"]}板 打开+4')
    elif s['height'] < 3: score -= 4; notes.append(f'高度{s["height"]}板 压缩-4')
    # 形态判定
    r = s['updown_ratio']
    if r is not None and r >= 2 and s['limit_up'] >= 50: regime = '🟢 广谱反弹'
    elif r is not None and s['limit_down'] > 15 and r < 0.5: regime = '🔴 普跌退潮'
    elif s['limit_up'] < 30 and s['limit_down'] > 5: regime = '🔴 亏钱效应扩散'
    elif s['height'] >= 6 and s['seal_rate'] >= 70: regime = '🟢 情绪主升'
    elif s['limit_up'] >= 50 and s['limit_down'] > 5: regime = '🟡 高位分歧(涨停多但跌停现)'
    else: regime = '🟡 结构分化'
    gate = '进攻' if score >= 40 else ('半仓' if score >= 20 else '防守')
    # 危险形态强制降档: 普跌/亏钱扩散 → 防守; 高位分歧 → 半仓
    if regime in ('🔴 普跌退潮', '🔴 亏钱效应扩散'):
        gate = '防守'
    elif regime == '🟡 高位分歧(涨停多但跌停现)' and gate == '进攻':
        gate = '半仓'
    return {'score': round(score, 0), 'regime': regime, 'gate': gate, 'notes': notes, **s}

if __name__ == '__main__':
    import sys
    ds = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime('%Y%m%d')
    s = market_state(ds)
    m = market_score(s)
    print(f"市场评分 {m['score']} | {m['regime']} | 闸门: {m['gate']}")
    print(f"涨停{m['limit_up']} 跌停{m['limit_down']} 炸板{m['broken']} 封板率{m['seal_rate']}% 高度{m['height']}板")
    print(f"两市成交{m['turnover_yi']:.0f}亿 涨{m['up']}/跌{m['down']} 涨跌比{m['updown_ratio']}")
    print(f"主线行业: {', '.join(f'{s}({n}家)' for s,n in m['top_sectors'])}")
    for n in m['notes']: print(' -', n)
