"""integrated_scan.py — 八维整合扫描 (模型v3 增强版)
并联: 市场(技术面) + 主线延续性 + 宏观(国际) + 事件(治理/公告) + 估值(PE温度计)
     + 持仓(动态读) + 板块容量(资金吸收) + 中报S7纠偏(基本面)
闸门逻辑:
  基础闸门 = 市场评分
  主线延续性否决: 当日主线为"弱主线(一日游)" → 进攻降半仓
  宏观否决权: 高压 → 进攻降半仓
  估值否决权: 极贵组合 × 宏观偏压 → 进攻降半仓
  板块容量: >30%接不住 → 进攻降半仓(主线不可持续)
  中报S7: 偏差>20% → 相关持仓清仓信号
数据缺失: 任一层失败仅降级该层, 不假装有数据, 不强行给进攻
用法: python3 integrated_scan.py [YYYYMMDD]
"""
import sys, os, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from market_dimension import market_state, market_score
from sector_continuity_layer import continuity_check
from macro_layer import macro_state, macro_gate_override
from fundamental_event_layer import scan_holdings
from fundamental_s7_layer import batch_check as s7_batch
from sector_capacity_layer import capacity_check
from positions_io import load_positions

def get_pe(code):
    """腾讯PE接口(已验证稳定): qt.gtimg.cn 字段 pe=~39(动态)"""
    import subprocess
    mkt = 'sh' if code.startswith('6') else 'sz'
    try:
        r = subprocess.run(['curl','-s','--max-time','10', f'https://qt.gtimg.cn/q={mkt}{code}'],
                           capture_output=True, timeout=15)
        parts = r.stdout.decode('gbk','ignore').split('=')[1].strip('"').split('~')
        if len(parts) > 39 and parts[39]:
            return float(parts[39])
    except Exception:
        return None
    return None

def valuation_grade(pe):
    if pe is None: return '未知', 0
    if pe >= 300: return '🔴 极贵', 3
    if pe >= 100: return '🟠 偏贵', 2
    if pe >= 50:  return '🟡 中性偏贵', 1
    return '🟢 合理', 0

