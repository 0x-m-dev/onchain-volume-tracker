"""Follow specific trader wallets on-chain ("FOMO traders").

Free, no-cost path:
- Wallet addresses come from the user (visible in the fomo app's leaderboard /
  trader profiles — the app is non-custodial, so every trader has a real
  on-chain address).
- Transaction history comes from a Solana RPC endpoint. Public no-key RPCs
  usually block datacenter IPs (429/403), so a free Helius key is the reliable
  option: set ``HELIUS_API_KEY`` and we build ``https://mainnet.helius-rpc.com/?api-key=<key>``.
  Any endpoint can be supplied via ``TRACKER_SOLANA_RPCS``.

We read a wallet's recent signatures (``getSignaturesForAddress``) and decode
each parsed transaction's ``preTokenBalances``/``postTokenBalances`` to compute
net token balance changes — i.e. what the wallet bought/sold, when, and how much.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

HELIUS_TEMPLATE = "https://mainnet.helius-rpc.com/?api-key={key}"


def build_rpcs(config) -> list[str]:
    """Resolve the Solana RPC pool, preferring a Helius key if present."""
    import os
    key = os.getenv("HELIUS_API_KEY")
    if key:
        return [HELIUS_TEMPLATE.format(key=key)] + list(config.solana_rpcs)
    return list(config.solana_rpcs)


def _rpc_call(rpc, method, params, timeout):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        resp = requests.post(
            rpc, json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "tracker/0.1"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        return resp.json(), None
    except requests.RequestException as e:
        return None, str(e)


def get_recent_signatures(wallet, rpcs, limit=20, timeout=12):
    """Return (signatures, note)."""
    errors = []
    for rpc in rpcs:
        body, err = _rpc_call(rpc, "getSignaturesForAddress", [wallet, {"limit": limit}], timeout)
        if err:
            errors.append(f"{rpc}: {err}")
            continue
        result = (body or {}).get("result")
        if result:
            return [s.get("signature") for s in result], f"via {rpc}"
        errors.append(f"{rpc}: empty")
    return [], "; ".join(errors) if errors else "no RPC available"


def _decode_transaction(parsed, wallet):
    """Extract the wallet's net token balance changes from a parsed tx.

    Returns list of {mint, amount, decimals, direction} where direction is
    'bought' if the wallet's balance increased, 'sold' if it decreased.
    """
    result = parsed or {}
    meta = result.get("meta") or {}
    pre = meta.get("preTokenBalances") or []
    post = meta.get("postTokenBalances") or []

    pre_map = {}
    for b in pre:
        if b.get("owner") == wallet:
            pre_map[b.get("mint")] = b.get("uiTokenAmount", {})
    post_map = {}
    for b in post:
        if b.get("owner") == wallet:
            post_map[b.get("mint")] = b.get("uiTokenAmount", {})

    changes = []
    for mint in set(list(pre_map) + list(post_map)):
        pu = pre_map.get(mint, {}).get("uiAmount") or 0
        po = post_map.get(mint, {}).get("uiAmount") or 0
        delta = po - pu
        if abs(delta) < 1e-9:
            continue
        changes.append({
            "mint": mint,
            "amount": abs(delta),
            "decimals": (post_map.get(mint) or pre_map.get(mint) or {}).get("decimals"),
            "direction": "bought" if delta > 0 else "sold",
        })
    return changes


def fetch_wallet_activity(wallet, rpcs, limit=15, timeout=12):
    """Fetch a wallet's recent trades.

    Returns (trades, note). Each trade: {time, signature, token_changes}.
    """
    sigs, note = get_recent_signatures(wallet, rpcs, limit=limit, timeout=timeout)
    if not sigs:
        return [], note

    trades = []
    errors = []
    for rpc in rpcs:
        if trades:
            break
        for sig in sigs:
            body, err = _rpc_call(
                rpc, "getParsedTransaction",
                [sig, {"maxSupportedTransactionVersion": 0}], timeout,
            )
            if err or not body or not body.get("result"):
                continue
            parsed = body["result"]
            ts = (parsed.get("blockTime") or 0)
            changes = _decode_transaction(parsed, wallet)
            trades.append({
                "time": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
                "signature": sig,
                "token_changes": changes,
            })
    if not trades and not note:
        note = "parsed transactions unavailable on all RPCs"
    return trades, note


def summarize_activity(trades, top=8):
    """Reduce raw trades into a readable per-token flow summary."""
    from collections import defaultdict
    flow = defaultdict(lambda: {"bought": 0.0, "sold": 0.0, "n_buys": 0, "n_sells": 0})
    for t in trades:
        for c in t["token_changes"]:
            mint = c["mint"]
            if c["direction"] == "bought":
                flow[mint]["bought"] += c["amount"]
                flow[mint]["n_buys"] += 1
            else:
                flow[mint]["sold"] += c["amount"]
                flow[mint]["n_sells"] += 1
    rows = [
        {"mint": m, **v}
        for m, v in flow.items()
        if v["bought"] > 0 or v["sold"] > 0
    ]
    rows.sort(key=lambda r: r["bought"] + r["sold"], reverse=True)
    return rows[:top]
