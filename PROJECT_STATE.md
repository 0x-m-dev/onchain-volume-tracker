# Project State

## Objective
CLI that shows where onchain DeFi volume is growing or declining — with a
dedicated focus on onchain **memecoin activity**: where money is following,
what's heating up in volume/TVL, and top wallets.

## Current state
- Public repo: `0x-m-dev/onchain-volume-tracker` on `main`.
- **Pushed:** all work is live on `main` via `gh` (installed to `/opt/data/bin/gh`, authed as `0x-m-dev` via device flow).
- **GitHub Pages refreshed** with live memecoin + FOMO snapshot (2026-09-07 21:00 UTC): top chains, memecoin money-flow, FOMO retail-surge watch, top memecoins. Verified HTTP 200 + new sections serving.
- Static GitHub Pages landing lives in `docs/` (source = `/docs` on main).
- **Upgrade: memecoin activity module added** (this session):
  - `tracker memes` command + memecoin section in `tracker run`.
  - DexScreener watchlist search + token-profiles/token-boosts (new-listing/attention signals).
  - Money-flow by chain, top memecoins by volume & 24h surge, memecoin-infra TVL
    (launchpads / meme protocols, bridge/RWA excluded).
  - Top-holder "wallets" via Solana public RPC (best-effort, graceful on 429).
  - **FOMO retail-surge watch:** tokens in an active retail-FOMO phase (volume +
    price + buy-pressure signature) on retail-app chains. Verified live: caught
    NVIDOG (solana, +428%, 74% buy, new-listing). POPCAT's +1219% correctly
    excluded (buy ratio below threshold).
  - New `memecoin_metrics` table (+ buys/sells/buy_ratio/source) + `holders.py` module.
- **FOMO app research:** fomo.family is non-custodial (Privy smart wallets) but
  publishes NO public API (APIs.io: "agent readiness 0/100, human only"). Its
  trader leaderboard/feed is auth-gated. Tracking "their traders" by name isn't
  feasible free/keyless; the on-chain surge signal is the accessible proxy.
- **Trader wallet tracking added:** `tracker wallet <ADDR>` + `TRACKER_WALLETS`
  watchlist decodes a wallet's buy/sell per token from Solana RPC parsed txs.
  Public no-key RPCs block this datacenter (429/403/401/400), so a **free Helius
  key** (`HELIUS_API_KEY`) is the reliable path. User supplies the addresses
  (visible in the fomo app) + the free key.
- **20 tests pass** (5 original + 15 new).
- Live smoke-tested: ~173 tokens collected, 33 active; FOMO surge watch populated;
  `tracker wallet` runs and degrades gracefully without a key.
- Scheduling, webhook delivery, and launchd are not enabled.

## Decisions
- GitHub Pages `/docs` is the public preview; not a production deploy.
- Memecoin infra TVL is ranked by TVL value (7d change is often null in `/protocols`).
- Top wallets = top holders via free Solana RPC only; EVM holder enumeration is
  intentionally out of scope for the free tier (needs Moralis/Alchemy/Dune).
- FOMO trader feed is off-limits (no public API); we track FOMO-style retail
  inflow via on-chain surge signature instead.
- Channel IDs stay in the local registry only.

## Next actions
1. Verify full `tracker run` report end-to-end (chain + memecoin combined).
2. Consider refreshing the GitHub Pages landing with a live memecoin snapshot.
3. Only then consider webhook delivery and launchd scheduling (needs explicit approval).

## Blockers
- Public Solana RPCs frequently return 429/403, so top-holder data is intermittent
  by nature of the free tier. DeFiLlama `/protocols` omits `change_7d` for many
  protocols (shown as n/a).
- Wallet-level FOMO trader tracking needs a free Helius key (`HELIUS_API_KEY`)
  + wallet addresses from the fomo app (`TRACKER_WALLETS`). Not yet configured.

## Last verified
2026-09-07 21:05 UTC
