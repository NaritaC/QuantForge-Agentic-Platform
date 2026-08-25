# Day 03：从数据到组合的完整研究闭环

> 时间预算：60 分钟。目标不是证明策略有效，而是能解释每个中间产物为什么存在、如何防止未来数据泄漏，以及如何对账。

## 1. 今天要跑通什么

```text
Raw → Staging → Quality → Universe → Factors → Signals
    → Orders → Fills → Holdings → NAV → Metrics
```

运行：

```powershell
python -m quantforge experiment --config configs/research-demo.yaml
python -m quantforge dashboard
```

演示数据是确定性合成数据，只证明工程链路可用，不构成策略证据。买入持有、网格交易和定投比较本轮明确暂缓。

## 2. 面试术语

| 中文 | English | 本项目中的含义 |
|---|---|---|
| 数据血缘 | data lineage | 输入请求、哈希、字段规则、代码版本和输出快照之间的关系 |
| 行数对账 | row reconciliation | 每一层输入、输出行数及差值；非零差值必须有业务规则 |
| 时点股票池 | point-in-time universe | 只使用调仓日当时可知的上市、退市、ST 和流动性状态 |
| 信号时点 | signal availability | 月末收盘后信号才可知，不能按同日开盘成交 |
| 目标权重 | target weight | 策略希望调仓后每只证券占组合资产的比例 |
| 订单与成交 | order vs. fill | “想交易”与“实际成交”是两张不同的事实表 |
| 组合记账 | portfolio accounting | 现金、持仓市值、费用和权益逐日守恒 |
| 未来函数 | look-ahead bias | 在历史时点使用当时尚不可知的数据 |

## 3. 因子公式

### 12-1 动量

在交易日序列上跳过最近 21 日，再观察到 252 日前：

\[
MOM_{i,t}=\frac{P_{i,t-21}}{P_{i,t-252}}-1
\]

跳过最近一个月常用于减少短期反转影响。实现位于
`quantforge.research.factors.compute_price_factors`。

### 60 日低波动

\[
r_{i,t}=\frac{P_{i,t}}{P_{i,t-1}}-1,
\qquad
LOWVOL_{i,t}=-\sqrt{\frac{1}{N}\sum_{k=0}^{N-1}(r_{i,t-k}-\bar r)^2}
\]

取负号后，波动越低，因子值越高。

### 截面 MAD 去极值与标准化

\[
MAD_t=median_i(|x_{i,t}-median_i(x_{i,t})|)
\]

先把值限制在 `median ± 5 × MAD`，再计算：

\[
z_{i,t}=\frac{x^{clip}_{i,t}-mean_i(x^{clip}_{i,t})}{std_i(x^{clip}_{i,t})}
\]

两个价格因子的 z-score 等权平均，得到组合排序分数。本演示不伪造 PIT ROA；ROA 要等财务事实数据满足公告时点与修订版本合同后再接入。

## 4. 为什么信号、订单、成交必须分表

- `signals`：月末收盘后知道的目标权重。
- `orders`：次日开盘计划及每次重试，可能处于 `filled`、`retry_pending`、`expired` 或 `rejected`。
- `fills`：真正改变现金和持仓的成交事实。

若证券停牌、涨停买不进、跌停卖不出或缺少必要行情，订单不能自动变成成交。本项目最多重试五个交易日。

成交价格示意：

\[
P^{buy}_{fill}=P_{open}(1+slippage),\qquad
P^{sell}_{fill}=P_{open}(1-slippage)
\]

买入现金变化为 `-(成交额 + 佣金)`；卖出为 `+(成交额 - 佣金 - 印花税)`。

## 5. NAV 与对账

每日收盘：

\[
Equity_t=Cash_t+\sum_i Shares_{i,t}\times Close_{i,t}
\]

\[
NAV_t=\frac{Equity_t}{InitialCash},\qquad
Drawdown_t=\frac{Equity_t}{\max_{s\leq t}Equity_s}-1
\]

最重要的工程检查不是收益高低，而是：

1. 只有 `fills` 能改变现金与持仓；
2. 买卖费用方向正确；
3. 目标股之外的旧持仓会产生卖单；
4. 每日权益等于现金加持仓市值；
5. 信号日期严格早于成交日期。

## 6. SQL 复核

```sql
-- 防止同日信号同日成交
SELECT COUNT(*) AS leakage_rows
FROM read_parquet('artifacts/runs/<run_id>/research/fills.parquet')
WHERE trade_date <= signal_date;

-- 订单状态分布
SELECT status, reason, COUNT(*) AS attempts
FROM read_parquet('artifacts/runs/<run_id>/research/orders.parquet')
GROUP BY status, reason
ORDER BY attempts DESC;

-- NAV 基本范围
SELECT MIN(trade_date), MAX(trade_date), MIN(nav), MAX(nav)
FROM read_parquet('artifacts/runs/<run_id>/research/nav.parquet');
```

## 7. 20 分钟代码阅读路线

1. `research/universe.py`：股票池为什么是时点函数。
2. `research/factors.py`：滚动窗口与截面变换如何分开。
3. `research/backtest.py`：订单约束、成交费用和组合记账。
4. `experiment.py`：如何把所有产物和哈希绑定到一次实验。

## 8. 面试自测

1. 为什么月末信号不能用月末开盘价成交？
2. `drop_duplicates(keep='last')` 为什么可能掩盖数据质量问题？
3. 订单和成交合成一张表会丢失什么信息？
4. 为什么今天的指数成分股不能直接回填历史股票池？
5. 如何证明改变未来价格不会改变过去的因子？
6. 如果供应商没有涨跌停价，你会怎样限制回测结论？
