#!/usr/bin/env python3
"""
数据库迁移脚本：
1. 将 stock_cache.db 所有表复制到 chanlun_klines.sqlite
2. 将 sequoia_v2.db stock_daily 合并到目标库
3. 创建扩展表（SQLite适配版）
4. chanlun-pro 原有 cl_* 表不动
"""

import sqlite3
import os
import time

TARGET = os.path.expanduser("~/.chanlun_pro/db/chanlun_klines.sqlite")
SRC1 = os.path.expanduser("/home/dogzi/.openclaw/workspace/a-stock-analyst/backend/data/stock_cache.db")
SRC2 = os.path.expanduser("/home/dogzi/.openclaw/workspace/a-stock-analyst/backend/data/sequoia_v2.db")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def get_tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

def copy_table(target, src_conn, table):
    """复制一张表的数据，跳过已存在的"""
    # 检查目标是否已有此表
    existing = get_tables(target)
    if table in existing:
        log(f"  表 {table} 已存在，跳过")
        return
    
    # 获取源表的建表语句
    schema = src_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
    if not schema or not schema[0]:
        log(f"  表 {table} 无 schema，跳过")
        return
    
    # 在目标库建表
    target.execute(schema[0])
    
    # 获取数据行数
    count = src_conn.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]
    if count == 0:
        log(f"  表 {table} 已建（空表）")
        target.commit()
        return
    
    # 分批复制数据
    BATCH = 50000
    cols = [r[1] for r in src_conn.execute(f"PRAGMA table_info(\"{table}\")")]
    col_names = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    
    copied = 0
    offset = 0
    while offset < count:
        rows = src_conn.execute(f"SELECT * FROM \"{table}\" LIMIT {BATCH} OFFSET {offset}").fetchall()
        if not rows:
            break
        target.executemany(f"INSERT OR IGNORE INTO \"{table}\" ({col_names}) VALUES ({placeholders})", rows)
        target.commit()
        copied += len(rows)
        offset += BATCH
        if copied % 200000 == 0 or offset >= count:
            log(f"  表 {table}: {copied}/{count} 行已复制")
    
    # 复制索引
    for idx in src_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='{table}' AND sql IS NOT NULL"):
        try:
            target.execute(idx[0])
        except sqlite3.OperationalError as e:
            log(f"  索引跳过: {e}")
    target.commit()
    log(f"  ✅ 表 {table}: {copied} 行完成")

