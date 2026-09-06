# Project State

## Objective
CLI that shows where onchain DeFi volume is growing or declining using free data sources.

## Current state
- Promoted from a private workspace to a public Studio project.
- Repo: `0x-m-dev/onchain-volume-tracker` on `main`.
- Discord work stays in the existing `#onchain-volume-tracker` channel (no duplicate).
- Five regression tests pass.
- Live collection previously stored 466 chains, 8,190 protocols, and 50 DEX pairs.
- Scheduling, webhook delivery, and launchd are not enabled.

## Decisions
- Keep SQLite local; no production deploy from this launch.
- Channel IDs stay in the local registry only.
- Do not load launchd until a second verified run and an explicit schedule ask.

## Next actions
1. Broader tests for analyzer, report formatting, and persistence.
2. Second live `tracker run` in this channel.
3. Only then consider webhook delivery and launchd.

## Blockers
- None for launch. Isolated DeFiLlama HTTP 500s are skipped by the collector.

## Last verified
2026-09-06 16:23 PDT
