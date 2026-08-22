"""sector_capacity_layer.py — 板块容量检验层 (模型v3 缺失的第10维)
来源: 用户硬性要求 "目标板块日均成交能否吸收流出, >30%接不住"
逻辑:
  1. 取主线行业top3 (来自市场层 top_sectors)
  2. 拉东财行业板块成交额(bkzj) + 全市场成交额
  3. 计算 板块成交 / 全市场成交 占比
  4. 占比 > 30% → 容量过载(钱涌进单板块, 接不住/易见顶)
     占比 < 8%  → 容量充裕(可容纳资金轮动)
作用: 在"进攻"指令前, 验证主线板块能否吸收资金, 防止接飞刀。
降级: 板块API失败 → 标注"容量未知", 不假装有数据。
"""
import subprocess, json

EM_UT = '7eea3edcaed734bea9cbfc24409ed989'

def fetch(url, timeout=12):
    r = subprocess.run(['curl','-s','--max-time',str(timeout),'-A','Mozilla/5.0',url],
                       capture_output=True, timeout=timeout+5)
    return r.stdout.decode('utf-8','ignore')

def get_sector_turnover():
    """东财行业板块资金流: 返回 {板块名: 成交额(亿)}"""
    url = (f"https://push2.eastmoney.com/api/qt/clist/get?ut={EM_UT}"
           "&pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f62"
           "&fs=m:90+t:2&fields=f12,f14,f51,f52,f55,f57,f58,f59,f60,f61,f62,f63,f64")
    try:
        d = json.loads(fetch(url))
        diff = (d.get('data') or {}).get('diff') or []
        out = {}
        for x in diff:
            # f14=板块名, f51=主力净流入, f55=成交额(可能字段)
            name = x.get('f14') or x.get('name')
            # 成交额常见字段 f55/f57/f60; 取非空
            amt = x.get('f55') or x.get('f57') or x.get('f60') or x.get('f51')
            if name and amt:
                try: out[name] = float(amt)/1e8
                except: pass
        return out
    except Exception:
        return {}

def capacity_check(top_sectors, market_turnover_yi):
    """top_sectors: [(行业名, 涨停家数), ...]
    返回 list of {sector, 涨停家数, 成交额亿, 占比, 容量评级}"""
    sec_amt = get_sector_turnover()
    if not sec_amt:
        return None  # 降级
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
    # 演示: 用8/21主线
    top = [('通信设备',6),('化学制药',4),('专用设备',4)]
    res = capacity_check(top, 18793)
    if res is None:
        print("板块容量API失败(限流), 降级")
    else:
        for r in res:
            print(f"{r['sector']}: 涨停{r['zt']}家 成交{r['amt']}亿 占比{r['pct']} {r['grade']}")
