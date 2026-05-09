"""
API 路由 - 实盘交易（基于 chanlun-pro 交易引擎）
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Query

logger = logging.getLogger('trade_route')
router = APIRouter(prefix="/api/v1/trade", tags=["实盘交易"])

BASE_DIR = Path(__file__).resolve().parent.parent


@router.get("/status")
async def trade_status():
    """交易系统状态"""
    return {
        "status": "ok",
        "system": "dognize-trade",
        "version": "0.1.0",
        "mode": "paper",  # 默认模拟交易
    }


@router.get("/positions")
async def get_positions():
    """获取持仓"""
    return {
        "status": "ok",
        "positions": [],
    }


@router.post("/order")
async def place_order(
    symbol: str = Query(..., description="股票代码"),
    side: str = Query(..., description="买卖方向: buy/sell"),
    price: float = Query(0, description="价格（0表示市价单）"),
    quantity: int = Query(..., description="数量"),
):
    """下单"""
    return {
        "status": "pending",
        "message": f"订单已提交: {symbol} {side} {quantity}",
        "order_id": "demo_" + symbol,
    }


@router.get("/orders")
async def get_orders():
    """获取订单列表"""
    return {
        "status": "ok",
        "orders": [],
    }
