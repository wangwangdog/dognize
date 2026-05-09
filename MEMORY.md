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
- systemd: `a-stock-backend.service` + `a-stock-frontend.service`
- Tailscale: `dogzi-ms-7d73.tailbc211b.ts.net` / 100.77.41.19
- Vite 必须配 `allowedHosts: true` 否则 Tailscale 域名被 403
- Funnel 配置: `tailscale funnel --bg 3000` (直接传端口号，不是 --https 443)
- 首次配 Tailscale 需 `sudo tailscale set --operator=dogzi`

## 故障记录
- 2026-05-06: AKShare 连不上（东方财富 RemoteDisconnected），Baostock 正常可替代

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
