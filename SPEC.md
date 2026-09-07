# Spec: onchain-volume-tracker

## Goal
A Python CLI tool that aggregates onchain DeFi volume data from free APIs (DeFiLlama, DexScreener), detects trending and declining chains/categories/protocols, and outputs a formatted report to stdout + Discord webhook. Runs on a schedule via launchd.

## Data Sources (free, no API keys)
1. **DeFiLlama** (https://api.llama.fi)
   - `/overview/dexs` — daily DEX volume data
   - `/v2/chains` — chain TVL + 24h/7d volume changes
   - `/protocols` — all protocols with TVL, chain, category
   - `/historicalChainTvl/{chain}` — historical chain TVL
   - `/overview/fees` — fees/revenue by chain and protocol

2. **DexScreener** (https://api.dexscreener.com/latest/dex)
   - `/search?q={token}` — search pairs by token symbol
   - `/tokens/{address}` — get all pairs for a token

## Core Features

### 1. Data Collection Module
- Fetches chain-level metrics from DeFiLlama (`/v2/chains`, `/overview/dexs`, `/overview/fees`)
- Fetches protocol-level metrics from DeFiLlama (`/protocols`)
- Fetches hot pair data from DexScreener (top tokens by search volume or predefined list)
- Stores all raw data in SQLite for historical analysis
- Rate-limits respect of API constraints (no key = conservative polling)

### 1b. Memecoin Activity Module
- DexScreener `search` over a configurable memecoin watchlist, plus
  `token-profiles/latest/v1` and `token-boosts/latest/v1` for new-listing /
  attention signals (deduped to one best pair per token)
- Where money flows: memecoin 24h volume aggregated by chain
- What's heating up: top memecoins by volume and by 24h price surge, plus
  memecoin-infrastructure TVL (DeFiLlama `Launchpad`/`Meme` categories and
  `pump`/`meme`-named protocols, excluding bridges/RWA)
- Top wallets: best-effort Solana top holders via public RPC
  `getTokenLargestAccounts` (graceful when rate-limited); EVM needs a paid provider

### 2. Trend Analysis Engine
- Calculates volume deltas: 24h vs 7d rolling averages per chain
- Calculates volume deltas: 24h vs 7d rolling averages per category
- Calculates top movers: chains/protocols with highest % volume increase or decrease
- Flags anomalies: chains with >50% volume surge or drop in 24h
- Ranks: top 10 chains by volume, top 10 by growth, top 10 by decline

### 3. Report Generation
- CLI output: formatted text with sections (Top Chains, Top Movers, Category Trends, Anomalies)
- Markdown report: for Discord/webhook rendering
- Color-coded console output (green for up, red for down)

### 4. Discord Integration
- Sends formatted report to Discord via webhook
- Configurable channel (default: command-center in Hive server)
- Includes: summary stats, top movers, anomalies section

### 5. Scheduling
- launchd plist for macOS scheduling
- Default: every 6 hours
- Configurable interval

## Project Structure
```
onchain-volume-tracker/
├── pyproject.toml
├── requirements.txt
├── README.md
├── src/
│   └── tracker/
│       ├── __init__.py
│       ├── cli.py          # CLI entry point
│       ├── collector.py    # Data fetching from DeFiLlama + DexScreener
│       ├── analyzer.py     # Trend analysis, delta calculations
│       ├── report.py       # Report formatting (CLI + Discord)
│       ├── db.py           # SQLite storage schema + queries
│       └── config.py       # Configuration (webhook URL, interval)
├── tests/
│   ├── test_collector.py
│   ├── test_analyzer.py
│   └── test_report.py
└── launchd/
    └── com.onchain-tracker.plist
```

## CLI Commands
```
tracker run              # Fetch latest data, analyze, generate full report (chain + memecoin)
tracker memes            # Memecoin-only: volume, surge, money flow, TVL, top holders, followed wallets
tracker wallet <ADDR>    # Show a trader wallet's recent on-chain buy/sell activity
tracker trends           # Show historical trends from SQLite
tracker chains           # List all tracked chains with current stats
tracker top              # Top 10 chains by volume / growth / decline
```

## Configuration
Environment variables / config file:
- `DEFLAMA_WEBHOOK_URL` — Discord webhook for sending reports
- `DEFAULT_CHAINS` — comma-separated list of chains to track (default: all from DeFiLlama)
- `CHECK_INTERVAL` — hours between runs (default: 6)

## SQLite Schema
```sql
CREATE TABLE chains (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL
);

CREATE TABLE chain_metrics (
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

CREATE TABLE protocols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    category TEXT,
    chain TEXT,
    tvl REAL
);

CREATE TABLE protocol_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_slug TEXT REFERENCES protocols(slug),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    volume_24h REAL,
    volume_7d REAL,
    volume_change_24h REAL
);

CREATE TABLE dex_pairs (
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

CREATE TABLE memecoin_metrics (
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
```

## Acceptance Criteria
- [ ] CLI runs and produces a formatted report
- [ ] DeFiLlama data is fetched correctly (chains, protocols, fees)
- [ ] DexScreener data is fetched correctly (top pairs)
- [ ] Memecoin module ranks tokens by volume/surge and aggregates money flow by chain
- [ ] Memecoin infrastructure TVL (launchpads) is captured
- [ ] Top-holder (wallet) lookup degrades gracefully when public RPC is rate-limited
- [ ] SQLite stores data persistently with trend history
- [ ] Trend analysis correctly identifies top movers and anomalies
- [ ] Discord webhook delivers formatted report
- [ ] launchd plist schedules runs every 6 hours
- [ ] All tests pass

## Notes
- DeFiLlama has no rate limit for free usage but be respectful (1 req/s max)
- DexScreener API is free and has generous rate limits
- No API keys needed for V1 — Dune integration is a future V2 enhancement
- SQLite chosen for zero-dependency local persistence (already on macOS)

