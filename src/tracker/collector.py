"""Data collection from DeFiLlama and DexScreener APIs."""

import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from .config import Config
from .db import (
    store_chain_metrics, store_protocols, store_dex_pairs,
    store_memecoin_metrics, get_db,
)

logger = logging.getLogger(__name__)


class DeFiLlamaClient:
    """Client for DeFiLlama API."""

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.base_url = config.defilama_base
        self.rate_limit_delay = config.rate_limit_delay

    def _fetch(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Fetch data from DeFiLlama API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching {url}")
            resp = self.session.get(url, timeout=self.config.request_timeout, params=params)
            resp.raise_for_status()
            time.sleep(self.rate_limit_delay)  # Be respectful
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def get_chain_data(self) -> list[dict]:
        """Get all chains with TVL and volume data."""
        data = self._fetch("v2/chains")
        if isinstance(data, list):
            return [
                {
                    "slug": str(item.get("name", "")).strip().lower().replace(" ", "-"),
                    **item,
                }
                for item in data
                if isinstance(item, dict) and item.get("name")
            ]
        if isinstance(data, dict):
            # API returns dict keyed by chain slug
            return [
                {"slug": slug, "name": info.get("name", slug), **info}
                for slug, info in data.items()
                if isinstance(info, dict)
            ]
        return []

    def get_chain_dex_volume(self, chain: str) -> dict:
        """Get current DEX volume metrics for one chain."""
        data = self._fetch(f"overview/dexs/{quote(chain, safe='')}")
        return data if isinstance(data, dict) else {}

    def get_dex_volume(self) -> dict:
        """Get DEX volume overview."""
        data = self._fetch("overview/dexs")
        if isinstance(data, dict):
            return data
        return {}

    def get_fees_data(self) -> dict:
        """Get fees/revenue data."""
        data = self._fetch("overview/fees")
        if isinstance(data, dict):
            return data
        return {}

    def get_protocols(self) -> list[dict]:
        """Get all protocols."""
        data = self._fetch("protocols")
        if isinstance(data, list):
            return [
                {
                    "pid": p.get("pid"),
                    "name": p.get("name", ""),
                    "slug": p.get("slug", ""),
                    "category": p.get("category", ""),
                    "chains": p.get("chain", ""),
                    "tvl": p.get("tvl"),
                    "volume_24h": p.get("volume_24h"),
                    "volumeChangeOver24h": p.get("volumeChangeOver24h"),
                }
                for p in data
            ]
        return []

    def get_chain_tvl_history(self, chain: str, days: int = 30) -> Optional[dict]:
        """Get historical TVL for a chain."""
        return self._fetch(f"historicalChainTvl/{chain}")


class DexScreenerClient:
    """Client for DexScreener API."""

    # Profiles/boosts live at the API root, NOT under /latest/dex/
    ROOT_URL = "https://api.dexscreener.com"

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.base_url = config.dexscreener_base
        self.rate_limit_delay = config.rate_limit_delay

    def _fetch(self, endpoint: str) -> Optional[dict]:
        """Fetch data from DexScreener API (under /latest/dex/)."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching {url}")
            resp = self.session.get(url, timeout=self.config.request_timeout)
            resp.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _fetch_root(self, endpoint: str) -> Optional[dict]:
        """Fetch from the DexScreener API root (token-profiles, token-boosts)."""
        url = f"{self.ROOT_URL}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching {url}")
            resp = self.session.get(url, timeout=self.config.request_timeout)
            resp.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def search_pairs(self, token: str) -> list[dict]:
        """Search for pairs by token symbol."""
        data = self._fetch(f"search?q={token}")
        if isinstance(data, dict) and isinstance(data.get("pairs"), list):
            return data["pairs"]
        return []

    def get_top_pairs(self, token: str) -> list[dict]:
        """Get top trading pairs for a token."""
        return self.search_pairs(token)

    def get_pairs_by_token(self, address: str) -> list[dict]:
        """Get all pairs for a token address."""
        data = self._fetch(f"tokens/{address}")
        if isinstance(data, dict) and isinstance(data.get("pairs"), list):
            return data["pairs"]
        return []

    def get_token_profiles(self) -> list[dict]:
        """Get latest token profiles (new listings / trending submissions)."""
        data = self._fetch_root("token-profiles/latest/v1")
        if isinstance(data, list):
            return data
        return []

    def get_token_boosts(self) -> list[dict]:
        """Get latest boosted tokens (paid promo, attention signal)."""
        data = self._fetch_root("token-boosts/latest/v1")
        if isinstance(data, list):
            return data
        return []


class DataCollector:
    """Orchestrates data collection from all sources."""

    def __init__(self, config: Config):
        self.config = config
        self.defilama = DeFiLlamaClient(config)
        self.dexscreener = DexScreenerClient(config)

    def collect_all(self) -> dict:
        """Collect data from all sources. Returns aggregated data."""
        result = {
            "chains": [],
            "protocols": [],
            "dex_pairs": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 1. Collect chain data from DeFiLlama
        logger.info("Collecting chain data from DeFiLlama...")
        chain_data = self.defilama.get_chain_data()
        configured = {name.casefold() for name in self.config.default_chains}
        if configured:
            volume_targets = [
                chain for chain in chain_data
                if str(chain.get("name", "")).casefold() in configured
            ]
        else:
            volume_targets = sorted(
                chain_data,
                key=lambda chain: float(chain.get("tvl") or 0),
                reverse=True,
            )[:20]
        for chain in volume_targets:
            volume = self.defilama.get_chain_dex_volume(str(chain["name"]))
            chain.update(
                volume_24h=volume.get("total24h"),
                volume_7d=volume.get("total7d"),
                volumeChangeOver24h=volume.get("change_1d"),
                volumeChangeOver7d=volume.get("change_7d"),
            )
        result["chains"] = chain_data

        # 2. Collect DEX volume data
        logger.info("Collecting DEX volume data...")
        dex_volume = self.defilama.get_dex_volume()
        result["dex_volume"] = dex_volume

        # 3. Collect fees data
        logger.info("Collecting fees data...")
        fees_data = self.defilama.get_fees_data()
        result["fees"] = fees_data

        # 4. Collect protocols
        logger.info("Collecting protocols...")
        protocols = self.defilama.get_protocols()
        result["protocols"] = protocols

        # 5. Collect DEX pairs from DexScreener
        logger.info("Collecting DEX pair data from DexScreener...")
        all_pairs = []
        for token in self.config.watch_tokens[:10]:  # Limit to avoid too many requests
            pairs = self.dexscreener.get_top_pairs(token)
            if pairs:
                all_pairs.extend(pairs[:5])  # Top 5 pairs per token
            if len(all_pairs) >= 50:
                break
        result["dex_pairs"] = all_pairs

        # 6. Collect memecoin activity heat
        logger.info("Collecting memecoin activity heat...")
        result["memecoins"] = self.collect_memecoins()

        # 7. Collect memecoin infrastructure TVL (launchpads / meme protocols)
        logger.info("Collecting memecoin infrastructure TVL...")
        result["meme_tvl"] = self.collect_tvl_heating(protocols)

        return result

    @staticmethod
    def _pair_to_token(pair: dict, fallback_symbol: str = "") -> dict:
        """Normalize a DexScreener pair into a compact token-metrics dict."""
        bt = pair.get("baseToken") or {}
        vol = pair.get("volume") or {}
        chg = pair.get("priceChange") or {}
        liq = pair.get("liquidity") or {}
        txn = pair.get("txns") or {}
        h24 = txn.get("h24") or {}
        buys = h24.get("buys", 0) or 0
        sells = h24.get("sells", 0) or 0
        total_txns = buys + sells
        buy_ratio = (buys / total_txns) if total_txns else None
        return {
            "token_address": bt.get("address"),
            "symbol": (bt.get("symbol") or fallback_symbol or "").upper(),
            "name": bt.get("name", ""),
            "chain": pair.get("chainId", ""),
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "volume_24h": float(vol.get("h24", 0) or 0),
            "price_change_24h": float(chg.get("h24", 0) or 0),
            "txns_24h": int(total_txns),
            "buys_24h": int(buys),
            "sells_24h": int(sells),
            "buy_ratio": round(buy_ratio, 3) if buy_ratio is not None else None,
            "liquidity": float(liq.get("usd", 0) or 0),
            "market_cap": float(pair.get("marketCap", 0) or 0),
            "pair_address": pair.get("pairAddress", ""),
            "dex": pair.get("dexId", ""),
            "url": pair.get("url", ""),
        }

    def collect_memecoins(self) -> list[dict]:
        """Collect memecoin activity: canonical watchlist tokens + new listings.

        Returns a list of per-token metric dicts (best pair per token).
        """
        best: dict = {}

        def absorb(pair, fallback_symbol):
            tok = self._pair_to_token(pair, fallback_symbol)
            addr = tok["token_address"]
            if not addr:
                return
            # Keep the strongest pair for a given token (liquidity, then volume)
            strength = (tok["liquidity"], tok["volume_24h"])
            if addr not in best or strength > best[addr][1]:
                best[addr] = (tok, strength)

        # 1. Canonical per-token metrics from watchlist symbol searches
        for symbol in self.config.watch_memecoins:
            pairs = self.dexscreener.search_pairs(symbol)
            for p in pairs:
                bt = p.get("baseToken") or {}
                if (bt.get("symbol") or "").upper() != symbol.upper():
                    continue
                absorb(p, symbol)

        # 2. New-listings / boosted attention signals (bounded, best pair each)
        attention = []
        attention.extend(self.dexscreener.get_token_profiles() or [])
        attention.extend(self.dexscreener.get_token_boosts() or [])
        for prof in attention[:10]:
            addr = prof.get("tokenAddress")
            chain = prof.get("chainId")
            if not addr or addr in best:
                continue
            pairs = self.dexscreener.get_pairs_by_token(addr)
            if not pairs:
                continue
            top = max(pairs, key=lambda p: float((p.get("volume") or {}).get("h24", 0) or 0))
            tok = self._pair_to_token(top, (top.get("baseToken") or {}).get("symbol", ""))
            if tok["token_address"] and tok["symbol"]:
                tok["source"] = "new-listing"
                best[tok["token_address"]] = (tok, (tok["liquidity"], tok["volume_24h"]))

        tokens = [v[0] for v in best.values()]
        tokens.sort(key=lambda t: t["volume_24h"], reverse=True)
        return tokens

    def collect_tvl_heating(self, protocols: Optional[list[dict]] = None) -> list[dict]:
        """Find memecoin-infrastructure protocols (launchpads / meme) heating up in TVL."""
        if protocols is None:
            protocols = self.defilama.get_protocols()
        cats = {c.casefold() for c in self.config.meme_categories}
        # Keyword hits must exclude infra bridges / RWA funds that merely share a
        # substring (e.g. "PumpBTC" bridge, RWA "Funds").
        keywords = ("pump", "meme", "four.meme")
        excluded_cats = {"bridge", "rwa"}
        out = []
        for p in protocols:
            cat = (p.get("category") or "").casefold()
            name = (p.get("name") or "").lower()
            if cat in cats:
                pass
            elif any(k in name for k in keywords) and cat not in excluded_cats:
                pass
            else:
                continue
            out.append({
                "name": p.get("name", ""),
                "category": p.get("category", ""),
                "chain": p.get("chain", ""),
                "tvl": p.get("tvl"),
                "change_1d": p.get("change_1d"),
                "change_7d": p.get("change_7d"),
                "mcap": p.get("mcap"),
            })
        return out

    def store_to_db(self, data: dict) -> dict:
        """Store collected data to SQLite."""
        stats = {"chains": 0, "protocols": 0, "dex_pairs": 0}

        with get_db(self.config) as conn:
            # Store chain metrics
            for chain in data.get("chains", []):
                try:
                    store_chain_metrics(conn, chain["slug"], chain.get("name", chain["slug"]), chain)
                    stats["chains"] += 1
                except Exception as e:
                    logger.warning(f"Error storing chain {chain.get('slug')}: {e}")

            # Store protocols
            protocols = data.get("protocols", [])
            if protocols:
                try:
                    store_protocols(conn, protocols)
                    stats["protocols"] = len(protocols)
                except Exception as e:
                    logger.warning(f"Error storing protocols: {e}")

            # Store DEX pairs
            pairs = data.get("dex_pairs", [])
            if pairs:
                try:
                    store_dex_pairs(conn, pairs)
                    stats["dex_pairs"] = len(pairs)
                except Exception as e:
                    logger.warning(f"Error storing DEX pairs: {e}")

            # Store memecoin activity snapshots
            memecoins = data.get("memecoins", [])
            if memecoins:
                try:
                    store_memecoin_metrics(conn, memecoins)
                    stats["memecoins"] = len(memecoins)
                except Exception as e:
                    logger.warning(f"Error storing memecoin metrics: {e}")

        return stats
