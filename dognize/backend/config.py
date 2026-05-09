"""dognize - 统一配置"""
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# ── 数据库 ──
_DEFAULT_DB = BASE_DIR / "data" / "stock_cache.db"
_EXISTING_DB = Path("/home/dogzi/.openclaw/workspace/a-stock-analyst/backend/data/stock_cache.db")
# 优先复用已有关联项目的数据库，避免数据重建
DB_PATH = _EXISTING_DB if _EXISTING_DB.exists() else _DEFAULT_DB

# 缠论缓存数据库
CHANLUN_DB_PATH = BASE_DIR / "data" / "chanlun_cache.db"

# 数据源优先级: akshare > baostock
DATA_SOURCES = ["akshare", "baostock"]

# 校验容差
VALIDATION_TOLERANCE = {
    "open": 0.02,   # 开盘价 ±2%
    "close": 0.02,  # 收盘价 ±2%
    "high": 0.03,   # 最高价 ±3%
    "low": 0.03,    # 最低价 ±3%
    "volume": 0.05, # 成交量 ±5%
}

# 请求间隔(秒)，避免被封
REQUEST_INTERVAL = 0.5

# ── Chanlun-Pro 配置 ──

# WEB 服务配置
WEB_HOST = '0.0.0.0'
WEB_PORT = 8765

# 登录密码 (为空则免登录)
LOGIN_PWD = ''

# 项目数据保存路径，如果以 . 开头，则保存到 home 目录
DATA_PATH = ".dognize_data"

# 代理服务器配置
PROXY_HOST = '127.0.0.1'
PROXY_PORT = 7890

# 数据库配置
DB_TYPE = "sqlite"   # 支持 mysql 与 sqlite
DB_HOST = '127.0.0.1'
DB_PORT = 3306
DB_USER = 'root'
DB_PWD = '123456'
DB_DATABASE = 'dognize_klines'

# Redis 配置（不使用则设置为空）
REDIS_HOST = ''
REDIS_PORT = 6379

# 各市场交易所设置
EXCHANGE_A = "baostock"        # 沪深A股市场
EXCHANGE_HK = "tdx_hk"         # 港股市场
EXCHANGE_FUTURES = "tdx_futures"   # 期货市场
EXCHANGE_NY_FUTURES = "tdx_ny_futures"  # 纽约期货市场
EXCHANGE_CURRENCY = "binance"       # 数字货币（合约）
EXCHANGE_CURRENCY_SPOT = "binance_spot"  # 数字货币（现货）
EXCHANGE_US = "tdx_us"         # 美股市场
EXCHANGE_FX = "tdx_fx"         # 外汇市场

# Chanlun-Pro 源路径
CLP_SRC = str(BASE_DIR.parent / "chanlun-vendors" / "chanlun-pro" / "src")

# Chanlun-Pro 服务端口（独立部署）
CHANLUN_PRO_PORT = 9900
