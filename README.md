# Onchain Volume Tracker

Python CLI that pulls free DeFiLlama and DexScreener volume data, stores
history in SQLite, and prints chain-level trend reports.

Public repo: `0x-m-dev/onchain-volume-tracker`

## What changed

Promoted from a private workspace to a public Studio project. Added repo
hygiene (PII/README hooks + CI), `PROJECT.yaml`, and an implementation plan.
Scheduling and Discord webhook delivery stay off until explicitly approved.

## Run / verify

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make test
tracker run
```

`tracker run` writes `tracker.db` (gitignored). Optional Discord delivery:

```bash
export DEFLAMA_WEBHOOK_URL=   # leave unset to print locally
```

Commands: `tracker run`, `tracker trends`, `tracker chains`, `tracker top`.

## Notes

- No API keys required for v1.
- Do not commit `.env`, `tracker.db`, or Discord identifiers.
- launchd plist in `launchd/` is a template; it is not loaded.
