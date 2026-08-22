"""fundamental_event_layer.py — 个股事件/基本面风险层 (模型v3 缺失的第8维 v2)
数据源: 东财公告API (np-anotice-stock)
修复: 字段正确路径 data.list[].notice_date / title (v1误取eiitime导致空扫)
作用: 自动扫描持仓公告, 命中风险关键词(治理/减值/诉讼/减持/停牌)即预警。
      例: 铜冠铜箔(301217)董秘逝世 本应自动alert, 而非人工发现。
"""
import subprocess, json

RISK_KW = ['逝世','去世','无法履职','辞职','留置','立案','调查','诉讼','仲裁','减值','停产',
           '停牌','减持','业绩','预亏','亏损','退市','违规','处罚','质押','冻结','问询','终止']

EM_UT = '7eea3edcaed734bea9cbfc24409ed989'

def fetch(url, timeout=15):
    r = subprocess.run(['curl','-s','--max-time',str(timeout),'-A','Mozilla/5.0',url],
                       capture_output=True, timeout=timeout+5)
    return r.stdout.decode('utf-8','ignore')

def scan_one(code):
    url = (f"https://np-anotice-stock.eastmoney.com/api/security/announcement/get?"
           f"page_size=8&page_index=1&stock_list={code}&utm_term={code}&ut={EM_UT}")
    try:
        d = json.loads(fetch(url))
        items = (d.get('data') or {}).get('list') or []
    except Exception:
        return []
    hits = []
    for it in items:
        title = it.get('title') or ''
        notice_date = it.get('notice_date') or ''
        for kw in RISK_KW:
            if kw in title:
                hits.append({'date': notice_date[:10], 'title': title, 'kw': kw})
                break
    return hits

def scan_holdings(positions):
    """positions: list of (name, code, ...)"""
    out = {}
    for p in positions:
        name, code = p[0], p[1]
        hits = scan_one(code)
        if hits:
            out[code] = {'name': name, 'hits': hits}
    return out

if __name__ == '__main__':
    POS = [('国际复材','301526'),('铜冠铜箔','301217'),('长电科技','600584'),('蓝色光标','300058')]
    res = scan_holdings(POS)
    for code, v in res.items():
        print(f"### {v['name']}({code}) 命中{len(v['hits'])}条")
        for h in v['hits'][:5]:
            print(f"  {h['date']} [{h['kw']}] {h['title']}")
    if not res:
        print("（限流或暂无可命中关键词公告）")
