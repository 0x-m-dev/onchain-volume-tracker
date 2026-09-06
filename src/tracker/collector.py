"""Data collection from DeFiLlama and DexScreener APIs."""

import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from .config import Config
from .db import (
    store_chain_metrics, store_protocols, store_dex_pairs, get_db,
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

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.base_url = config.dexscreener_base
        self.rate_limit_delay = config.rate_limit_delay

    def _fetch(self, endpoint: str) -> Optional[dict]:
        """Fetch data from DexScreener API."""
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

        return result

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

        return stats
