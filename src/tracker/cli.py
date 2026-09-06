"""CLI entry point for onchain-volume-tracker."""

import argparse
import logging
import sys
from datetime import datetime

from .config import Config
from .collector import DataCollector
from .analyzer import TrendAnalyzer
from .report import format_cli_report, send_to_discord
from .db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_run(config: Config):
    """Fetch data, analyze, and report."""
    print("🔄 Collecting onchain data...")
    collector = DataCollector(config)

    # Collect data
    data = collector.collect_all()
    print(f"✅ Collected {len(data.get('chains', []))} chains, "
          f"{len(data.get('protocols', []))} protocols, "
          f"{len(data.get('dex_pairs', []))} dex pairs")

    # Store to DB
    stats = collector.store_to_db(data)
    print(f"📊 Stored: {stats['chains']} chains, {stats['protocols']} protocols, "
          f"{stats['dex_pairs']} dex pairs")

    # Analyze
    print("📈 Analyzing trends...")
    analyzer = TrendAnalyzer(config)
    analysis = analyzer.get_chain_analysis()

    # Format and print report
    report = format_cli_report(analysis)
    print(report)

    # Send to Discord if configured
    if config.webhook_url:
        print("📡 Sending to Discord...")
        success = send_to_discord(analysis, config)
        if success:
            print("✅ Report sent to Discord")
        else:
            print("❌ Failed to send to Discord")
    else:
        print("💡 Tip: Set DEFLAMA_WEBHOOK_URL to send reports to Discord")

    return analysis


def cmd_trends(config: Config):
    """Show historical trends from SQLite."""
    from .db import get_db, get_latest_chain_metrics

    with get_db(config) as conn:
        latest = get_latest_chain_metrics(conn)

    print("📊 Latest chain metrics (from database):")
    print("-" * 70)
    for chain in latest[:20]:
        name = chain.get("name", "Unknown")
        vol = chain.get("volume_24h", 0) or 0
        change = chain.get("volume_change_24h", 0) or 0
        change_str = f"{change:+.1f}%" if change else "N/A"
        tvl = chain.get("tvl", 0) or 0
        print(f"  {name:20s} | Vol: ${vol:>14,.0f} | Change: {change_str:8s} | TVL: ${tvl:>14,.0f}")
    print(f"\n  Total chains: {len(latest)}")


def cmd_chains(config: Config):
    """List all tracked chains."""
    from .db import get_db, get_latest_chain_metrics

    with get_db(config) as conn:
        latest = get_latest_chain_metrics(conn)

    print(f"📋 Tracked chains ({len(latest)} total):")
    print("-" * 70)
    for chain in sorted(latest, key=lambda x: (x.get("volume_24h") or 0), reverse=True):
        name = chain.get("name", "Unknown")
        vol = chain.get("volume_24h", 0) or 0
        tvl = chain.get("tvl", 0) or 0
        print(f"  {name:25s} | Vol: ${vol:>14,.0f} | TVL: ${tvl:>14,.0f}")


def cmd_top(config: Config):
    """Show top 10 chains by volume/growth/decline."""
    from .db import get_db, get_top_movers

    analyzer = TrendAnalyzer(config)
    analysis = analyzer.get_chain_analysis()

    # Top by volume
    print("🔥 TOP 10 BY VOLUME:")
    for i, chain in enumerate(analysis.get("top_by_volume", [])[:10], 1):
        name = chain.get("name", "Unknown")
        vol = chain.get("volume_24h", 0) or 0
        print(f"  {i:2d}. {name:20s} ${vol:,.0f}")

    print("\n🚀 TOP 10 GAINERS:")
    for i, chain in enumerate(analysis.get("top_gainers", [])[:10], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        print(f"  {i:2d}. {name:20s} {change:+.1f}%")

    print("\n📉 TOP 10 DECLINERS:")
    for i, chain in enumerate(analysis.get("top_losers", [])[:10], 1):
        name = chain.get("name", "Unknown")
        change = chain.get("volume_change_24h", 0) or 0
        print(f"  {i:2d}. {name:20s} {change:+.1f}%")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tracker",
        description="Onchain Volume Tracker — DeFi trend detection",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config file (optional)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    subparsers.add_parser("run", help="Fetch latest data, analyze, and generate report")

    # trends command
    subparsers.add_parser("trends", help="Show historical trends from SQLite")

    # chains command
    subparsers.add_parser("chains", help="List all tracked chains")

    # top command
    subparsers.add_parser("top", help="Top 10 by volume/growth/decline")

    args = parser.parse_args()

    # Load config
    config = Config.from_env()

    if args.command == "run":
        cmd_run(config)
    elif args.command == "trends":
        cmd_trends(config)
    elif args.command == "chains":
        cmd_chains(config)
    elif args.command == "top":
        cmd_top(config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
