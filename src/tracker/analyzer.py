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
