# Project State

## Objective
CLI that shows where onchain DeFi volume is growing or declining using free data sources.

## Current state
- Public repo: `0x-m-dev/onchain-volume-tracker` on `main`.
- Static GitHub Pages landing lives in `docs/` (snapshot from 2026-09-06 live run).
- Five regression tests pass.
- Live collection stored 466 chains, 8,190 protocols, 50 DEX pairs; ~$7.38B 24h volume.
- Scheduling, webhook delivery, and launchd are not enabled.

## Decisions
- GitHub Pages `/docs` is the public preview; this is not a production app deploy.
- Channel IDs stay in the local registry only.
- Do not load launchd until a second verified run and an explicit schedule ask.

## Next actions
1. Confirm Pages build is `built` and the preview URL returns HTTP 200.
2. Broader tests for analyzer, report formatting, and persistence.
3. Only then consider webhook delivery and launchd.

## Blockers
- None for Pages preview. Isolated DeFiLlama HTTP 500s are skipped by the collector.

## Last verified
2026-09-06 16:27 PDT
