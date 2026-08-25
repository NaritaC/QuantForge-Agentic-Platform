# 第 02 天学习：参考数据与动态股票池

[English](day-02-reference-data-and-universe.en.md) · [语言入口](day-02-reference-data-and-universe.md)

建议用时：60 分钟。学习目标是能够解释：为什么量化数据工程师不能使用今天下载的成分股名单选择历史股票，以及如何构造可审计的时点股票池。

## 0–15 分钟：术语与数据语义

- **证券主数据（Security Master）**：稳定的证券身份及上市、退市生命周期。证券名称只是属性，不能作为主键。
- **交易日历（Trading Calendar）**：明确记录交易所每天是否开市。“上市满 120 个交易日”不等于 `上市日期 + 120 个自然日`。
- **时点数据（Point in Time, PIT）**：在时刻 `t` 查询时，只能使用在 `t` 之前已经生效且已经可知的记录。
- **幸存者偏差（Survivorship Bias）**：把今天的股票名单回填到历史，会让失败和退市证券从样本中消失。
- **流动性代理变量（Liquidity Proxy）**：日成交额通常是价格与成交数量的乘积，以货币计量；跨来源比较前必须先统一单位和字段定义。
- **覆盖率（Coverage）**：有效观测数除以预期市场交易日数。供应商缺失一行数据并不自动代表股票停牌。

股票 (i) 在调仓日 (t) 的上市交易日龄定义为：

\[
Age_i(t)=\#\{d\in Calendar_{trade}: list\_date_i\le d\le t\}
\]

流动性得分定义为最近 60 个市场交易日内的平均成交额：

\[
Liquidity_i(t)=\frac{1}{N_i}\sum_{d\in W_{60}(t)}Amount_{i,d},\qquad N_i\ge48
\]

这里同时使用“60 日窗口”和“至少 48 个有效观测”：前者定义经济观察周期，后者是数据覆盖率门槛。

## 15–30 分钟：SQL 表达

核心 SQL 模式是：先按时点过滤数据，再聚合滚动窗口，连接有效期内的证券主数据和调仓日状态，最后进行截面排名。

```sql
WITH liquidity AS (
    SELECT
        instrument_id,
        avg(amount) AS liquidity_score,
        count(amount) AS observations
    FROM daily_bars
    WHERE trade_date BETWEEN :window_start AND :rebalance_date
    GROUP BY instrument_id
    HAVING count(amount) >= 48
),
state_at_close AS (
    SELECT instrument_id, is_st, trade_status
    FROM daily_bars
    WHERE trade_date = :rebalance_date
),
eligible AS (
    SELECT
        m.instrument_id,
        l.liquidity_score,
        s.trade_status
    FROM security_master AS m
    JOIN liquidity AS l USING (instrument_id)
    JOIN state_at_close AS s USING (instrument_id)
    WHERE m.list_date <= :minimum_list_date
      AND (m.delist_date IS NULL OR m.delist_date > :rebalance_date)
      AND NOT s.is_st
)
SELECT *, row_number() OVER (
    ORDER BY liquidity_score DESC, instrument_id
) AS liquidity_rank
FROM eligible
QUALIFY liquidity_rank <= 300;
```

其中，`:minimum_list_date` 必须由交易日历向前寻找第 120 个交易日得到，不能使用普通自然日加减。

需要理解的 SQL 知识点：

1. `GROUP BY` 将逐日行情聚合为每只股票一条流动性记录。
2. `HAVING` 在聚合后检查有效观测数量；这里不能用聚合前的 `WHERE` 替代。
3. `JOIN ... USING (instrument_id)` 要求各层使用同一个稳定证券标识。
4. `row_number() OVER (...)` 是窗口函数，在保留每只证券记录的同时完成截面排名。
5. 第二排序键 `instrument_id` 用于稳定处理并列值，保证重复运行结果一致。
6. DuckDB 的 `QUALIFY` 可以直接过滤窗口函数结果。

## 30–50 分钟：Python 实现审查

阅读 `src/quantforge/research/universe.py`，找出以下保护措施：

1. 必填字段检查会尽早阻止 Schema 漂移。
2. 对重复的证券—日期记录直接报错，不静默保留任意一条。
3. 调仓日期必须是交易所实际交易日。
4. 上市日龄根据交易日历计数，不使用自然日差。
5. 必须取得调仓日收盘时已经可知的 ST 状态。
6. 停牌证券仍保留在股票池中，由执行模拟器处理无法成交问题。
7. 流动性相同时使用 `instrument_id` 决定稳定顺序。
8. 从 Parquet 读取后再次统一日期类型；落盘往返可能暴露内存 Fixture 没有显示出的类型差异。

运行针对性测试：

```powershell
python -m pytest tests/unit/test_universe.py -q
```

建议亲自完成以下代码阅读练习：

- 找到 `liquidity_window` 与 `min_liquidity_observations` 的参数校验。
- 解释为什么 `trade_status == SUSPENDED` 没有被当作股票池删除条件。
- 将 `top_n=300` 临时改成 `top_n=2`，预测并核对测试输出。
- 在 Fixture 中制造重复主键，观察程序在哪一层失败。

## 50–60 分钟：面试演练

**问题 1：为什么不能使用今天下载的沪深 300 成分股做十年前的回测？**

因为指数成分会发生变化。把今天仍然存在的股票回填到历史，会删除退市、经营失败和被调出指数的证券，造成幸存者偏差。应当重建历史成分，或者使用只依赖当时可见数据的规则型动态股票池。

**问题 2：为什么停牌不等于缺失数据？**

停牌是已经观察到的市场状态；缺失数据可能来自供应商故障、网络失败或处理流水线错误。把两者都填成零收益或零成交额，会掩盖数据故障并扭曲波动率和流动性。

**问题 3：为什么同时使用 60 日窗口和 48 个观测门槛？**

60 日窗口定义因子的经济观察周期；48 个观测是覆盖率闸门，防止只有少量数据的股票得到不稳定或不可比较的流动性分数。

**问题 4：为什么停牌股票仍可能保留在研究股票池？**

股票池资格和订单能否执行是两个不同状态。直接删除停牌股票，相当于假设策略能够提前避开它，或者凭空完成卖出。正确做法是保留它，并在执行层记录订单未成交、现金未使用或旧持仓无法退出。

**问题 5：平均成交额和成交额总和有什么区别？**

如果每只股票都有完整的 60 个观测，两者的排名一致；当观测数不同，直接求和会系统性偏向数据更完整的股票。项目使用平均成交额，并额外要求至少 48 个观测，从而把经济指标与数据覆盖检查分开。

**问题 6：为什么需要对 Parquet 落盘后的数据重新测试？**

序列化可能改变空值列的具体数据类型。例如全部为空的退市日期可能读回为 `datetime64[ns]`，而小型内存 Fixture 可能是 Python `date`。只有经过真实存储往返的测试才能发现这类边界问题。

## 本节完成标准

完成后，你应当能够在不看材料的情况下：

1. 写出上市交易日龄和 60 日流动性公式。
2. 解释 PIT、幸存者偏差、覆盖率和停牌语义。
3. 逐段讲解上述 SQL 的过滤、聚合、连接和窗口排名。
4. 说明本项目为什么把股票池选择与订单执行分开。
5. 回答至少四个面试问题，并指出当前实现仍需要历史全市场数据和断点续传下载器。

