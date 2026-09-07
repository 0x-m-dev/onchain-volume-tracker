"""Tests for the memecoin activity module."""

import pytest

from tracker.analyzer import TrendAnalyzer
from tracker.collector import DataCollector
from tracker.config import Config
from tracker.db import get_db, store_memecoin_metrics
from tracker.holders import get_token_top_holders
from tracker.report import format_memecoin_cli_report, _money_fmt, _pct


def _sample_pair(symbol="PEPE", addr="0xpepe", chain="ethereum",
                 vol=1_000_000, liq=500_000, chg=25.0, mc=800_000_000):
    return {
        "chainId": chain,
        "dexId": "uniswap",
        "pairAddress": f"pair-{symbol}",
        "priceUsd": "0.00001",
        "marketCap": mc,
        "baseToken": {"address": addr, "name": symbol, "symbol": symbol},
        "quoteToken": {"address": "0xeth", "name": "ETH", "symbol": "ETH"},
        "priceChange": {"m5": 0.1, "h1": 2.0, "h6": 10.0, "h24": chg},
        "volume": {"h24": vol, "h6": vol * 0.4, "h1": vol * 0.1, "m5": vol * 0.01},
        "txns": {
            "h24": {"buys": 100, "sells": 50},
            "h1": {"buys": 10, "sells": 5},
        },
        "liquidity": {"usd": liq, "base": 1, "quote": 1},
        "url": f"https://dexscreener.com/{chain}/x",
    }


# --- report helpers ---------------------------------------------------------

def test_money_fmt_compacts():
    assert _money_fmt(1_500_000) == "$1.50M"
    assert _money_fmt(340_000) == "$340.0K"
    assert _money_fmt(1_200_000_000) == "$1.20B"
    assert _money_fmt(None) == "n/a"


def test_pct_signed_and_flat():
    assert _pct(5.0) == "+5.0%"
    assert _pct(-3.0) == "-3.0%"
    assert _pct(0.0) == "flat"
    assert _pct(None) == "n/a"


# --- collector --------------------------------------------------------------

def test_pair_to_token_normalizes_fields():
    collector = DataCollector(Config(rate_limit_delay=0))
    tok = collector._pair_to_token(_sample_pair(), "PEPE")
    assert tok["symbol"] == "PEPE"
    assert tok["volume_24h"] == 1_000_000
    assert tok["price_change_24h"] == 25.0
    assert tok["txns_24h"] == 150  # buys 100 + sells 50
    assert tok["buys_24h"] == 100
    assert tok["sells_24h"] == 50
    assert tok["liquidity"] == 500_000


def test_collect_memecoins_dedupes_and_keeps_best_pair(monkeypatch):
    config = Config(rate_limit_delay=0, watch_memecoins=["PEPE"])
    collector = DataCollector(config)

    # Two pairs for the same token, second has more liquidity
    low = _sample_pair(symbol="PEPE", addr="0xpepe", vol=100_000, liq=50_000)
    high = _sample_pair(symbol="PEPE", addr="0xpepe", vol=900_000, liq=800_000)

    monkeypatch.setattr(collector.dexscreener, "search_pairs", lambda sym: [low, high])
    monkeypatch.setattr(collector.dexscreener, "get_token_profiles", lambda: [])
    monkeypatch.setattr(collector.dexscreener, "get_token_boosts", lambda: [])

    tokens = collector.collect_memecoins()
    assert len(tokens) == 1
    assert tokens[0]["liquidity"] == 800_000  # best pair won


def test_collect_memecoins_includes_new_listings(monkeypatch):
    config = Config(rate_limit_delay=0, watch_memecoins=["PEPE"])
    collector = DataCollector(config)

    monkeypatch.setattr(collector.dexscreener, "search_pairs", lambda sym: [])
    monkeypatch.setattr(collector.dexscreener, "get_token_profiles", lambda: [{"tokenAddress": "0xnew", "chainId": "solana"}])
    monkeypatch.setattr(collector.dexscreener, "get_token_boosts", lambda: [])
    monkeypatch.setattr(
        collector.dexscreener, "get_pairs_by_token",
        lambda addr: [_sample_pair(symbol="NEW", addr=addr, chain="solana", vol=60_000)],
    )

    tokens = collector.collect_memecoins()
    assert len(tokens) == 1
    assert tokens[0]["symbol"] == "NEW"
    assert tokens[0]["source"] == "new-listing"


def test_collect_tvl_heating_filters_by_category_and_keyword():
    collector = DataCollector(Config(rate_limit_delay=0))
    protocols = [
        {"name": "four.meme", "category": "Launchpad", "chain": "Binance", "tvl": 4_000_000, "change_7d": 6.6},
        {"name": "PumpSwap", "category": "Dexs", "chain": "Solana", "tvl": 339_000_000, "change_7d": 2.0},  # keyword pump
        {"name": "PumpBTC", "category": "Bridge", "chain": "Bitcoin", "tvl": 27_000_000, "change_7d": 5.0},  # bridge -> excluded
        {"name": "Securitize Fund", "category": "RWA", "chain": "Ethereum", "tvl": 100_000_000, "change_7d": 3.0},  # rwa -> excluded
        {"name": "Aave", "category": "Lending", "chain": "Ethereum", "tvl": 9_000_000, "change_7d": 1.0},  # excluded
        {"name": "MemeDex", "category": "MemeDex", "chain": "Conflux", "tvl": 50_000, "change_7d": -3.0},
    ]
    out = collector.collect_tvl_heating(protocols)
    names = {p["name"] for p in out}
    assert names == {"four.meme", "PumpSwap", "MemeDex"}
    assert {"PumpBTC", "Securitize Fund", "Aave"} & names == set()


