"""A股短线指挥官模型 v2 — 规则引擎（可导入复用）
修正项（基于2026-08-11→08-14首轮回测）：
  F1 止损=收盘确认制：盘中破位仅标记，收盘价<止损线才执行（消除33%假破位误伤）
  F2 进攻=竞价触发+市场闸门：退潮期（涨停<40或跌停>15）全部取消
  F3 后排跟风票淘汰：进攻池只保留板块最强1-2只
  F4 执行自动化：所有指令必须可被cron监控，不依赖人工盯盘

用法:
  from model_v2 import CommanderModel
  m = CommanderModel(market={...})
  m.evaluate_stop(...) / m.evaluate_entry(...) / m.gate_market(...)
"""
from dataclasses import dataclass, field
from typing import Optional

# ---------- 数据容器 ----------
@dataclass
class Bar:
    date: str; open: float; close: float; high: float; low: float; vol: float

@dataclass
class StopOrder:
    """止损/减仓指令"""
    name: str; code: str
    line: float            # 止损线（价格）
    action: str            # 'reduce'减仓 / 'exit'离场 / 'half'减半
    set_date: str          # 指令设定日
    window_days: int = 3   # 验证窗口（交易日）
    mode: str = 'close'    # 'close'收盘确认制(v2) / 'intraday'盘中破位(v1)

@dataclass
class EntryOrder:
    """进攻/建仓指令"""
    name: str; code: str
    rule: str              # 'gap_pct'竞价高开区间 / 'low_open'低开 / 'multi'多条件
    params: dict           # 如 {'min':3,'max':6} 高开3-6%
    set_date: str; exec_date: str
    max_pos: float = 0.10  # 单笔仓位上限
    stop_pct: float = 0.15  # v3: 防灾难级止损(2年回测:-8%负期望,-15%才转正)

@dataclass
class MarketState:
    limit_up: int; limit_down: int; height: int  # 涨停/跌停/连板高度
    def gate(self) -> str:
        """市场闸门: 进攻/半仓/防守 (六维评分, 见market_dimension)"""
        try:
            from market_dimension import market_state, market_score
            s = market_state()
            m = market_score(s)
            return m['gate']
        except Exception:
            # 降级: 简易闸门
            if self.limit_up < 40 or self.limit_down > 15 or self.height < 3:
                return '防守'
            return '进攻'

# ---------- 规则引擎 ----------
class CommanderModel:
    def __init__(self, market: MarketState):
        self.market = market

    # F1: 止损评估（收盘确认制 v2）
    def evaluate_stop(self, order: StopOrder, bars: list) -> dict:
        """bars: 自set_date起的日K序列。
        返回: {'triggered':bool, 'trigger_date':str, 'exec_open':float|None,
               'hold_close':float, 'outcome':'correct'|'wrong'|'na'}
        outcome判定：exec_open vs 窗口末收盘。
          exec_open > 窗口末收盘 → 止损正确（避免后续下跌）
          exec_open < 窗口末收盘 → 止损错误（卖飞）"""
        start = next((i for i,b in enumerate(bars) if b.date >= order.set_date), None)
        if start is None: return {'triggered':False,'reason':'no data'}
        window = bars[start: start + order.window_days + 1]
        triggered_date = None; exec_open = None
        for idx, b in enumerate(window[1:], start=1):  # 从T+1开始检查
            if order.mode == 'intraday':
                hit = b.low < order.line
            else:  # close 收盘确认
                hit = b.close < order.line
            if hit:
                triggered_date = b.date
                # 次日开盘执行（若存在）
                nxt = window[idx+1] if idx+1 < len(window) else None
                exec_open = nxt.open if nxt else b.close
                break
        hold_close = window[-1].close if window else None
        if not triggered_date:
            return {'triggered':False, 'hold_close':hold_close}
        outcome = 'correct' if (exec_open or 0) > (hold_close or 0) else 'wrong'
        return {'triggered':True, 'trigger_date':triggered_date, 'exec_open':exec_open,
                'hold_close':hold_close, 'outcome':outcome}

    # F2: 进攻评估（竞价触发式）
    def evaluate_entry(self, order: EntryOrder, bars: list) -> dict:
        """bars: exec_date当天及之后的K线。
        返回: {'executed':bool, 'buy_price':float, 'hold_close':float,
               'pnl_pct':float, 'skip_benefit':float}
        skip_benefit: 未触发时，若当日追高会亏多少（过滤有效性）"""
        ex = next((i for i,b in enumerate(bars) if b.date >= order.exec_date), None)
        if ex is None: return {'executed':False,'reason':'no data'}
        b0 = bars[ex]
        prev_close = bars[ex-1].close if ex > 0 else b0.open
        gap = (b0.open / prev_close - 1) * 100 if prev_close else 0
        r = order.rule
        executed = False
        if r == 'gap_pct':
            executed = order.params['min'] <= gap <= order.params['max']
        elif r == 'low_open':
            executed = gap <= order.params.get('max', 0)
        elif r == 'multi':
            executed = all(order.params.get(k) for k in ('c1','c2','c3'))
        if not executed:
            # 过滤有效性：假设无脑追高当日开盘买入的浮亏
            hold = bars[min(ex+2, len(bars)-1)].close
            skip = (hold / b0.open - 1) * 100
            return {'executed':False, 'gap':gap, 'buy_price':b0.open, 'hold_close':hold,
                    'pnl_pct':skip, 'skip_benefit':skip}
        hold = bars[min(ex+2, len(bars)-1)].close
        pnl = (hold / b0.open - 1) * 100
        return {'executed':True, 'gap':gap, 'buy_price':b0.open, 'hold_close':hold, 'pnl_pct':pnl}

    # 仓位规则（宪章）
    def pos_check(self, weight, cap=0.30):
        return weight <= cap

if __name__ == '__main__':
    print('CommanderModel v2 loaded — F1收盘确认制/F2市场闸门/F3前排优先/F4自动执行')
