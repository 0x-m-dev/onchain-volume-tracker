"""Top token holders / "whale wallets" for memecoins.

Free onchain data does not expose per-token holder lists on most chains. The
one free, keyless path that works is Solana's public RPC `getTokenLargestAccounts`,
which returns the largest holder accounts for an SPL token mint. It is
best-effort: public RPCs are frequently rate-limited (HTTP 429), so this module
tries a small pool of public endpoints, returns whatever it can, and degrades
gracefully to an empty list with an explanatory note.

EVM-chain holder enumeration needs a paid provider (Moralis, Alchemy, Dune)
and is intentionally out of scope for the free tier.
"""

import logging

import requests

logger = logging.getLogger(__name__)


def get_token_top_holders(
    mint_address: str,
    rpc_endpoints: list[str],
    limit: int = 10,
    timeout: int = 12,
) -> tuple[list[dict], str]:
    """Fetch top holder accounts for a Solana SPL token mint.

    Returns ``(holders, note)`` where ``holders`` is a list of
    ``{"wallet", "amount", "amount_human", "decimals"}`` dicts (empty on
    failure) and ``note`` describes data quality / failures.
    """
    if not mint_address:
        return [], "no token address supplied"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenLargestAccounts",
        "params": [mint_address],
    }
    errors = []
    for rpc in rpc_endpoints:
        try:
            resp = requests.post(
                rpc, json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 429:
                errors.append(f"{rpc} -> HTTP 429 (rate-limited)")
                continue
            if resp.status_code != 200:
                errors.append(f"{rpc} -> HTTP {resp.status_code}")
                continue
            body = resp.json()
            result = (body or {}).get("result") or {}
            value = result.get("value") or []
            holders = []
            for acc in value[:limit]:
                amount = float(acc.get("amount", 0) or 0)
                decimals = acc.get("decimals", 0)
                ui = amount / (10 ** decimals) if decimals else amount
                holders.append({
                    "wallet": acc.get("address", ""),
                    "amount": amount,
                    "amount_human": ui,
                    "decimals": decimals,
                })
            if holders:
                note = f"top-holder data via {rpc}"
                return holders, note
            errors.append(f"{rpc} -> empty result")
        except requests.RequestException as e:
            errors.append(f"{rpc} -> {e}")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"{rpc} -> parse error: {e}")

    return [], "; ".join(errors) if errors else "no RPC endpoints configured"