def main():
    log("=" * 50)
    log("数据库迁移开始")
    log(f"目标库: {TARGET}")
    log(f"源库1: {SRC1}")
    log(f"源库2: {SRC2}")
    log("=" * 50)
    
    # 打开连接
    target = sqlite3.connect(TARGET)
    target.execute("PRAGMA journal_mode=WAL")
    target.execute("PRAGMA synchronous=OFF")
    target.execute("PRAGMA cache_size=-8000000")  # 8GB cache
    
    src1 = sqlite3.connect(SRC1)
    src2 = sqlite3.connect(SRC2)
    
    existing_target_tables = get_tables(target)
    log(f"目标库已有 {len(existing_target_tables)} 张表: {existing_target_tables}")
    
    # === 第一步：复制 stock_cache.db 全部表 ===
    log("\n📦 步骤1: 复制 stock_cache.db 全部表")
    src1_tables = get_tables(src1)
    log(f"源库1 有 {len(src1_tables)} 张表: {src1_tables}")
    
    for t in src1_tables:
        copy_table(target, src1, t)
    
    # === 第二步：复制 sequoia_v2.db stock_daily ===
    log("\n📦 步骤2: 复制 sequoia_v2.db stock_daily")
    src2_tables = get_tables(src2)
    log(f"源库2 有 {len(src2_tables)} 张表: {src2_tables}")
    
    if "stock_daily" not in existing_target_tables:
        copy_table(target, src2, "stock_daily")
    else:
        # stock_daily 已从 stock_cache.db 复制，检查是否需要合并 sequoia 的数据
        target_cnt = target.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
        src2_cnt = src2.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
        log(f"  stock_daily 已存在 (目标 {target_cnt} 行, 源2 {src2_cnt} 行)")
        
        # 找出 sequoia 有但目标没有的行，分批插入
        log("  检查需要补充的数据...")
        missing = src2.execute("""
            SELECT COUNT(*) FROM stock_daily s 
            WHERE NOT EXISTS (SELECT 1 FROM stock_daily t WHERE t.symbol=s.symbol AND t.date=s.date)
        """).fetchone()[0]
        if missing > 0:
            log(f"  有 {missing} 行需要补充，开始复制...")
            # 分批从 src2 补数据
            BATCH = 50000
            offset = 0
            total = src2_cnt
            copied = 0
            while offset < total:
                rows = src2.execute(f"""
                    SELECT s.* FROM stock_daily s 
                    WHERE NOT EXISTS (SELECT 1 FROM stock_daily t WHERE t.symbol=s.symbol AND t.date=s.date)
                    LIMIT {BATCH} OFFSET {offset}
                """).fetchall()
                if not rows:
                    break
                cols = [r[1] for r in src2.execute("PRAGMA table_info('stock_daily')")]
                col_names = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join("?" for _ in cols)
                target.executemany(f"INSERT OR IGNORE INTO stock_daily ({col_names}) VALUES ({placeholders})", rows)
                target.commit()
                copied += len(rows)
                offset += BATCH
            log(f"  ✅ 补充了 {copied} 行")
        else:
            log("  无需补充")
    
    # === 第三步：创建扩展表 ===
    log("\n📦 步骤3: 创建扩展表")
    
    # 3.1 user_settings
    target.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id TEXT PRIMARY KEY,
        default_llm_provider TEXT DEFAULT 'qwen',
        default_analysis_depth TEXT DEFAULT 'standard' CHECK(default_analysis_depth IN ('quick','standard','deep')),
        agent_memory_enabled INTEGER DEFAULT 1,
        quant_strategy_weights TEXT,
        email_alert TEXT,
        webhook_url TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )
    """)
    log("  ✅ 3.1 user_settings")
    
    # 3.2 agent_session
    target.execute("""
    CREATE TABLE IF NOT EXISTS agent_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        session_uuid TEXT NOT NULL UNIQUE,
        market TEXT DEFAULT 'a_share',
        symbol TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        last_active TEXT DEFAULT (datetime('now','localtime'))
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_agent_session_user ON agent_session(user_id)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_agent_session_symbol ON agent_session(symbol)")
    log("  ✅ 3.2 agent_session")
    
    # 3.2 agent_message
    target.execute("""
    CREATE TABLE IF NOT EXISTS agent_message (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
        content TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_session ON agent_message(session_id)")
    log("  ✅ 3.2 agent_message")
    
    # 3.2 agent_analysis_cache
    target.execute("""
    CREATE TABLE IF NOT EXISTS agent_analysis_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        analysis_type TEXT NOT NULL,
        result TEXT NOT NULL,
        cached_at TEXT DEFAULT (datetime('now','localtime')),
        expires_at TEXT
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_aac_symbol_market ON agent_analysis_cache(symbol, market)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_aac_expires ON agent_analysis_cache(expires_at)")
    log("  ✅ 3.2 agent_analysis_cache")
    
    # 3.3 quant_strategy_run
    target.execute("""
    CREATE TABLE IF NOT EXISTS quant_strategy_run (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        strategy_name TEXT NOT NULL,
        market TEXT NOT NULL,
        scan_scope TEXT,
        run_at TEXT DEFAULT (datetime('now','localtime')),
        status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed')),
        total_scanned INTEGER,
        matched_count INTEGER,
        error_message TEXT
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_qsr_user ON quant_strategy_run(user_id)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_qsr_run_at ON quant_strategy_run(run_at)")
    log("  ✅ 3.3 quant_strategy_run")
    
    # 3.3 quant_hit_record
    target.execute("""
    CREATE TABLE IF NOT EXISTS quant_hit_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        code_name TEXT,
        strategy_name TEXT NOT NULL,
        signal_type TEXT NOT NULL CHECK(signal_type IN ('buy','sell','hold')),
        signal_strength REAL,
        details TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_qhr_run ON quant_hit_record(run_id)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_qhr_symbol ON quant_hit_record(symbol)")
    log("  ✅ 3.3 quant_hit_record")
    
    # 3.4 market_anomaly
    target.execute("""
    CREATE TABLE IF NOT EXISTS market_anomaly (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        anomaly_type TEXT NOT NULL,
        occur_time TEXT NOT NULL,
        price REAL,
        volume INTEGER,
        extra TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )
    """)
    target.execute("CREATE INDEX IF NOT EXISTS idx_ma_symbol_time ON market_anomaly(symbol, occur_time)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_ma_type ON market_anomaly(anomaly_type)")
    log("  ✅ 3.4 market_anomaly")
    
    # 3.5 trading_calendar
    target.execute("""
    CREATE TABLE IF NOT EXISTS trading_calendar_ext (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL UNIQUE,
        market TEXT DEFAULT 'a_share',
        is_open INTEGER DEFAULT 1
    )
    """)
    target.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tce_date_market ON trading_calendar_ext(trade_date, market)")
    log("  ✅ 3.5 trading_calendar_ext")
    
    # 3.6 user_zixuan_ext
    target.execute("""
    CREATE TABLE IF NOT EXISTS user_zixuan_ext (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        market TEXT NOT NULL,
        group_name TEXT DEFAULT '默认分组',
        symbol TEXT NOT NULL,
        code_name TEXT,
        sort_order INTEGER DEFAULT 0,
        color_tag TEXT,
        added_at TEXT DEFAULT (datetime('now','localtime'))
    )
    """)
    target.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uzx_ugp_sym ON user_zixuan_ext(user_id, market, group_name, symbol)")
    target.execute("CREATE INDEX IF NOT EXISTS idx_uzx_user ON user_zixuan_ext(user_id)")
    log("  ✅ 3.6 user_zixuan_ext")
    
    target.commit()
    
    # === 汇总报告 ===
    log("\n" + "=" * 50)
    log("📊 迁移完成报告")
    log("=" * 50)
    
    all_tables = get_tables(target)
    log(f"目标库总计: {len(all_tables)} 张表")
    
    total_rows = 0
    for t in sorted(all_tables):
        cnt = target.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        total_rows += cnt
        prefix = "cl_" if t.startswith("cl_") else "  "
        log(f"  {prefix} {t:40s} → {cnt:>10,} 行")
    
    log(f"\n  总计: {total_rows:,} 行")
    log(f"  数据库大小: {os.path.getsize(TARGET) / 1024 / 1024 / 1024:.2f} GB")
    log("✅ 迁移完成!")
    
    target.close()
    src1.close()
    src2.close()

if __name__ == "__main__":
    main()
