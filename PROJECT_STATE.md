# Project State

## Objective
CLI that shows where onchain DeFi volume is growing or declining — with a
dedicated focus on onchain **memecoin activity**: where money is following,
what's heating up in volume/TVL, and top wallets.

## Current state
- Public repo: `0x-m-dev/onchain-volume-tracker` on `main`.
- Static GitHub Pages landing lives in `docs/` (snapshot from 2026-09-06 live run).
- Preview verified: https://0x-m-dev.github.io/onchain-volume-tracker/ (HTTP 200, status `built`).
- **Upgrade: memecoin activity module added** (this session):
  - `tracker memes` command + memecoin section in `tracker run`.
  - DexScreener watchlist search + token-profiles/token-boosts (new-listing/attention signals).
  - Money-flow by chain, top memecoins by volume & 24h surge, memecoin-infra TVL
    (launchpads / meme protocols, bridge/RWA excluded).
  - Top-holder "wallets" via Solana public RPC (best-effort, graceful on 429).
  - New `memecoin_metrics` table + `holders.py` module.
- **15 tests pass** (5 original + 10 new memecoin/analysis/report/holder tests).
- Live smoke-tested: ~124 tokens collected, 26–29 active (vol > $25k); money flow
  aggregated (bsc/solana/ethereum/robinhood); launchpad TVL listed; holder lookup
  returns unavailable + reason when public RPC is rate-limited.
- Scheduling, webhook delivery, and launchd are not enabled.

## Decisions
- GitHub Pages `/docs` is the public preview; not a production deploy.
- Memecoin infra TVL is ranked by TVL value (7d change is often null in `/protocols`).
- Top wallets = top holders via free Solana RPC only; EVM holder enumeration is
  intentionally out of scope for the free tier (needs Moralis/Alchemy/Dune).
- Channel IDs stay in the local registry only.

## Next actions
1. Verify full `tracker run` report end-to-end (chain + memecoin combined).
2. Consider refreshing the GitHub Pages landing with a live memecoin snapshot.
3. Only then consider webhook delivery and launchd scheduling (needs explicit approval).

## Blockers
- Public Solana RPCs frequently return 429/403, so top-holder data is intermittent
  by nature of the free tier. DeFiLlama `/protocols` omits `change_7d` for many
  protocols (shown as n/a).

## Last verified
2026-09-07 20:27 UTC
