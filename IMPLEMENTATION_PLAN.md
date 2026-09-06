# Implementation plan — onchain-volume-tracker

Promoted from a private workspace with working CLI code. Do not re-scaffold.

## Done
- Python CLI (`tracker run|trends|chains|top`)
- DeFiLlama + DexScreener collectors with SQLite persistence
- Trend ranking and anomaly flags
- CLI + markdown report formatters
- Optional Discord webhook delivery via env (unset by default)

## Next
1. Broader unit coverage for analyzer, report formatting, and persistence.
2. Keep live collection unscheduled until a second verified run and webhook
   target exist.
3. Add launchd install helper that fills absolute paths; do not load the
   agent until that helper is tested.
4. Preview/ship only after `make test` and a live `tracker run` succeed.

## Out of scope for this launch
- Production deploy
- Dune / paid APIs
- Hardcoded Discord channel IDs
