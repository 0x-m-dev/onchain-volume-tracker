"""Report formatting for CLI output and Discord webhook."""

import json
import logging
import requests
from typing import Optional

from .config import Config
from .db import get_db, get_latest_chain_metrics, get_top_movers

logger = logging.getLogger(__name__)


def format_cli_report(analysis: dict) -> str:
    """Format analysis data as a CLI report."""
    lines = []
    lines.append("=" * 60)
    lines.append("  ONCHAIN VOLUME TRACKER")
    lines.append("=" * 60)
    lines.append(f"  Generated: {analysis['analyzed_at']}")
    lines.append(f"  Chains Tracked: {analysis['total_chains']}")
    lines.append("")

    # Summary
    if analysis.get("summary"):
        lines.append(f"  📊 {analysis['summary']}")
        lines.append("")

    # Top chains by volume
    lines.append("-" * 60)
    lines.append("  TOP 10 CHAINS BY VOLUME (24h)")
    lines.append("-" * 60)
    for i, chain in enumerate(analysis.get("top_by_volume", [])[:10], 1):
        name = chain.get("name", "Unknown")
        vol = chain.get("volume_24h", 0) or 0
        change = chain.get("volume_change_24h", 0) or 0
        change_str = f"{change:+.1f}%" if change else "N/A"
        color_code = "\033[92m" if change > 0 else "\033[91m" if change < 0 else ""
        reset_code = "\033[0m"
        lines.append(f"  {i:2d}. {name:20s} ${vol:>14,.0f}  ({color_code}{change_str}{reset_code})")
    lines.append("")

    # Top gainers
    lines.append("-" * 60)
    lines.append("  🚀 TOP GAINERS (24h)")
    lines.append("-" * 60)
    for i, chain in enumerate(analysis.get("top_gainers", [])[:10], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        vol = chain.get("volume_24h", 0) or 0
        lines.append(f"  {i:2d}. {name:20s} {change:+.1f}%  (vol: ${vol:,.0f})")
    lines.append("")

    # Top losers
    lines.append("-" * 60)
    lines.append("  📉 TOP DECLINERS (24h)")
    lines.append("-" * 60)
    for i, chain in enumerate(analysis.get("top_losers", [])[:10], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        vol = chain.get("volume_24h", 0) or 0
        lines.append(f"  {i:2d}. {name:20s} {change:+.1f}%  (vol: ${vol:,.0f})")
    lines.append("")

    # Anomalies
    anomalies = analysis.get("anomalies", [])
    if anomalies:
        lines.append("-" * 60)
        lines.append(f"  ⚠️  ANOMALIES DETECTED (>50% volume change)")
        lines.append("-" * 60)
        for i, chain in enumerate(anomalies[:5], 1):
            name = chain.get("name", "Unknown")
            change = chain.get("volume_change_24h", 0) or 0
            vol = chain.get("volume_24h", 0) or 0
            direction = "📈 SURGE" if change > 0 else "📉 DROP"
            lines.append(f"  {i:2d}. {name:20s} {direction} {change:+.1f}%  (vol: ${vol:,.0f})")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_markdown_report(analysis: dict) -> str:
    """Format analysis data as markdown for Discord."""
    lines = []
    lines.append("## 📊 Onchain Volume Tracker Report")
    lines.append(f"*Generated: {analysis['analyzed_at']}*")
    lines.append(f"*Chains tracked: {analysis['total_chains']}*")
    lines.append("")

    # Summary
    if analysis.get("summary"):
        lines.append(f"**Summary:** {analysis['summary']}")
        lines.append("")

    # Top chains by volume
    lines.append("### 🔥 Top 10 Chains by Volume (24h)")
    lines.append("")
    lines.append("| Rank | Chain | Volume (24h) | Change |")
    lines.append("|------|-------|--------------|--------|")
    for i, chain in enumerate(analysis.get("top_by_volume", [])[:10], 1):
        name = chain.get("name", "Unknown")
        vol = chain.get("volume_24h", 0) or 0
        change = chain.get("volume_change_24h", 0) or 0
        change_str = f"{change:+.1f}%" if change else "N/A"
        emoji = "🟢" if change > 0 else "🔴" if change < 0 else ""
        lines.append(f"| {i} | {emoji} {name} | ${vol:,.0f} | {change_str} |")
    lines.append("")

    # Top gainers
    lines.append("### 🚀 Top Gainers (24h)")
    lines.append("")
    for i, chain in enumerate(analysis.get("top_gainers", [])[:5], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        vol = chain.get("volume_24h", 0) or 0
        lines.append(f"- **{name}**: {change:+.1f}% (volume: ${vol:,.0f})")
    lines.append("")

    # Top losers
    lines.append("### 📉 Top Decliners (24h)")
    lines.append("")
    for i, chain in enumerate(analysis.get("top_losers", [])[:5], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        vol = chain.get("volume_24h", 0) or 0
        lines.append(f"- **{name}**: {change:+.1f}% (volume: ${vol:,.0f})")
    lines.append("")

    # Anomalies
    anomalies = analysis.get("anomalies", [])
    if anomalies:
        lines.append("### ⚠️ Anomalies Detected")
        lines.append("")
        for chain in anomalies[:5]:
            name = chain.get("name", "Unknown")
            change = chain.get("volume_change_24h", 0) or 0
            vol = chain.get("volume_24h", 0) or 0
            direction = "📈 SURGE" if change > 0 else "📉 DROP"
            lines.append(f"- **{name}**: {direction} {change:+.1f}% (volume: ${vol:,.0f})")
        lines.append("")

    return "\n".join(lines)


def send_discord_report(content: str, webhook_url: Optional[str] = None) -> bool:
    """Send report to Discord webhook."""
    if not webhook_url:
        logger.warning("No webhook URL configured")
        return False

    # Discord messages have a 2000 character limit, so we need to split
    max_length = 1800
    if len(content) <= max_length:
        return _send_webhook_message(content, webhook_url)

    # Split into chunks
    chunks = [content[i:i + max_length] for i in range(0, len(content), max_length)]
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"{chunk}\n\n--- *(continued...)*"
        _send_webhook_message(chunk, webhook_url)
        logger.info(f"Sent Discord message {i + 1}/{len(chunks)}")

    return True


def _send_webhook_message(content: str, webhook_url: str) -> bool:
    """Send a single message to Discord webhook."""
    try:
        payload = {
            "content": content,
            "username": "Volume Tracker",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2619/2619204.png",
        }
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code == 204:
            logger.info("Discord webhook sent successfully")
            return True
        else:
            logger.error(f"Discord webhook error: {resp.status_code} - {resp.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"Failed to send Discord webhook: {e}")
        return False


def send_to_discord(analysis: dict, config: Optional[Config] = None) -> bool:
    """Send formatted report to Discord."""
    if config is None:
        config = Config.from_env()

    if not config.webhook_url:
        logger.warning("No Discord webhook URL configured (set DEFLAMA_WEBHOOK_URL)")
        return False

    markdown = format_markdown_report(analysis)
    return send_discord_report(markdown, config.webhook_url)
