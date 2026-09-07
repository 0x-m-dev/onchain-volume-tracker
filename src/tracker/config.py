"""Configuration for onchain-volume-tracker."""

import os
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"), "side-work", "projects", "onchain-volume-tracker", "tracker.db"
)


@dataclass(frozen=True)
class Config:
    """Application configuration from environment variables."""

    # Discord webhook URL for sending reports
    webhook_url: Optional[str] = field(default_factory=lambda: os.getenv("DEFLAMA_WEBHOOK_URL"))

    # API base URLs
    defilama_base: str = field(default="https://api.llama.fi")
    dexscreener_base: str = field(default="https://api.dexscreener.com/latest/dex")

    # SQLite database path
    db_path: str = field(default_factory=lambda: DEFAULT_DB_PATH)

    # Default chains to track (empty = all from DeFiLlama)
    default_chains: list[str] = field(default_factory=list)

    # Check interval in hours
    check_interval: int = field(default=6)

    # Top N results
    top_n: int = field(default=10)

    # Anomaly threshold (%)
    anomaly_threshold: float = field(default=50.0)

    # Request timeout in seconds
    request_timeout: int = field(default=30)

    # Rate limit delay between requests (seconds)
    rate_limit_delay: float = field(default=0.5)

    # DexScreener top tokens to watch (if no search results)
    watch_tokens: list[str] = field(default_factory=lambda: [
        "USDT", "USDC", "WETH", "BTC", "SOL", "ARB", "OP", "AAVE",
        "LINK", "UNI", "PEPE", "WIF", "DOGE", "SHIB", "TON",
        "NEAR", "AVAX", "MATIC", "SUI", "APT", "SEI", "TIA",
    ])

    # Memecoin symbols tracked for onchain activity heat
    watch_memecoins: list[str] = field(default_factory=lambda: [
        "PEPE", "WIF", "BONK", "DOGE", "SHIB", "FLOKI", "PENGU", "POPCAT",
        "BRETT", "MOG", "TURBO", "MEW", "WEN", "MAGA", "MOODENG", "GOAT",
        "PNUT", "NEIRO", "SPX6900", "MICHI", "FARTCOIN", "SAMO", "MYRO",
        "TRUMP", "KISHU", "ANDY", "BILLY", "GIGA",
    ])

    # DeFiLlama categories that capture memecoin infrastructure (launchpads, meme protocols)
    meme_categories: list[str] = field(default_factory=lambda: ["Launchpad", "Meme", "MemeDex"])

    # How many top token holders to resolve for the "top wallets" section
    top_holders_limit: int = field(default=10)

    # Public Solana RPC endpoints used for top-holder lookups (free, best-effort)
    solana_rpcs: list[str] = field(default_factory=lambda: [
        "https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
        "https://solana.drpc.org",
    ])

    # Floor (USD) on 24h volume/liquidity before a memecoin counts as "real" activity
    meme_volume_floor: float = field(default=25000.0)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment."""
        webhook_id = os.getenv("DEFLAMA_WEBHOOK_ID")
        webhook_token = os.getenv("DEFLAMA_WEBHOOK_TOKEN")

        webhook_url = None
        if webhook_id and webhook_token:
            webhook_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"

        return cls(
            webhook_url=webhook_url or os.getenv("DEFLAMA_WEBHOOK_URL"),
            db_path=os.getenv("TRACKER_DB_PATH", DEFAULT_DB_PATH),
            check_interval=int(os.getenv("TRACKER_CHECK_INTERVAL", "6")),
            top_n=int(os.getenv("TRACKER_TOP_N", "10")),
            anomaly_threshold=float(os.getenv("TRACKER_ANOMALY_THRESHOLD", "50")),
            request_timeout=int(os.getenv("TRACKER_REQUEST_TIMEOUT", "30")),
            rate_limit_delay=float(os.getenv("TRACKER_RATE_LIMIT_DELAY", "0.5")),
            watch_tokens=os.getenv("TRACKER_WATCH_TOKENS", "USDT,USDC,WETH,BTC,SOL,ARB,OP,AAVE,LINK,UNI,PEPE,WIF,DOGE,SHIB,TON,NEAR,AVAX,MATIC,SUI,APT,SEI,TIA").split(","),
            watch_memecoins=os.getenv(
                "TRACKER_MEMECOINS",
                "PEPE,WIF,BONK,DOGE,SHIB,FLOKI,PENGU,POPCAT,BRETT,MOG,TURBO,MEW,WEN,MAGA,MOODENG,GOAT,PNUT,NEIRO,SPX6900,MICHI,FARTCOIN,SAMO,MYRO,TRUMP,KISHU,ANDY,BILLY,GIGA",
            ).split(","),
            meme_categories=os.getenv(
                "TRACKER_MEME_CATEGORIES", "Launchpad,Meme,MemeDex"
            ).split(","),
            top_holders_limit=int(os.getenv("TRACKER_TOP_HOLDERS", "10")),
            solana_rpcs=os.getenv(
                "TRACKER_SOLANA_RPCS",
                "https://api.mainnet-beta.solana.com,https://solana-rpc.publicnode.com,https://solana.drpc.org",
            ).split(","),
            meme_volume_floor=float(os.getenv("TRACKER_MEME_VOLUME_FLOOR", "25000")),
        )
