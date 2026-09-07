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


def _money_fmt(value) -> str:
    """Compact USD formatting: 1.2M / 340K / 900."""
    if value is None:
        return "n/a"
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return "n/a"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    if v >= 1e3:
        return f"${v/1e3:.1f}K"
    return f"${v:.0f}"


def _pct(value, signed: bool = True) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return "n/a"
    if abs(v) < 0.05:
        return "flat"
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def format_memecoin_cli_report(analysis: dict) -> str:
    """Format the memecoin activity analysis as a CLI report."""
    lines = []
    lines.append("=" * 60)
    lines.append("  🐸 MEMECOIN ACTIVITY")
    lines.append("=" * 60)
    lines.append(f"  Generated: {analysis['analyzed_at']}")
    lines.append(f"  Active tokens (24h vol > $25k): {analysis['active_tokens']}")
    if analysis.get("summary"):
        lines.append(f"  📊 {analysis['summary']}")
    lines.append("")

    # Where money is flowing
    lines.append("-" * 60)
    lines.append("  💰 WHERE MONEY IS FLOWING (memecoin vol by chain)")
    lines.append("-" * 60)
    for i, row in enumerate(analysis.get("chain_flow", [])[:8], 1):
        top = f"  (top: {row['top_symbol']})" if row.get("top_symbol") else ""
        lines.append(
            f"  {i:2d}. {row['chain']:14s} {_money_fmt(row['volume']):>9s}  "
            f"{row['token_count']} tokens {top}"
        )
    lines.append("")

    # Top by volume
    lines.append("-" * 60)
    lines.append("  🔥 TOP MEMECOINS BY 24h VOLUME")
    lines.append("-" * 60)
    for i, t in enumerate(analysis.get("top_volume", [])[:10], 1):
        src = " 🆕" if t.get("source") == "new-listing" else ""
        lines.append(
            f"  {i:2d}. {t.get('symbol','?'):8s} {t.get('chain',''):10s} "
            f"{_money_fmt(t.get('volume_24h')):>9s}  {_pct(t.get('price_change_24h'))}"
            f"  mc {_money_fmt(t.get('market_cap'))}{src}"
        )
    lines.append("")

    # Top surge
    lines.append("-" * 60)
    lines.append("  🚀 HOTTEST GAINERS (24h price)")
    lines.append("-" * 60)
    for i, t in enumerate(analysis.get("top_surge", [])[:10], 1):
        lines.append(
            f"  {i:2d}. {t.get('symbol','?'):8s} {t.get('chain',''):10s} "
            f"{_pct(t.get('price_change_24h')):>9s}  vol {_money_fmt(t.get('volume_24h'))}"
        )
    lines.append("")

    # TVL in memecoin infrastructure
    lines.append("-" * 60)
    lines.append("  🏗️  MEMECOIN INFRA TVL (launchpads / meme protocols)")
    lines.append("-" * 60)
    for i, p in enumerate(analysis.get("tvl_by_value", [])[:8], 1):
        lines.append(
            f"  {i:2d}. {p.get('name','?'):20s} {_money_fmt(p.get('tvl')):>9s} "
            f"7d {_pct(p.get('change_7d'))}  ({p.get('category','')})"
        )
    lines.append("")

    # Top holders / wallets
    holders = analysis.get("top_holders", [])
    lines.append("-" * 60)
    if holders:
        sym = (analysis.get("holders_token") or {}).get("symbol", "?")
        lines.append(f"  👛 TOP HOLDERS — ${sym} on Solana")
        lines.append("-" * 60)
        for i, h in enumerate(holders[:10], 1):
            lines.append(
                f"  {i:2d}. {h.get('wallet','')[:22]}…  "
                f"{h.get('amount_human', 0):,.0f}"
            )
        lines.append("")
    else:
        lines.append("  👛 TOP HOLDERS: unavailable")
        lines.append(f"     {analysis.get('holders_note') or 'no data'}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_memecoin_markdown_report(analysis: dict) -> str:
    """Format the memecoin activity analysis as markdown for Discord."""
    lines = []
    lines.append("## 🐸 Memecoin Activity")
    lines.append(f"*Generated: {analysis['analyzed_at']}*")
    lines.append(f"*Active tokens (24h vol > $25k): {analysis['active_tokens']}*")
    if analysis.get("summary"):
        lines.append(f"**Summary:** {analysis['summary']}")
    lines.append("")

    lines.append("### 💰 Where money is flowing")
    lines.append("")
    for row in analysis.get("chain_flow", [])[:8]:
        top = f" — top {row['top_symbol']}" if row.get("top_symbol") else ""
        lines.append(f"- **{row['chain']}**: {_money_fmt(row['volume'])} ({row['token_count']} tokens){top}")
    lines.append("")

    lines.append("### 🔥 Top memecoins by 24h volume")
    lines.append("")
    for t in analysis.get("top_volume", [])[:10]:
        src = " 🆕new" if t.get("source") == "new-listing" else ""
        lines.append(
            f"- **{t.get('symbol','?')}** ({t.get('chain','')}): {_money_fmt(t.get('volume_24h'))}"
            f" vol, {_pct(t.get('price_change_24h'))} 24h, mc {_money_fmt(t.get('market_cap'))}{src}"
        )
    lines.append("")

    lines.append("### 🚀 Hottest gainers (24h)")
    lines.append("")
    for t in analysis.get("top_surge", [])[:10]:
        lines.append(
            f"- **{t.get('symbol','?')}** ({t.get('chain','')}): {_pct(t.get('price_change_24h'))}"
            f" 24h, vol {_money_fmt(t.get('volume_24h'))}"
        )
    lines.append("")

    lines.append("### 🏗️ Memecoin infra TVL (by TVL)")
    lines.append("")
    for p in analysis.get("tvl_by_value", [])[:8]:
        lines.append(
            f"- **{p.get('name','?')}** ({p.get('category','')}): "
            f"{_money_fmt(p.get('tvl'))} TVL, {_pct(p.get('change_7d'))} 7d"
        )
    lines.append("")

    holders = analysis.get("top_holders", [])
    lines.append("### 👛 Top holders")
    lines.append("")
    if holders:
        sym = (analysis.get("holders_token") or {}).get("symbol", "?")
        lines.append(f"**${sym}** on Solana:")
        for h in holders[:10]:
            lines.append(f"- `{h.get('wallet','')}` — {h.get('amount_human',0):,.0f}")
    else:
        lines.append(f"Unavailable — {analysis.get('holders_note') or 'no data'}")
    lines.append("")

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
