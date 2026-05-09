
---

## 数据库（stock_cache.db）

所有数据存储在 `backend/data/stock_cache.db`（SQLite）。

### 核心表

#### stock_daily — 日K线（前复权）
**数据来源：** baostock（adjustflag=2，前复权），单日增量通过 sequoia engine 同步  
**数据量：** 2730010 条，4985 只股票  
**日期范围：** 2024-01-02 ~ 2026-05-07

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增ID |
| symbol | TEXT | 股票代码 |
| date | TEXT | 交易日期（YYYY-MM-DD） |
| open | REAL | 开盘价（前复权） |
| high | REAL | 最高价 |
| low | REAL | 最低价 |
| close | REAL | 收盘价 |
| volume | REAL | 成交量（股） |
| turnover | REAL | 成交额（元） |

#### big_deal_summary — 大笔买入统计
**数据来源：** 逐笔成交扫描（akshare tick），连续≤3笔买盘合并达阈值即为1次大笔买入  
**触发时间：** 交易日 15:05  
**分档阈值：** 5元↓/5~10/10~50/50~100/100~500/500↑ → 50000/25000/15000/6000/3000/1000手  
**剔除规则：** 开盘 09:30 前（集合竞价）、尾盘 15:00 后不计入  
**数据量：** 4939 条/日

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | TEXT | 交易日期 |
| symbol | TEXT | 股票代码 |
| name | TEXT | 股票名称 |
| big_buy_count | INTEGER | 大笔买入次数 |
| big_buy_lots | REAL | 大笔买入总手数 |
| big_buy_amount | REAL | 大笔买入总金额（元） |
| total_lots | REAL | 全日总成交手数 |
| total_amount | REAL | 全日总成交金额（元） |

#### big_buy_summary — 有大买盘记录
**数据来源：** 盘口异动（akshare `stock_changes_em` 的"有大买盘"分类）  
**触发时间：** 交易日 17:30（随 pkyd.py）  
**数据量：** 7944 条（含历史）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增ID |
| trade_date | TEXT | 交易日期 |
| symbol | TEXT | 股票代码 |
| name | TEXT | 股票名称 |
| time | TEXT | 发生时间（HH:MM:SS） |
| qty | REAL | 买入数量（股） |
| price | REAL | 成交单价（元） |
| change | REAL | 涨跌幅 |
| amount | REAL | 成交金额（元） |

#### hzeveryday — 大笔买入汇总
**数据来源：** 盘口异动→大笔买入分类，经 `wsqllite.py` → `hzeveryday.py` 汇总  
**数据量：** 5366 条

| 字段 | 类型 | 说明 |
|------|------|------|
| 股票代码 | TEXT | 股票代码 |
| 股票名称 | TEXT | 股票名称 |
| 大笔买数 | INTEGER | 大笔买入次数 |
| 合计金额 | REAL | 合计金额（元） |
| 合计手数 | REAL | 合计手数 |
| 买入日期 | TEXT | 交易日期 |

#### all_stock_info — 全市场股票基本信息
**数据来源：** akshare（代码名称）+ stock_individual_info_em（市值）+ baostock（每股收益）  
**数据量：** 4939 只

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | TEXT | 股票代码 |
| name | TEXT | 股票名称 |
| market_cap | REAL | 总市值 |
| eps | REAL | 每股收益（最新季度） |
| pe_ratio | REAL | 市盈率 |
| industry | TEXT | 行业 |
| listing_date | TEXT | 上市日期 |
| updated_at | TEXT | 更新时间 |

#### trade_calendar — A股交易日历
**数据来源：** baostock `query_trade_dates`  
**数据量：** 1096 天

| 字段 | 类型 | 说明 |
|------|------|------|
| calendar_date | TEXT | 日历日期（YYYY-MM-DD） |
| is_trading_day | INTEGER | 是否交易日（1=是，0=否） |

### 辅助表

| 表名 | 说明 |
|------|------|
| kline_cache | K线缓存，多源数据用于双源校验 |
| kline_check_log | AKShare vs Baostock 双源校验日志 |
| fundamentals_cache | 基本面缓存（a-share个股信息） |
| strategy_picks | 策略选股结果（sequoia 每日运行） |
| vol20day | 20日涨幅排名数据 |
| analysis_cache | AI 分析结果缓存 |
| favorites | 用户自选股 |
| users | 用户信息 |
| stock_records | 大笔买入原始记录（盘口异动明细） |
| download_progress | 数据下载进度跟踪 |

### 定时任务

| 任务 | 时间 | 说明 |
|------|------|------|
| a-stock-abnormal-update | 交易日 17:30 | sequoia 数据同步 + 策略运行 |
| a-stock-daily-update | 交易日 17:30 | kline_cache 增量更新 |
| big_deal_summary | 交易日 15:05 | 逐笔成交大笔买入扫描 |
| a-stock-pkyd | 交易日 17:30 | 盘口异动全流程 + 有大买盘入库 |
