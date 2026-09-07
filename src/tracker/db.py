"""SQLite database schema and queries for onchain-volume-tracker."""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from .config import Config


SCHEMA = """
CREATE TABLE IF NOT EXISTS chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS chain_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_slug TEXT REFERENCES chains(slug),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tvl REAL,
    volume_24h REAL,
    volume_7d REAL,
    fees_24h REAL,
    volume_change_24h REAL,
    volume_change_7d REAL
);

CREATE TABLE IF NOT EXISTS protocols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    category TEXT,
    chain TEXT,
    tvl REAL
);

CREATE TABLE IF NOT EXISTS protocol_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_slug TEXT REFERENCES protocols(slug),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    volume_24h REAL,
    volume_7d REAL,
    volume_change_24h REAL
);

CREATE TABLE IF NOT EXISTS dex_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT,
    base_token TEXT,
    quote_token TEXT,
    price_usd REAL,
    volume_24h REAL,
    buy_volume_24h REAL,
    sell_volume_24h REAL,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memecoin_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT,
    symbol TEXT,
    name TEXT,
    chain TEXT,
    price_usd REAL,
    volume_24h REAL,
    price_change_24h REAL,
    txns_24h INTEGER,
    liquidity REAL,
    market_cap REAL,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chain_metrics_timestamp ON chain_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_protocol_metrics_timestamp ON protocol_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_chain_metrics_chain_slug ON chain_metrics(chain_slug);
CREATE INDEX IF NOT EXISTS idx_dex_pairs_fetched_at ON dex_pairs(fetched_at);
CREATE INDEX IF NOT EXISTS idx_memecoin_metrics_fetched_at ON memecoin_metrics(fetched_at);
CREATE INDEX IF NOT EXISTS idx_memecoin_metrics_symbol ON memecoin_metrics(symbol);
"""


@contextmanager
def get_db(config: Optional[Config] = None):
    """Context manager for database connection. Auto-initializes schema."""
    if config is None:
        config = Config.from_env()

    # Ensure directory exists
    db_dir = os.path.dirname(config.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Auto-initialize schema on every connection
    conn.executescript(SCHEMA)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def init_db(config: Optional[Config] = None):
    """Initialize database schema."""
    with get_db(config) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def store_chain_metrics(conn, slug: str, name: str, data: dict) -> int:
    """Store chain metrics. Returns row id."""
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO chains (name, slug) VALUES (?, ?)", (name, slug))
    conn.commit()

    cur.execute("""
        INSERT INTO chain_metrics
            (chain_slug, tvl, volume_24h, volume_7d, fees_24h, volume_change_24h, volume_change_7d)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        slug,
        data.get("tvl"),
        data.get("volume_24h"),
        data.get("volume_7d"),
        data.get("fees_24h"),
        data.get("volumeChangeOver24h"),
        data.get("volumeChangeOver7d"),
    ))
    conn.commit()
    return cur.lastrowid


def store_protocol_metrics(conn, slug: str, data: dict) -> int:
    """Store protocol metrics."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO protocol_metrics
            (protocol_slug, volume_24h, volume_7d, volume_change_24h)
        VALUES (?, ?, ?, ?)
    """, (
        slug,
        data.get("volume_24h"),
        data.get("volume_7d"),
        data.get("volumeChangeOver24h"),
    ))
    conn.commit()
    return cur.lastrowid


def store_protocols(conn, protocols: list[dict]):
    """Bulk store protocol metadata."""
    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO protocols (id, name, slug, category, chain, tvl)
            VALUES (:pid, :name, :slug, :category, :chain, :tvl)
        """, [
            {
                "pid": p.get("pid"),
                "name": p.get("name", ""),
                "slug": p.get("slug", ""),
                "category": p.get("category", ""),
                "chain": p.get("chains", ""),
                "tvl": p.get("tvl"),
            }
            for p in protocols
        ])


def store_dex_pairs(conn, pairs: list[dict]):
    """Bulk store DEX pair data."""
    with conn:
        conn.executemany("""
            INSERT INTO dex_pairs (chain_id, base_token, quote_token, price_usd, volume_24h, buy_volume_24h, sell_volume_24h)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                p.get("chainId"),
                p.get("baseToken", {}).get("name", ""),
                p.get("quoteToken", {}).get("name", ""),
                float(p.get("priceUsd", 0) or 0),
                float(p.get("volume", {}).get("h24", 0) or 0),
                0,  # DexScreener doesn't provide buy/sell breakdown
                0,
            )
            for p in pairs
        ])


def store_memecoin_metrics(conn, tokens: list[dict]):
    """Bulk store memecoin activity snapshots."""
    if not tokens:
        return
    with conn:
        conn.executemany("""
            INSERT INTO memecoin_metrics
                (token_address, symbol, name, chain, price_usd, volume_24h,
                 price_change_24h, txns_24h, liquidity, market_cap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                t.get("token_address"),
                t.get("symbol", ""),
                t.get("name", ""),
                t.get("chain", ""),
                t.get("price_usd"),
                t.get("volume_24h"),
                t.get("price_change_24h"),
                t.get("txns_24h"),
                t.get("liquidity"),
                t.get("market_cap"),
            )
            for t in tokens
        ])


