"""fundamental_score_layer.py — 中报财务层 (零成本稳定源: akshare stock_financial_abstract)
替代原 stock_yjbb_em(全市场拉取, 东财限流卡死)。
stock_financial_abstract 为单股财务摘要, 本地akshare调用, 稳定不限流, 含中报营收/净利/同比。
降级: 单股拉取失败 → 返回 None, 调用方必须据此降级而非假装有数据。
"""
import subprocess, json, sys

_CACHE = {}  # code -> dict

def get_fundamental(code):
    """返回 {code, 收入, 净利, 收入同比%, 净利同比%} 或 None"""
    if code in _CACHE:
        return _CACHE[code]
    code_src = (
        "import akshare as ak, json\n"
        "df = ak.stock_financial_abstract(symbol='" + code + "')\n"
        "print(df.to_json(orient='records', force_ascii=False))\n"
    )
    try:
        r = subprocess.run([sys.executable, '-c', code_src],
                           capture_output=True, timeout=40,
                           cwd='/Users/nanchen/炒股/daily_stock_analysis')
        out = r.stdout.decode('utf-8', 'ignore')
        if '[' in out and ']' in out:
            out = out[out.rfind('['):]
        rows = json.loads(out)
        rec = {}
        for row in rows:
            ind = str(row.get('指标') or row.get('选项') or '')
            # 精确匹配, 排除"每股*"干扰
            if ind == '营业总收入':
                rec['收入'] = _to_float(row.get('20260630'))
            elif ind == '营业总收入增长率':
                rec['收入同比'] = _to_float(row.get('20260630'))
            elif ind == '归母净利润':
                rec['净利'] = _to_float(row.get('20260630'))
            elif ind == '归属母公司净利润增长率':
                rec['净利同比'] = _to_float(row.get('20260630'))
        if not rec:
            _CACHE[code] = None
            return None
        rec['code'] = code
        _CACHE[code] = rec
        return rec
    except Exception:
        _CACHE[code] = None
        return None

def _to_float(v):
    try: return float(v)
    except: return None

if __name__ == '__main__':
    for c, n in [('301526','国际复材'),('301217','铜冠铜箔'),('600584','长电科技'),('300058','蓝色光标')]:
        f = get_fundamental(c)
        print(n, c, f if f else "（无数据）")
