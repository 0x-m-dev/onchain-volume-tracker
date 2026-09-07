"""Trend analysis engine for onchain volume data."""

import logging
from typing import Optional
from datetime import datetime

from .config import Config
from .db import get_db, get_top_movers, get_anomalies, get_latest_chain_metrics

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyzes chain and protocol trends from stored data."""

    def __init__(self, config: Config):
        self.config = config
        self.top_n = config.top_n
        self.anomaly_threshold = config.anomaly_threshold

    def get_chain_analysis(self) -> dict:
        """Get full chain analysis report."""
        with get_db(self.config) as conn:
            latest = get_latest_chain_metrics(conn)
            top_by_volume = get_top_movers(conn, self.top_n, "volume_24h")
            top_by_growth = get_top_movers(conn, self.top_n, "volume_change_24h")
            top_by_decline = get_top_movers(
                conn, self.top_n, "volume_change_24h", descending=False
            )
            anomalies = get_anomalies(conn, self.anomaly_threshold)

        # Separate growth and decline
        positive = [row for row in top_by_growth if row["volume_change_24h"] > 0]
        negative = [row for row in top_by_decline if row["volume_change_24h"] < 0]

        return {
            "analyzed_at": datetime.utcnow().isoformat(),
            "total_chains": len(latest),
            "top_by_volume": latest[:self.top_n],
            "top_gainers": positive,
            "top_losers": negative,
            "anomalies": anomalies,
            "summary": self._generate_summary(latest, positive, negative, anomalies),
        }

    def get_category_analysis(self) -> dict:
        """Analyze trends by category (from protocol data)."""
        # This would require cross-referencing chain data with protocol categories
        # For now, return a placeholder that can be expanded
        return {
            "categories": [],
            "message": "Category analysis requires protocol-level volume aggregation",
        }

    def get_memecoin_analysis(self, meme_tvl: list[dict] | None = None) -> dict:
        """Build the memecoin activity report from the latest DB snapshot.

        Sections: top memecoins by volume, 24h price surge, where retail money
        is concentrating (volume by chain), and TVL heating in memecoin
        infrastructure (launchpads / meme protocols).
        """
        from .db import get_db, get_latest_memecoins
        from .holders import get_token_top_holders

        with get_db(self.config) as conn:
            tokens = get_latest_memecoins(conn)

        floor = self.config.meme_volume_floor

        # Top by 24h volume (exclude dust)
        real = [t for t in tokens if (t.get("volume_24h") or 0) >= floor]
        top_volume = sorted(real, key=lambda t: t["volume_24h"], reverse=True)[:self.top_n]

        # Top 24h price surge among tokens with real activity + sane liquidity
        surge = [
            t for t in real
            if (t.get("liquidity") or 0) >= (floor * 0.5)
            and 0 < (t.get("price_change_24h") or 0) <= 2000
        ]
        top_surge = sorted(surge, key=lambda t: t["price_change_24h"], reverse=True)[:self.top_n]

        # Where money flows: memecoin 24h volume aggregated by chain
        chain_flow: dict[str, dict] = {}
        for t in real:
            chain = t.get("chain") or "unknown"
            entry = chain_flow.setdefault(chain, {"volume": 0.0, "tokens": set(), "top": None})
            entry["volume"] += t.get("volume_24h") or 0
            entry["tokens"].add(t.get("symbol"))
            if entry["top"] is None or (t.get("volume_24h") or 0) > entry["top"][1]:
                entry["top"] = (t.get("symbol"), t.get("volume_24h") or 0)
        chain_flow_rows = [
            {
                "chain": c,
                "volume": v["volume"],
                "token_count": len(v["tokens"]),
                "top_symbol": v["top"][0] if v["top"] else None,
            }
            for c, v in chain_flow.items()
        ]
        chain_flow_rows.sort(key=lambda r: r["volume"], reverse=True)

        # TVL heating in memecoin infrastructure
        meme_tvl = meme_tvl or []
        tvl_ranked = sorted(
            meme_tvl, key=lambda p: (p.get("change_7d") or 0), reverse=True
        )
        tvl_by_value = sorted(
            meme_tvl, key=lambda p: (p.get("tvl") or 0), reverse=True
        )
        # Top wallets: best-effort for the biggest Solana memecoin
        top_holders = []
        holders_note = None
        solana_top = next(
            (t for t in top_volume if (t.get("chain") or "").casefold() == "solana"),
            None,
        )
        if solana_top and solana_top.get("token_address"):
            top_holders, holders_note = get_token_top_holders(
                solana_top["token_address"],
                self.config.solana_rpcs,
                limit=self.config.top_holders_limit,
                timeout=8,
            )

        summary = (
            f"**{len(real)} memecoins** with 24h volume over ${floor:,.0f}; "
            f"top chain **{chain_flow_rows[0]['chain'] if chain_flow_rows else 'n/a'}** "
            f"(~${(chain_flow_rows[0]['volume'] if chain_flow_rows else 0):,.0f} memecoin vol)"
        )

        return {
            "analyzed_at": datetime.utcnow().isoformat(),
            "total_tokens": len(tokens),
            "active_tokens": len(real),
            "top_volume": top_volume,
            "top_surge": top_surge,
            "chain_flow": chain_flow_rows,
            "tvl_heating": tvl_ranked[:self.top_n],
            "tvl_by_value": tvl_by_value[:self.top_n],
            "top_holders": top_holders,
            "holders_token": solana_top,
            "holders_note": holders_note,
            "summary": summary,
        }

    def _generate_summary(self, latest, gainers, losers, anomalies) -> str:
        """Generate a human-readable summary."""
        total_volume = sum(c.get("volume_24h", 0) or 0 for c in latest)
        chains_with_data = len([c for c in latest if c.get("volume_24h")])

        parts = [
            f"**{chains_with_data} chains** tracked with total 24h volume of **${total_volume:,.0f}**",
        ]

        if gainers:
            top_gainer = gainers[0]
            parts.append(
                f"🚀 Top gainer: **{top_gainer.get('name', 'Unknown')}** "
                f"({top_gainer['volume_change_24h']:+.1f}%)"
            )

        if losers:
            top_loser = losers[0]
            parts.append(
                f"📉 Top loser: **{top_loser.get('name', 'Unknown')}** "
                f"({top_loser['volume_change_24h']:+.1f}%)"
            )

        if anomalies:
            parts.append(
                f"⚠️ **{len(anomalies)} anomaly/anomalies** detected "
                f"(>={self.anomaly_threshold}% volume change)"
            )

        return " | ".join(parts)