def get_latest_memecoins(conn) -> list[dict]:
    """Get the most recent snapshot of every tracked memecoin token."""
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*
        FROM memecoin_metrics m
        WHERE m.id IN (
            SELECT MAX(id) FROM memecoin_metrics GROUP BY token_address
        )
        ORDER BY m.volume_24h DESC
    """)
    return [dict(row) for row in cur.fetchall()]


def get_chain_trends(conn, chain_slug: str, limit: int = 30) -> list[dict]:
    """Get historical chain metrics for trend analysis."""
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, tvl, volume_24h, volume_7d, fees_24h, volume_change_24h, volume_change_7d
        FROM chain_metrics
        WHERE chain_slug = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (chain_slug, limit))
    return [dict(row) for row in cur.fetchall()]


def get_latest_chain_metrics(conn) -> list[dict]:
    """Get the latest metrics for all chains."""
    cur = conn.cursor()
    cur.execute("""
        SELECT cm.*, c.name
        FROM chain_metrics cm
        JOIN chains c ON cm.chain_slug = c.slug
        WHERE cm.id IN (
            SELECT MAX(id) FROM chain_metrics GROUP BY chain_slug
        )
        ORDER BY cm.volume_24h DESC
    """)
    return [dict(row) for row in cur.fetchall()]


def get_top_movers(
    conn, n: int = 10, metric: str = "volume_change_24h", descending: bool = True
) -> list[dict]:
    """Get top or bottom N chains by an allowed metric."""
    allowed = {"volume_24h", "volume_change_24h", "volume_change_7d", "tvl"}
    if metric not in allowed:
        raise ValueError(f"Unsupported metric: {metric}")
    direction = "DESC" if descending else "ASC"
    cur = conn.cursor()
    cur.execute("""
        SELECT cm.*, c.name
        FROM chain_metrics cm
        JOIN chains c ON cm.chain_slug = c.slug
        WHERE cm.id IN (
            SELECT MAX(id) FROM chain_metrics GROUP BY chain_slug
        )
        AND cm.volume_change_24h IS NOT NULL
        ORDER BY cm.{} {}
        LIMIT ?
    """.format(metric, direction), (n,))
    return [dict(row) for row in cur.fetchall()]


def get_anomalies(conn, threshold: float = 50.0) -> list[dict]:
    """Get chains with volume changes exceeding threshold."""
    cur = conn.cursor()
    cur.execute("""
        SELECT cm.*, c.name
        FROM chain_metrics cm
        JOIN chains c ON cm.chain_slug = c.slug
        WHERE cm.id IN (
            SELECT MAX(id) FROM chain_metrics GROUP BY chain_slug
        )
        AND ABS(cm.volume_change_24h) >= ?
        ORDER BY ABS(cm.volume_change_24h) DESC
    """, (threshold,))
    return [dict(row) for row in cur.fetchall()]
