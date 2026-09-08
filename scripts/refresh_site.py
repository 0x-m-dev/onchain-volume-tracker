#!/usr/bin/env python3
"""Refresh the onchain-volume-tracker GitHub Pages dashboard with live data.

Runs a live collection via the tracker package, then regenerates docs/index.html
(the bento-grid dashboard) embedding the fresh numbers, and commits/pushes to
main so GitHub Pages serves it.

Usage (run from the repo root or via cron):
    python refresh_site.py [--commit] [--db /tmp/site.db]

Requires the tracker venv (python -m pip install -e ".[dev]").
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
sys.path.insert(0, os.path.join(REPO, "src"))
DOCS = os.path.join(REPO, "docs", "index.html")


def sh(cmd, cwd=REPO):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)


def money(v):
    v = float(v or 0)
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v/1e3:.1f}K"


def pct_html(v):
    if v is None:
        return '<span class="pct flat">n/a</span>'
    c = "up" if v > 0 else "down" if v < 0 else "flat"
    s = "+" if v > 0 else ""
    return f'<span class="pct {c}">{s}{v:.1f}%</span>'


def _load_sections(run_output):
    """Parse key CLI sections back out of a tracker run's stdout (fragile but
    avoids importing heavy deps at render time)."""
    # We instead collect via the analyzer objects below; this helper is unused
    # fallback. Keep minimal.
    return {}


def collect(config):
    """Run collection + analysis and return a plain-dict snapshot."""
    from tracker.collector import DataCollector
    from tracker.analyzer import TrendAnalyzer
    from tracker.config import Config

    cfg = config or Config.from_env()
    collector = DataCollector(cfg)
    data = collector.collect_all()
    stats = collector.store_to_db(data)
    analyzer = TrendAnalyzer(cfg)
    chain = analyzer.get_chain_analysis()
    meme = analyzer.get_memecoin_analysis(data.get("meme_tvl", []))
    return {"chain": chain, "meme": meme, "stats": stats, "data": data}


def _meme_card(t):
    """Build a memecoin card: symbol/chain/vol/change/mcap + Chart link + copy CA."""
    sym = t.get("symbol") or "?"
    chain = (t.get("chain") or "").lower()
    ca = t.get("token_address") or ""
    nw = '<span class="flag-new">NEW</span>' if t.get("source") == "new-listing" else ""
    # DexScreener chart link uses the token address: dexscreener.com/{chain}/{ca}
    ds_url = f"https://dexscreener.com/{chain}/{ca}" if (chain and ca) else "#"
    chg = t.get("price_change_24h")
    chg_html = pct_html(chg)
    ca_short = (ca[:6] + "…" + ca[-4:]) if len(ca) > 14 else (ca or "-")
    return (
        f'<div class="meme-card">'
        f'<div class="row1"><span class="sym">{sym}{nw}</span>'
        f'<span class="chain">{chain}</span></div>'
        f'<div class="stats">'
        f'<span>vol <b>{money(t.get("volume_24h"))}</b></span>'
        f'<span>24h {chg_html}</span>'
        f'<span>mc <b>{money(t.get("market_cap"))}</b></span>'
        f'</div>'
        f'<div class="actions">'
        f'<a class="btn ds" href="{ds_url}" target="_blank" rel="noopener">Chart ↗</a>'
        f'<button class="btn ca" data-copy data-ca="{ca}" title="Copy contract address">'
        f'<span>{ca_short}</span> <span class="copyok" style="display:none">✓</span></button>'
        f'</div></div>'
    )


def build_html(snap, ts):
    chain = snap["chain"]
    meme = snap["meme"]
    data = snap["data"]

    # --- hero: top chains by volume ---
    chains = chain.get("top_by_volume", [])[:5]
    hero_bars = []
    maxv = 1
    for c in chains:
        v = c.get("volume_24h") or 0
        if v > maxv:
            maxv = v
    for c in chains:
        v = c.get("volume_24h") or 0
        w = (v / maxv * 100) if maxv else 0
        cls = "sol" if (c.get("name") or "").lower() == "solana" else ""
        hero_bars.append(
            f'<div class="bar-row"><span class="bn">{c.get("name","?")}</span>'
            f'<div class="track"><div class="fill {cls}" style="width:{w:.1f}%"></div></div>'
            f'<span class="bv">{money(v)} {pct_html(c.get("volume_change_24h"))}</span></div>'
        )
    total_vol = sum((c.get("volume_24h") or 0) for c in chain.get("top_by_volume", []))
    n_up = len(chain.get("top_gainers", []))
    n_anom = len(chain.get("anomalies", []))

    # --- movers ---
    movers_html = ""
    for g in chain.get("top_gainers", [])[:4]:
        v = g.get("volume_change_24h") or 0
        movers_html += (f'<div class="mover"><span class="mn">{g.get("name","?")}</span>'
                        f'<span class="md up">+{v:.1f}%</span></div>')
    # top losers
    losers = chain.get("top_losers", [])[:3]
    for l in losers:
        v = l.get("volume_change_24h") or 0
        movers_html += (f'<div class="mover"><span class="mn">{l.get("name","?")}</span>'
                        f'<span class="md down">{v:.1f}%</span></div>')

    # --- money flow ---
    flow = meme.get("chain_flow", [])[:4]
    flow_html = ""
    if flow:
        maxf = max((r.get("volume") or 0) for r in flow) or 1
        for r in flow:
            w = (r.get("volume") or 0) / maxf * 100
            flow_html += (f'<div class="flow-item"><div class="top">'
                          f'<span class="cn">{r.get("chain","?")}</span>'
                          f'<span class="cv up">{money(r.get("volume"))}</span></div>'
                          f'<div class="track"><div class="fill" style="width:{w:.1f}%"></div></div>'
                          f'<div class="sub2">{r.get("token_count",0)} tokens · top {r.get("top_symbol","-")}</div></div>')

    # --- fomo surge ---
    fomo = meme.get("fomo_surge", [])
    if fomo:
        fomo_html = "".join(_meme_card(t) for t in fomo[:6])
    else:
        fomo_html = ('<div class="fomo-empty">No token is in an active retail-FOMO surge right now. '
                     'Watch triggers on real volume + heavy buy pressure on retail chains '
                     '(solana / base / bsc / eth / monad).</div>')

    # --- top memecoins ---
    memes = meme.get("top_volume", [])[:6]
    memes_html = "".join(_meme_card(t) for t in memes)

    # --- infra tvl ---
    tvl = meme.get("tvl_by_value", [])
    tvl_rows = ""
    if len(tvl) > 1:
        for p in tvl[1:6]:
            tvl_rows += (f'<div class="tvl-row">'
                         f'<span class="pn">{p.get("name","?")}</span>'
                         f'<span class="pv">{money(p.get("tvl"))}</span>'
                         f'<span class="pc">{p.get("category","")}</span></div>')
    tvl_top = tvl[0] if tvl else {}
    tvl_top_name = tvl_top.get("name", "-")
    tvl_top_val = money(tvl_top.get("tvl"))
    tvl_top_cat = tvl_top.get("category", "")

    # --- hottest memecoin gainers (24h price) as cards with chart+CA ---
    hot = meme.get("top_surge", [])[:6]
    hot_html = "".join(_meme_card(t) for t in hot)

    # --- chips ---
    n_chains = chain.get("total_chains", len(data.get("chains", [])))
    n_proto = len(data.get("protocols", []))
    n_memes = meme.get("active_tokens", 0)

    html = TEMPLATE
    subs = {
        "{ts}": ts, "{n_chains}": str(n_chains), "{n_proto}": str(n_proto),
        "{n_memes}": str(n_memes), "{total_vol}": money(total_vol),
        "{n_tracked}": str(len(chain.get("top_by_volume", [])) or n_chains),
        "{n_up}": str(n_up), "{n_anom}": str(n_anom),
        "{hero_bars}": "".join(hero_bars), "{movers}": movers_html,
        "{flow}": flow_html, "{fomo}": fomo_html, "{memes}": memes_html,
        "{tvl_rows}": tvl_rows, "{tvl_top_name}": tvl_top_name,
        "{tvl_top_cat}": tvl_top_cat, "{tvl_top_val}": tvl_top_val,
        "{hot}": hot_html,
    }
    for k, v in subs.items():
        html = html.replace(k, v)
    return html


TEMPLATE = open(os.path.join(REPO, "templates", "bento.html")).read()


def commit_and_push(ts):
    sh("git add docs/index.html")
    r = sh(f"git commit -q -m 'chore: refresh site dashboard snapshot ({ts})'")
    if r.returncode != 0:
        return False  # nothing to commit
    p = sh("git push origin main 2>&1")
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="commit + push the refresh")
    ap.add_argument("--db", default=None)
    ap.add_argument("--memes", default=None, help="comma memecoin list")
    args = ap.parse_args()

    os.environ["TRACKER_DB_PATH"] = args.db or os.path.join(REPO, "site_refresh.db")
    if args.memes:
        os.environ["TRACKER_MEMECOINS"] = args.memes
    os.environ["TRACKER_RATE_LIMIT_DELAY"] = "0.1"

    snap = collect(None)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_html(snap, ts)
    os.makedirs(os.path.dirname(DOCS), exist_ok=True)
    with open(DOCS, "w") as f:
        f.write(html)
    print(f"docs/index.html regenerated ({len(html)} bytes) at {ts}")
    if args.commit:
        ok = commit_and_push(ts.replace(" ", "_").replace(":", "-"))
        print("pushed" if ok else "commit/push skipped or failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
