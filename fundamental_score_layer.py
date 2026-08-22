"""fundamental_score_layer.py — 中报财务层 (模型v3 缺失的第9维)
数据源: akshare stock_yjbb_em 底层 (东财业绩报表, 按报告期)
柔性解析: 东财近期在业绩报表新增列导致标准列名错位, 故直接拉原始表并用
         位置/已知列名混合解析, 取 营业总收入 / 归母净利润 / 同比。
降级: 接口失败返回 None, 调用方必须据此降级而非假装有数据。
"""
import subprocess, json, sys

def _ak_yjbb_raw(date="20260630"):
    """调用 akshare 拉业绩报表, 返回 list[dict] (原始行)"""
    code = (
        "import akshare as ak\n"
        "df = ak.stock_yjbb_em(date='" + date + "')\n"
        "print(df.to_json(orient='records', force_ascii=False))\n"
    )
    try:
        r = subprocess.run([sys.executable, '-c', code],
                           capture_output=True, timeout=120,
                           cwd='/Users/nanchen/炒股/daily_stock_analysis')
        out = r.stdout.decode('utf-8', 'ignore')
        # 去掉进度条残留
        if '[' in out and ']' in out:
            out = out[out.rfind('['):]
        return json.loads(out)
    except Exception:
        return None

# 列名候选 (兼容错位)
INC_CAND = ['营业总收入','营业收入','TOTAL_OPERATE_INCOME']
NP_CAND  = ['归母净利润','净利润','PARENT_NETPROFIT']
YSTZ_CAND= ['营业总收入-同比增长','营业总收入同比增长率','YSTZ']
SJLTZ_CAND=['归母净利润-同比增长','净利润-同比增长','净利润同比增长率','SJLTZ']

def get_fundamental(code):
    rows = _ak_yjbb_raw()
    if not rows:
        return None
    for r in rows:
        if str(r.get('股票代码') or r.get('代码')) == code:
            def pick(cands):
                for c in cands:
                    if c in r and r[c] not in (None, ''):
                        return r[c]
                return None
            return {
                'code': code,
                '收入': pick(INC_CAND),
                '净利': pick(NP_CAND),
                '收入同比': pick(YSTZ_CAND),
                '净利同比': pick(SJLTZ_CAND),
            }
    return None

if __name__ == '__main__':
    for c, n in [('301526','国际复材'),('301217','铜冠铜箔'),('600584','长电科技'),('300058','蓝色光标')]:
        f = get_fundamental(c)
        print(n, c, f if f else "（限流/无数据）")