# --- holders ----------------------------------------------------------------

def test_get_token_top_holders_parses_success(monkeypatch):
    resp = type("R", (), {"status_code": 200, "json": lambda self: {
        "result": {"value": [
            {"address": "whale1", "amount": "1000000000", "decimals": 9},
            {"address": "whale2", "amount": "500000000", "decimals": 9},
        ]}
    }})()
    monkeypatch.setattr("tracker.holders.requests.post", lambda *a, **k: resp)

    holders, note = get_token_top_holders("mint", ["https://rpc"], limit=10)
    assert len(holders) == 2
    assert holders[0]["amount_human"] == 1.0  # 1e9 / 1e9
    assert "whale1" in holders[0]["wallet"]


def test_get_token_top_holders_rate_limited_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "tracker.holders.requests.post",
        lambda *a, **k: type("R", (), {"status_code": 429})(),
    )
    holders, note = get_token_top_holders("mint", ["https://rpc1", "https://rpc2"])
    assert holders == []
    assert "429" in note


# --- analyzer ---------------------------------------------------------------

def test_memecoin_analysis_chain_flow_and_rankings(tmp_path, monkeypatch):
    config = Config(db_path=str(tmp_path / "t.db"), rate_limit_delay=0,
                    meme_volume_floor=25_000)
    monkeypatch.setattr(
        "tracker.holders.get_token_top_holders",
        lambda *a, **k: ([], "mocked"),
    )
    tokens = [
        {"token_address": "a", "symbol": "PEPE", "name": "Pepe", "chain": "ethereum",
         "price_usd": 1, "volume_24h": 5_000_000, "price_change_24h": 10.0,
         "txns_24h": 100, "liquidity": 2_000_000, "market_cap": 1e9},
        {"token_address": "b", "symbol": "WIF", "name": "Wif", "chain": "solana",
         "price_usd": 2, "volume_24h": 8_000_000, "price_change_24h": 300.0,
         "txns_24h": 100, "liquidity": 3_000_000, "market_cap": 2e9},
        {"token_address": "c", "symbol": "DUST", "name": "Dust", "chain": "solana",
         "price_usd": 0, "volume_24h": 1_000, "price_change_24h": 5.0,
         "txns_24h": 1, "liquidity": 100, "market_cap": 1},  # below floor
    ]
    with get_db(config) as conn:
        store_memecoin_metrics(conn, tokens)

    analysis = TrendAnalyzer(config).get_memecoin_analysis(
        meme_tvl=[{"name": "PumpSwap", "category": "Dexs", "chain": "Solana",
                   "tvl": 339e6, "change_7d": 2.0}]
    )
    assert analysis["active_tokens"] == 2  # DUST excluded by floor
    assert analysis["top_volume"][0]["symbol"] == "WIF"
    assert analysis["top_surge"][0]["symbol"] == "WIF"
    flows = {r["chain"]: r for r in analysis["chain_flow"]}
    assert flows["solana"]["volume"] == 8_000_000
    assert flows["ethereum"]["volume"] == 5_000_000
    assert analysis["chain_flow"][0]["chain"] == "solana"


# --- report ----------------------------------------------------------------

def test_memecoin_report_contains_sections():
    analysis = {
        "analyzed_at": "2026-01-01T00:00:00Z",
        "active_tokens": 2,
        "summary": "test summary",
        "chain_flow": [{"chain": "solana", "volume": 8_000_000, "token_count": 1, "top_symbol": "WIF"}],
        "top_volume": [{"symbol": "PEPE", "name": "Pepe", "chain": "ethereum",
                        "volume_24h": 5_000_000, "price_change_24h": 10.0,
                        "liquidity": 2e6, "market_cap": 1e9}],
        "top_surge": [{"symbol": "WIF", "name": "Wif", "chain": "solana",
                       "volume_24h": 8_000_000, "price_change_24h": 300.0,
                       "liquidity": 3e6, "market_cap": 2e9}],
        "tvl_by_value": [{"name": "PumpSwap", "category": "Dexs", "tvl": 339e6, "change_7d": 2.0}],
        "top_holders": [],
        "holders_note": "public RPC rate-limited",
    }
    report = format_memecoin_cli_report(analysis)
    assert "WHERE MONEY IS FLOWING" in report
    assert "TOP MEMECOINS BY 24h VOLUME" in report
    assert "TOP HOLDERS" in report
    assert "PumpSwap" in report
    assert "PEPE" in report
