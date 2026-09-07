# Onchain Volume Tracker

Python CLI that pulls free DeFiLlama and DexScreener data, stores history in
SQLite, and prints trend reports — with a dedicated **memecoin activity**
tracker for where retail money is flowing.

Public repo: `0x-m-dev/onchain-volume-tracker`

## Highlights

- **Chain / protocol trends** from DeFiLlama: top chains by volume, top
  gainers/decliners, anomalies.
- **Memecoin activity** (`tracker memes`): top memecoins by 24h volume, hottest
  24h gainers, where memecoin volume is concentrating by chain, memecoin
  infrastructure TVL (launchpads / meme protocols), and best-effort top-holder
  "whale wallets" on Solana.
- **FOMO retail-surge watch:** tokens currently in an active retail-FOMO phase
  (sharp volume + price move + heavy buy pressure) on the chains retail apps
  support. FOMO (fomo.family) is non-custodial, so its traders' money moves
  real tokens that surface here as on-chain surges. FOMO publishes no public
  API, so this is the on-chain signature of its activity.
- **Trader wallet tracking** (`tracker wallet <addr>`): follow specific FOMO
  trader wallets on-chain — pull their recent signatures and decode buy/sell
  per token via Solana RPC (free; a free Helius key is the reliable path since
  public no-key RPCs block datacenter IPs). Watchlist via `TRACKER_WALLETS`.

## Run / verify

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make test
tracker run          # full chain + memecoin report
tracker memes        # memecoin-only report
```

`tracker run` writes `tracker.db` (gitignored). Commands:
`tracker run`, `tracker memes`, `tracker trends`, `tracker chains`, `tracker top`.

## Memecoin module

- **Sources (free, no keys):** DexScreener search + token-profiles/token-boosts
  (new listings & attention signals), DeFiLlama `/protocols` for launchpad /
  meme-category TVL.
- **Top holders / wallets:** free tier uses Solana's public RPC
  `getTokenLargestAccounts` against a small pool of public endpoints. Public
  RPCs are often rate-limited (HTTP 429), so this is best-effort and degrades
  gracefully. EVM-chain holder enumeration requires a paid provider
  (Moralis/Alchemy/Dune) and is intentionally out of scope.
- **Config:** the memecoin watchlist, category set, volume floor, holder count,
  and Solana RPC pool are all overridable via env (see `.env.example`).

## Preview

https://0x-m-dev.github.io/onchain-volume-tracker/

## Notes

- No API keys required for v1.
- Do not commit `.env`, `tracker.db`, or Discord identifiers.
- launchd plist in `launchd/` is a template; it is not loaded.
