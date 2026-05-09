# MEMORY.md - 老道 🦞 的长期记忆

## 关于我
- AI CTO，负责股票优选团队的开发与运维
- 老板: 狗哥 (CEO)
- 风格: 干脆利落，少废话多干活

## 项目: A-Stock Analyst
- 位置: `/home/dogzi/.openclaw/workspace/a-stock-analyst`
- 后端: FastAPI :8765
- 前端: Vue3 + Vite :3000
- AI: LangGraph + DeepSeek
- 数据源: AKShare + Baostock (双源)

## 部署备忘
- 部署在 Linux，user=dogzi，用户级 systemd 服务
- systemd: `a-stock-backend.service` (FastAPI :9901) + `chanlun-pro.service` (Flask :9900)
- Tailscale: `dogzi-ms-7d73.tailbc211b.ts.net` / 100.77.41.19
- Funnel 配置: `tailscale funnel --bg 9900` (直接传端口号)
- 首次配 Tailscale 需 `sudo tailscale set --operator=dogzi`
- Flask proxy `/backend/*` → FastAPI `:9901`

## chanlun-pro
- 位置: `/home/dogzi/.openclaw/workspace/cl-vendors/chanlun-pro`
- 端口: 9900 (Flask/Tornado)
- 依赖: uv 管理，Python 3.11，.venv 在新位置
- systemd: `chanlun-pro.service` (用户级，已更新路径)
- 外网: `https://dogzi-ms-7d73.tailbc211b.ts.net` 通过 Tailscale Funnel
- 授权: PyArmor 加密，pyarmor.rkey 放在 `src/pyarmor_runtime_005445/`
- 缠论引擎: 开源版 chan.py 替代（`.venv site-packages chan.pth`）

## 数据库合并状态
- 目标库: `~/.chanlun_pro/db/chanlun_klines.sqlite` (1.35 GB)
- chanlun-pro 原生 cl_* 表: 11 张（未修改）
- 从 stock_cache.db 迁移: 18 张表（含 stock_daily 273万行 + kline_cache 427万行）
- 从 sequoia_v2.db 补充: 33,434 行
- 新扩展表: 9 张（user_settings, agent_session/msg/cache, quant_strategy_run/hit_record, market_anomaly, trading_calendar_ext, user_zixuan_ext）
- 总计: 38 张表，约 716 万行

## 后端集成规划（参考 dogzi 方案文档）
### 2.2 TradingAgents-CN 多Agent集成
- 核心类 TradingAgentsGraph，程序化调用
- 封装 AgentAnalysisService 服务类
- 新增 Flask 路由 /ai/* (ai_routes.py)
- 依赖: tradingagents, langchain, dashscope/openai/anthropic
- 需约 4GB+ 内存

### 2.3 Sequoia 量化选股
- 6大策略适配到 chanlun-pro 数据接口
- SequoiaStrategyAdapter 类封装
- 新增路由 /quant/*
- 已有 a-stock-backend 的 sequoia 相关 API 在 9901 端口

### 2.4 AKShare 数据流水线
- 交易日历集成 → 盘口异动(20类) → 数据管道编排 → 并发控制
- 统一 Exchange 抽象层 (CompositeExchange: TDX 优先, AKShare 降级)

### 2.5 多用户与缓存
- 用户自选股表扩展
- 24h 分析结果缓存 (Redis)

### 前端融合方案
- 方案A: 独立容器并存 + 统一路由切换 (/chart/legacy vs /chart/chanlun)
- 方案B: Web Component 封装 (Custom Element 嵌入 Jinja2 模板)

## 故障记录
- 2026-05-06: AKShare 连不上（东方财富 RemoteDisconnected），Baostock 正常可替代

## 分层融合架构（规划）
a-stock-analyst + chanlun-pro 融合策略：
1. **前端层**：chanlun-pro Jinja2+TradingView 原界面不变，独立入口页引入 React 子应用，两套前端隔离共存
2. **后端层**：Flask 新增路由模块，复用 chanlun-pro 已有的用户认证和会话管理
3. **引擎层**：Sequoia-X、TradingAgents-CN、缠论引擎三个核心引擎各自独立，通过统一数据接口和消息队列协作
4. **数据层**：统一 Redis 缓存 + 共享数据库，AKShare 作为 chanlun-pro 原有数据源的补充

## 项目关键修改记录
- 2026-05-07: stock_daily 全量前复权重载（adjustflag=2），sequoia engine 已同步改为前复权
- big_deal_summary: 逐笔成交扫描，连续≤3笔买盘合并达价格分档阈值
- big_buy_summary: pkyd 盘口异动"有大买盘"数据入库
- 前端指标：有大买单 → big_buy_summary.qty；大单买入数 → hzeveryday.合计手数
- 所有定时任务统一交易日 17:30 并行触发
- 前端静态文件已加 no-cache 头

## 健康检查
- 日志位置: `backend/scripts/health_check.py`
- 检查项: 后端存活、kline_cache 每日数据、stock_daily 完整性、strategy_picks 选股、K线 API 采样
- Cron: 交易日 17:30（a-stock-health-check），周六早8点（a-stock-health-check-weekend）
- 非交易日自动回退: strategy_picks 和 kline 均会回退到最近交易日

## K线回退机制
- sequoia_engine.get_daily_kline() 优先，缺少最新交易日时自动 fallback 到 baostock
- kline.py 中 merge 逻辑：baostock 最新数据 + sequoia 历史补充

## 东方财富跳转
- 前端 Kline.vue 指标栏增加「📈 东方财富」tag
- URL: https://quote.eastmoney.com/{market}{code}.html
- 市场前缀: 6/688→sh, 0/3→sz, 8→bj

## 健康检查 cron 备忘录
- a-stock-health-check: 交易日 17:30 运行，有 failed 汇报
- a-stock-health-check-weekend: 周六 8:00 运行，有 failed 汇报
- health_check.py --json 输出机器可读格式
- 静默通过（所有 passed）不打扰
