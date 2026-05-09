"""
交易所数据库接入（基于 chanlun-pro exchange_db 适配）
"""
import logging
from pathlib import Path

logger = logging.getLogger('exchange_db')

# 导入 chanlun exchange 模块
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
_CORE_SRC = str(BASE_DIR / "core")
if _CORE_SRC not in sys.path:
    sys.path.insert(0, _CORE_SRC)

from chanlun.exchange.exchange_db import ExchangeDB

# 重新导出让上层方便使用
__all__ = ['ExchangeDB']
