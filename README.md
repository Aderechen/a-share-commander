# A股短线指挥官模型 (A-Share Commander Model)

> 短线交易决策框架 + 自动化扫描系统。从「纯技术面情绪扫描」升级为「七维整合决策」，
> 解决原模型**缺国际宏观、缺估值温度计、缺基本面纠偏、缺板块容量检验**四大盲区。

## 核心思想

```
赚钱公式: 进场条件 > 仓位 > 止盈 > 止损
第一优先: 标的必须处于主线行业（资金抱团方向）— Alpha唯一来源
第二优先: 主线内竞价高开3-6%打板 — 强度筛选（回测+4.05%/胜率53.1%）
止损: -15%仅防灾难 + 逻辑证伪（机械止损负期望，勿用）
```

数据闭环来自于 2024-07 → 2026-08 的两年回测校准（详见各 backtest_*.py）。

## 七维扫描架构

| 维度 | 模块 | 数据源 | 否决权 |
|:--|:--|:--|:--|
| 市场(技术面) | `market_dimension.py` | 东财push2ex/push2 + 腾讯 | 基础闸门 |
| 宏观(国际) | `macro_layer.py` | FRED(美元/利率/VIX/美债) | ✅ 高压降档 |
| 事件(治理) | `fundamental_event_layer.py` | 东财公告API | 仅预警 |
| 估值(温度计) | `integrated_scan`内联PE | 腾讯qt.gtimg.cn | ✅ 极贵降档 |
| 持仓(动态) | `positions_io.py` | a-share-state/positions.md | — |
| 板块容量 | `sector_capacity_layer.py` | 东财行业板块资金流 | ✅ 过载降档 |
| 中报S7纠偏 | `fundamental_s7_layer.py` | akshare业绩报表 | 发清仓信号 |

**最终闸门** = 市场基础闸门 × 宏观否决权 × 估值否决权 × 板块容量否决权。

## 快速开始

```bash
# 1. 安装可选依赖(财务/中报层需要)
pip install -r requirements.txt

# 2. 每日盘后七维扫描
python3 integrated_scan.py YYYYMMDD
# 例: python3 integrated_scan.py 20260821

# 3. 旧版纯技术面(已弃用, 供对比)
python3 daily_scan.py YYYYMMDD

# 4. 每周五滚动回测校准
python3 backtest_2y.py
```

## 数据源与降级策略

- **东财 push2ex/push2**：涨停池/指数，高频限流 → 统一 curl subprocess + 重试
- **腾讯 qt.gtimg.cn**：实时行情/PE，稳定，作为降级链
- **FRED**：美元指数/利率/VIX/美债利差，稳定
- **东财公告API**：个股公告，偶发限流 → 事件层降级为空扫（不误判）
- **akshare 业绩报表**：中报财务，东财限流时降级（**不伪造数据**）

所有层均遵循「数据缺失→降级标注，不假装有数据，不强行给进攻」原则。

## 文件清单

```
commander-model/
├── integrated_scan.py          # 七维整合扫描(主入口, 推荐)
├── daily_scan.py               # 旧版纯技术面扫描
├── market_dimension.py         # 六维市场评分 + 主线聚合
├── macro_layer.py              # 宏观/国际层(FRED)
├── fundamental_event_layer.py  # 个股事件风险层(公告)
├── fundamental_score_layer.py  # 中报财务层(akshare)
├── fundamental_s7_layer.py     # 中报S7纠偏闭环
├── sector_capacity_layer.py    # 板块容量检验层
├── positions_io.py             # 持仓动态读取(替代硬编码)
├── model_v2.py                 # 规则引擎(止损/进攻/闸门)
├── backtest_*.py               # 回测校准(2年/全市场/行业/优化)
├── data/                       # K线缓存(已gitignore)
└── a-share-state/              # 持仓/选股/盲区状态(positions.md为模板)
```

## 已知局限 / 路线图

- [x] 宏观/国际层
- [x] 估值温度计
- [x] 事件风险层
- [x] 板块容量检验
- [x] 中报S7纠偏闭环
- [ ] 主线延续性验证（昨日主线今日是否仍有效）
- [ ] 回测分层：高利率/强美元时段作为分层变量重测夏普
- [ ] 实盘命中率校准（回测→实盘偏差追踪）

## 免责声明

本系统为个人交易研究工具，所有信号仅供决策参考，不构成投资建议。
短线交易高风险，请独立判断、自负盈亏。

### ⚠️ 持仓数据为估算态

- 模型通过 `positions_io.py` 读取 `~/炒股/a-share-state/positions.md`（**仓库外，不纳入版本控制**）。
- 该文件若为重建/反推值（成本按 -15% 灾难线反推、权重为历史快照），则**所有仓位/止损指令均为估算态，非实盘依据**。
- 仓库内 `a-share-state/positions.example.md` 仅为格式模板与示例数据，不代表任何真实持仓。
- 实盘使用前，务必以真实成本/权重覆盖该文件。
