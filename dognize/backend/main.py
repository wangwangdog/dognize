"""dognize - 后端主入口 (融合 a-stock-analyst + chanlun-pro)"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 确保模块可导入
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from loguru import logger

# 先初始化缓存和迁移
from data.cache import init_db, _migrate_v1_to_v2
init_db()
_migrate_v1_to_v2()

from routes.kline import router as kline_router
from routes.ai import router as ai_router
from routes.favorites import router as favorites_router
from routes.auth import router as auth_router
from routes.strategy import router as strategy_router
from routes.chanlun import router as chanlun_router
from routes.backtest import router as backtest_router
from routes.trade import router as trade_router

app = FastAPI(
    title="dognize",
    description="股票优选系统 - 后端服务",
    version="0.1.0",
)

# CORS - 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(kline_router)
app.include_router(ai_router)
app.include_router(favorites_router)
app.include_router(auth_router)
app.include_router(strategy_router)
app.include_router(chanlun_router)
app.include_router(backtest_router)
app.include_router(trade_router)

# === 启动时数据检查 ===
@app.on_event("startup")
async def startup_check():
    """启动时检查数据新鲜度，必要时提示更新"""
    try:
        from data.cache import _get_conn
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT MAX(trade_date) FROM kline_cache WHERE source='akshare' AND period='daily'"
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            last_date = row[0]
            days_ago = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
            logger.info(f"[启动检查] 最新缓存日线数据: {last_date} ({days_ago}天前)")
            if days_ago > 5:
                logger.warning(f"[启动检查] 数据已 {days_ago} 天未更新，建议运行数据更新脚本")
        else:
            logger.info("[启动检查] 缓存中无历史数据，首次运行建议执行批量下载")
    except Exception as e:
        logger.debug(f"[启动检查] 数据检查跳过: {e}")


@app.get("/api/root")
async def root():
    return {
        "service": "dognize",
        "version": "0.1.0",
        "status": "running",
        "api_docs": "/docs",
    }


@app.get("/api/ping")
async def ping():
    return {"pong": True, "time": __import__("datetime").datetime.now().isoformat()}


@app.get("/api/data/status")
async def data_status():
    """数据状态查询"""
    try:
        from data.cache import _get_conn
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT symbol, source, period, COUNT(*) as count, MAX(trade_date) as latest "
            "FROM kline_cache GROUP BY source, period ORDER BY source, period"
        )
        rows = cursor.fetchall()
        conn.close()

        sources = {}
        for r in rows:
            key = f"{r[1]}_{r[2]}"
            sources[key] = {
                "source": r[1],
                "period": r[2],
                "stocks": r[0],
                "records": r[3],
                "latest": r[4],
            }
        return {"status": "ok", "data": sources}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/data/update")
async def trigger_update():
    """手动触发增量更新（后台异步执行）"""
    script = BASE_DIR / "scripts" / "data_update.py"
    if not script.exists():
        return {"status": "error", "message": "更新脚本不存在"}
    try:
        python = sys.executable
        proc = subprocess.Popen(
            [python, str(script)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return {
            "status": "started",
            "message": "数据更新已启动（后台进程）",
            "pid": proc.pid,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# === 前端静态文件 ===
_frontend_dir = BASE_DIR.parent / "frontend" / "dist"
if _frontend_dir.is_dir():
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    class _NoCacheStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            resp = await super().get_response(path, scope)
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return resp

    app.mount("/assets", _NoCacheStaticFiles(directory=str(_frontend_dir / "assets")), name="frontend_assets")

    @app.api_route("/{path:path}", methods=["GET"])
    async def serve_frontend(path: str):
        if path.startswith(("api/", "chanlun/")) or path == "api" or path == "chanlun":
            from fastapi.responses import HTMLResponse
            return HTMLResponse(status_code=404)
        file_path = _frontend_dir / path
        if file_path.is_file():
            return FileResponse(str(file_path), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        return FileResponse(str(_frontend_dir / "index.html"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    logger.info(f"前端静态文件已挂载: {_frontend_dir}")
else:
    logger.warning("前端静态目录不存在 (frontend/dist)，仅 API 模式运行")


# === Chanlun-Pro 反向代理 ===
import httpx

@app.api_route("/chanlun-pro/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
@app.api_route("/chanlun-pro", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def chanlun_proxy(path: str = "", request: Request = None):
    """代理 chanlun-pro 到 9900 端口"""
    from config import CHANLUN_PRO_PORT
    target_path = path or ""
    target_url = f"http://localhost:{CHANLUN_PRO_PORT}/{target_path}"

    # 转发查询参数
    query = request.url.query
    if query:
        target_url += f"?{query}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            body = await request.body()
            headers = dict(request.headers)
            headers.pop("host", None)
            headers.pop("Host", None)

            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True,
            )
            return HTMLResponse(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
    except httpx.ConnectError:
        return HTMLResponse(
            content="<h1>Chanlun-Pro 未启动</h1><p>请在端口 9900 启动 chanlun-pro 服务</p>",
            status_code=502,
        )
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>代理错误</h1><p>{str(e)}</p>",
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn
    from config import WEB_HOST, WEB_PORT
    logger.info(f"启动 dognize 后端 (http://{WEB_HOST}:{WEB_PORT})...")
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT, log_level="info")
