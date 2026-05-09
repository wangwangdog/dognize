"""基本面数据分析"""
from datetime import datetime
from typing import Optional

from loguru import logger

from data import akshare_fetcher
from data.cache import save_fundamentals, get_fundamentals


def get_fundamental_summary(symbol: str, use_cache: bool = True) -> Optional[dict]:
    """
    获取基本面摘要信息（优先从合并数据库读取，AKShare 降级）
    """
    import sqlite3
    from pathlib import Path

    # 1. 优先从合并数据库读取
    try:
        merged = str(Path.home() / ".chanlun_pro" / "db" / "chanlun_klines.sqlite")
        conn = sqlite3.connect(merged)
        row = conn.execute(
            "SELECT name, market_cap, eps, industry FROM all_stock_info WHERE symbol=?",
            (symbol,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return {
                "symbol": symbol,
                "name": row[0],
                "market_cap": row[1],
                "circulating_market_cap": None,
                "industry": row[3] or "",
                "listing_date": "",
                "total_shares": None,
                "circulating_shares": None,
            }
    except Exception:
        pass

    # 2. 从缓存读取
    if use_cache:
        cached = get_fundamentals(symbol, "summary")
        if cached:
            return cached["data"]

    # 3. 降级到 AKShare（带超时）
    info = akshare_fetcher.get_individual_info(symbol)
    if not info:
        name = _get_name_from_list_quick(symbol)
        if not name:
            return None
        summary = {
            "symbol": symbol,
            "name": name,
            "market_cap": None,
            "circulating_market_cap": None,
            "industry": "",
            "listing_date": "",
            "total_shares": None,
            "circulating_shares": None,
        }
        return summary

    summary = {
        "symbol": symbol,
        "name": str(info.get("股票简称", info.get("name", ""))),
        "market_cap": _parse_float(info.get("总市值", "")),
        "circulating_market_cap": _parse_float(info.get("流通市值", "")),
        "industry": str(info.get("行业", info.get("industry", ""))),
        "listing_date": str(info.get("上市时间", "")),
        "total_shares": _parse_float(info.get("总股本", "")),
        "circulating_shares": _parse_float(info.get("流通股", "")),
    }
    return summary


# 缓存全量股票名称映射，避免重复请求
_STOCK_NAME_CACHE = None


def _get_name_from_list_quick(symbol: str) -> Optional[str]:
    """从合并数据库或 AKShare 获取股票名称"""
    import sqlite3
    from pathlib import Path
    merged = str(Path.home() / ".chanlun_pro" / "db" / "chanlun_klines.sqlite")
    try:
        conn = sqlite3.connect(merged)
        row = conn.execute("SELECT name FROM all_stock_info WHERE symbol=?", (symbol,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def _parse_float(val) -> Optional[float]:
    """安全的 float 转换"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", "").replace("%", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None
