"""
API 路由 - 回测分析（基于 chanlun-pro 回测引擎）
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Query

logger = logging.getLogger('backtest_route')
router = APIRouter(prefix="/api/v1/backtest", tags=["回测分析"])

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_bt_engine():
    """延迟加载回测引擎（避免启动时依赖缺失）"""
    import sys
    _CORE_SRC = str(BASE_DIR / "core")
    if _CORE_SRC not in sys.path:
        sys.path.insert(0, _CORE_SRC)
    from chanlun.backtesting.backtest import Backtest
    return Backtest


@router.get("/run")
async def run_backtest(
    symbol: str = Query(..., description="股票代码"),
    strategy: str = Query("default", description="策略名称"),
    start_date: str = Query("", description="开始日期 YYYY-MM-DD"),
    end_date: str = Query("", description="结束日期 YYYY-MM-DD"),
    initial_capital: float = Query(100000, description="初始资金"),
):
    """运行回测"""
    return {
        "status": "ok",
        "message": f"回测已启动: {symbol} / {strategy}",
        "params": {
            "symbol": symbol,
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
        },
    }


@router.get("/results")
async def get_backtest_results(
    task_id: str = Query(..., description="回测任务ID"),
):
    """获取回测结果"""
    return {
        "status": "ok",
        "task_id": task_id,
        "message": "回测结果查询（待实现）",
    }


@router.get("/strategies")
async def list_strategies():
    """列出可用策略"""
    return {
        "status": "ok",
        "strategies": [
            "default",
            "chanlun_xd_mmd",
            "chanlun_zs_tupo",
        ],
    }
