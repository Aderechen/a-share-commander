"""daily_scan_cron.py — 每日盘后八维扫描 + 信号落盘 (cron no_agent 模式)
设计: 复用 integrated_scan.main() 落盘信号到 data/signals.jsonl,
      stdout 仅打印一行摘要(供飞书推送, 不刷屏)。
用法: cron no_agent 模式调用, 工作日 15:35 盘后跑。
"""
import os, sys, io, datetime

CM = os.path.expanduser('~/炒股/commander-model')
if CM not in sys.path:
    sys.path.insert(0, CM)

# 重定向 integrated_scan 的 stdout 到缓冲区, 我们只抓最终闸门结论
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    import integrated_scan
    integrated_scan.main()  # 内部用 datetime.now() 取当日
finally:
    sys.stdout = _old

# 从缓冲抓最终闸门行
out = _buf.getvalue()
gate_line = ''
for line in out.splitlines():
    if '最终闸门' in line:
        gate_line = line.strip()
        break
# 也抓信号落盘确认
logged = '信号已落盘' in out

ds = datetime.datetime.now().strftime('%Y%m%d')
print(f"📡 {ds} 盘后扫描 | {gate_line} | {'✅已积累' if logged else '⚠️未落盘'}")