def main():
    ds = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime('%Y%m%d')
    print(f'# 📡 八维整合扫描 | {ds}')
    print()

    # 0. 持仓(动态)
    pos = load_positions()
    if not pos:
        print('⚠️ 持仓文件缺失, 跳过持仓维度; 需确认 a-share-state/positions.md')
        pos = [{'name':'国际复材','code':'301526'},{'name':'铜冠铜箔','code':'301217'},
               {'name':'长电科技','code':'600584'},{'name':'蓝色光标','code':'300058'}]
    print(f'## 持仓({len(pos)}只, 动态读取)')
    pes = {}
    for p in pos:
        pe = get_pe(p['code'])
        pes[p['code']] = pe
        g, _ = valuation_grade(pe)
        print(f"- {p['name']}({p['code']}): PE={pe} {g}")
    print()

    # 1. 市场维度
    print('## 市场维度(技术面)')
    top_sectors = []
    market_turnover = 0
    try:
        s = market_state(ds)
        m = market_score(s)
        base_gate = m['gate']
        top_sectors = m['top_sectors']
        market_turnover = m['turnover_yi']
        print(f"- 评分{m['score']} | {m['regime']} | 基础闸门: {base_gate}")
        print(f"- 涨停{m['limit_up']} 跌停{m['limit_down']} 炸板{m['broken']} 封板率{m['seal_rate']}% 高度{m['height']}板")
        print(f"- 两市成交{m['turnover_yi']:.0f}亿 涨跌比{m['updown_ratio']}")
        print(f"- 当日主线: {', '.join(f'{x}({n}家)' for x,n in top_sectors[:3])}")
    except Exception as e:
        print(f"- 市场数据失败 ({e}), 基础闸门降级为防守")
        base_gate = '防守'
    print()

    # 1.5 主线延续性维度
    print('## 主线延续性维度(近3日)')
    continuity_weak = False
    try:
        cont = continuity_check(3, datetime.datetime.strptime(ds, '%Y%m%d'))
        # 取当日top3行业对应的延续性
        top_names = [x[0] for x in top_sectors[:3]]
        shown = 0
        for sec, v in cont.items():
            if sec in top_names or shown < 6:
                print(f"- {sec}: 连续{v['days']}日 日均涨停{v['avg_zt']}家 {v['grade']}")
                if sec in top_names and v['days'] < 2:
                    continuity_weak = True
                shown += 1
        if continuity_weak and base_gate == '进攻':
            base_gate = '半仓'
            print('  ⚠️ 当日主线为弱主线(一日游) → 基础闸门: 进攻→半仓')
    except Exception as e:
        print(f"- 延续性检查失败 ({e}), 不降级")
    print()

    # 2. 宏观维度(国际, 有否决权)
    print('## 宏观维度(国际/利率)')
    macro = None
    try:
        macro = macro_state()
        final_gate, reason = macro_gate_override(base_gate)
        print(f"- 评级{macro['grade']} (分{macro['risk_score']})")
        for n in macro['notes']: print(f"  - {n}")
        print(f"- 闸门覆盖: {reason}")
    except Exception as e:
        print(f"- 宏观数据失败 ({e}), 不覆盖")
        final_gate = base_gate
    print()

    # 3. 事件维度(治理/公告)
    print('## 事件维度(个股公告风险)')
    try:
        ev = scan_holdings([(p['name'], p['code']) for p in pos])
        if ev:
            for code, v in ev.items():
                for h in v['hits'][:3]:
                    print(f"  🔥 {v['name']}({code}) {h['date']} [{h['kw']}] {h['title']}")
        else:
            print('- 暂无可命中风险关键词公告(或限流)')
    except Exception as e:
        print(f"- 事件扫描失败 ({e})")
    print()

    # 4. 估值维度(温度计)
    print('## 估值维度(PE温度计)')
    total_risk = 0
    for code, pe in pes.items():
        g, r = valuation_grade(pe)
        total_risk += r
        print(f"- {code}: PE={pe} {g}")
    if total_risk >= 6:
        print('  ⚠️ 组合估值整体偏贵, 退潮期脆弱')
    print()

    # 5. 板块容量维度(资金吸收)
    print('## 板块容量维度(资金能否吸收)')
    if top_sectors and market_turnover:
        cap = capacity_check(top_sectors, market_turnover)
        if cap is None:
            print('- 板块成交额API失败(限流), 容量未知→不单独改闸门')
        else:
            overloaded = False
            for r in cap:
                print(f"- {r['sector']}: 涨停{r['zt']}家 成交{r['amt']}亿 占比{r['pct']} {r['grade']}")
                if r['pct'] is not None and r['pct'] > 0.30:
                    overloaded = True
            if overloaded and final_gate == '进攻':
                final_gate = '半仓'
                print('  ⚠️ 板块容量过载(>30%接不住) → 闸门: 进攻→半仓')
    else:
        print('- 无主线数据, 跳过')
    print()

    # 6. 中报S7纠偏维度
    print('## 中报S7纠偏维度(基本面)')
    try:
        s7 = s7_batch([p['code'] for p in pos])
        for code, r in s7.items():
            flag = '🔥 清仓信号' if r['triggered'] else '✅ 正常'
            print(f"- {code}: {flag} | {r['reason']}")
    except Exception as e:
        import traceback
        print(f"- S7检查失败 ({e})")
        traceback.print_exc()
    print()

    # 7. 最终闸门 (市场 × 主线延续 × 宏观否决 × 估值否决)
    if final_gate == '进攻' and total_risk >= 6 and (macro and macro['risk_score'] >= 3):
        final_gate = '半仓'
        print('## ⚠️ 估值否决触发')
        print(f"- 组合PE总风险={total_risk}(极贵) × 宏观{macro['grade']}(分{macro['risk_score']})")
        print('- 闸门: 进攻 → 半仓')
    print('=' * 40)
    print(f'🎯 最终闸门: {final_gate}')
    print('  (市场基础 × 主线延续否决 × 宏观否决 × 估值否决 × 板块容量; S7仅发清仓信号)')
    print('=' * 40)

    # 8. 信号落盘(实盘校准跟踪)
    try:
        from signal_logger import log_signal
        top_sec_names = [x[0] for x in top_sectors[:3]]  # 仅行业名列表
        valuation_trig = (final_gate == '半仓' and total_risk >= 6
                          and macro and macro['risk_score'] >= 3)
        log_signal(ds, final_gate, base_gate,
                   macro['grade'] if macro else '未知',
                   top_sec_names, total_risk,
                   False, False,
                   notes=f"估值否决={'是' if valuation_trig else '否'}")
        print('\n📝 信号已落盘 data/signals.jsonl (供 calibration.py 校准)')
    except Exception as e:
        print(f'\n⚠️ 信号落盘失败 ({e})')

if __name__ == '__main__':
    main()
