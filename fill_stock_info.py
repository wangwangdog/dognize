"""补齐 all_stock_info 财务数据（市值、每股收益、市盈率）- 并发版"""
import sys, time, sqlite3, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "backend")
import akshare as ak
import baostock as bs

DB = "backend/data/stock_cache.db"
MAX_WORKERS = 8
BATCH = 100
_db_lock = threading.Lock()

def fetch_one(symbol):
    prefix = "sh" if symbol.startswith("6") or symbol.startswith("68") else "sz"
    mc = None; eps = None
    try:
        info = ak.stock_individual_info_em(symbol)
        for _, r in info.iterrows():
            if "总市值" in str(r.iloc[0]):
                mc = float(r.iloc[1])
    except: pass
    try:
        rs = bs.query_operation_data(f"{prefix}.{symbol}", year="2026", quarter="1")
        while rs.next():
            row = rs.get_row_data()
            if row[3]: eps = float(row[3])
    except: pass
    return symbol, mc, eps

def write_batch(rows):
    with _db_lock:
        conn = sqlite3.connect(DB)
        for sym, mc, eps in rows:
            pe = None
            if eps and eps > 0 and mc:
                pe = round(mc / (eps * 1.261e9), 2)  # approximate using avg shares
            conn.execute("UPDATE all_stock_info SET market_cap=?, eps=?, pe_ratio=? WHERE symbol=?", (mc, eps, pe, sym))
        conn.commit()
        conn.close()

def main():
    conn = sqlite3.connect(DB)
    missing = [r[0] for r in conn.execute("SELECT symbol FROM all_stock_info WHERE market_cap IS NULL").fetchall()]
    conn.close()
    print(f"待补齐: {len(missing)} 只")

    bs.login()
    batch = []
    ok = 0
    fail = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, sym): sym for sym in missing}
        for i, f in enumerate(as_completed(futures)):
            sym, mc, eps = f.result()
            if mc or eps:
                batch.append((sym, mc, eps))
                ok += 1
            else:
                fail += 1
            
            if len(batch) >= BATCH:
                write_batch(batch)
                batch = []

            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(missing)}: OK={ok}, 失败={fail}")

        if batch:
            write_batch(batch)

    bs.logout()
    print(f"\n✅ 完成: 成功 {ok}, 失败 {fail}")

if __name__ == "__main__":
    main()
