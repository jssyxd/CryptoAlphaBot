# CryptoAlphaBot

生产级加密货币量化交易机器人 — 支持 BTC/ETH 现货自动交易、多因子策略、**动态止盈**、严格风险管理与回测。

> **状态**：核心策略与风控已实现，可进行 paper / dry-run 测试。实盘前必须完成完整回测验证与参数敏感性分析。

## 项目背景与对话需求总结

本仓库由 GitHub Copilot Chat 对话驱动创建，原始需求来自对 [imbue-bit/AlphaGPT](https://github.com/imbue-bit/AlphaGPT) 的商业化探讨，最终落地为独立的 **CryptoAlphaBot**。

### 核心用户需求（已实现）

1. **交易标的**：BTC/USDT、ETH/USDT（Binance 现货），1h K线为主。
2. **多因子策略**：SMA10/SMA30 交叉 + RSI + MACD + 布林带综合信号。
3. **动态止盈**（关键创新点）：
   - 不再使用固定 5%。
   - 根据 **SMA10 穿过 SMA30 的交叉夹角** + **价格曲率** 自适应计算止盈。
   - 夹角陡（穿得快）→ 止盈更高（最高 15%）。
   - 夹角平缓 → 止盈较低（最低 4%）。
4. **风控规则**：
   - 日亏损 ≥ 10% → 当日停止交易。
   - 连续亏损 3 次 → 冷却 24 小时。
   - 单笔仓位 ≤ 账户 10%。
   - 最大回撤限制 15%。
5. **完整可维护文档**：本 README + 代码注释，方便下一个 AI Agent 或人类工程师接手。

### 待改进 / 待验证清单（Next Steps）

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P0 | 完整回测验证 | 样本内 / 样本外、滚动时间窗口（Walk-Forward）、蒙特卡洛压力测试 |
| P0 | 历史交易数据库 | 使用 SQLite 持久化所有信号、订单、PnL，支持后续分析 |
| P1 | 参数敏感性分析 | 对 angle_weight、curvature_weight、base_tp 做网格搜索 |
| P1 | 滑点与手续费真实模拟 | 当前 backtest 有基础滑点，需更精细 |
| P2 | Telegram 实时报警 | 已预留接口 |
| P2 | 实盘订单状态机 | 部分成交、超时、重试逻辑 |
| P3 | 多时间框架确认 | 15m + 1h + 4h 共振 |
| P3 | 与 AlphaGPT 因子融合 | 长期可考虑把 DRL 因子注入 |

## 架构

```
┌─────────────────────────────────────────────────┐
│ 实盘 / Paper 交易执行层 (trading/)              │
│ BinanceBroker + Executor + OrderManager         │
├─────────────────────────────────────────────────┤
│ 策略计算层 (strategy/)                          │
│ MultiFactorStrategy + DynamicTakeProfitEngine   │
├─────────────────────────────────────────────────┤
│ 数据处理层 (data/)                              │
│ DataFetcher (CCXT) + Processor + Storage        │
├─────────────────────────────────────────────────┤
│ 风险与仓位 (risk/)                              │
│ RiskControl + PositionManager + Portfolio       │
├─────────────────────────────────────────────────┤
│ 回测引擎 (backtest/)                            │
│ BacktestEngine + Runner                         │
└─────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/jssyxd/CryptoAlphaBot.git
cd CryptoAlphaBot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env：至少填 TRADING_MODE=sandbox
# 公开数据拉取不需要 API Key，实盘才需要
```

### 3. 冒烟测试（推荐先跑）

```bash
python smoke_test.py
```

会拉取公开 OHLCV → 计算信号 → 打印动态止盈示例 → 运行 2 分钟 paper 循环。

### 4. 回测

```bash
python -m backtest.runner
```

### 5. Paper / Dry-run 主循环

```bash
python main.py
```

## 动态止盈公式说明

```text
takeprofit = base + angle_contrib + curvature_contrib

angle_contrib     = normalize(crossover_angle) * angle_weight * (max_tp - base)
curvature_contrib = normalize(price_curvature) * curvature_weight * (max_tp - base)

最终 clamp 到 [4.0, 15.0]
```

参数位于 `config/strategy_params.json`。

## 回测方法论（推荐执行顺序）

1. **样本内回测**：用完整历史数据跑一遍，记录 baseline 指标（夏普、最大回撤、胜率、利润因子）。
2. **滚动时间窗口（Walk-Forward）**：
   - 训练窗口 6 个月 → 测试窗口 1 个月，滚动前进。
   - 记录每个 out-of-sample 区间的表现。
3. **样本内外对比**：确保样本外夏普下降不超过 30–40%。
4. **蒙特卡洛**：对交易序列做 bootstrap 重采样，评估最坏情况回撤分布。
5. **参数稳定性**：固定其他参数，只改变 angle_weight / curvature_weight，观察性能曲面。

历史交易应写入 SQLite（`data/trading.db`），方便后续分析。

## 风险声明

- 量化交易有亏损风险，本项目仅供研究与教育使用。
- 任何实盘使用前必须自行验证策略在样本外的有效性，并遵守当地法规。
- 作者不对任何资金损失负责。

## License

Apache-2.0（与 AlphaGPT 精神一致，便于商业化探索）。

---

**维护提示**：下一个接手的工程师 / AI Agent，请先阅读本 README 的「待改进清单」和 `strategy/dynamic_takeprofit.py`、`risk/risk_control.py`，再开始修改。
