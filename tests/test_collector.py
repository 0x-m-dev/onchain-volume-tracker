import pytest

from tracker.collector import DeFiLlamaClient
from tracker.config import Config
from tracker.db import get_db, get_top_movers, store_chain_metrics


def test_chain_data_accepts_current_list_shape(monkeypatch):
    client = DeFiLlamaClient(Config(rate_limit_delay=0))
    monkeypatch.setattr(
        client,
        "_fetch",
        lambda endpoint: [
            {"name": "OP Mainnet", "tvl": 123.0, "chainId": 10},
            {"name": "Solana", "tvl": 456.0, "chainId": 101},
        ],
    )

    chains = client.get_chain_data()

    assert [chain["slug"] for chain in chains] == ["op-mainnet", "solana"]
    assert chains[1]["tvl"] == 456.0


def test_chain_volume_endpoint_is_url_encoded(monkeypatch):
    client = DeFiLlamaClient(Config(rate_limit_delay=0))
    seen = []
    monkeypatch.setattr(client, "_fetch", lambda endpoint: seen.append(endpoint) or {"total24h": 1})

    assert client.get_chain_dex_volume("OP Mainnet")["total24h"] == 1
    assert seen == ["overview/dexs/OP%20Mainnet"]


def test_mover_direction_and_metric_validation(tmp_path):
    config = Config(db_path=str(tmp_path / "tracker.db"))
    with get_db(config) as conn:
        store_chain_metrics(conn, "gain", "Gain", {"volumeChangeOver24h": 25})
        store_chain_metrics(conn, "loss", "Loss", {"volumeChangeOver24h": -40})

        assert get_top_movers(conn, 1)[0]["name"] == "Gain"
        assert get_top_movers(conn, 1, descending=False)[0]["name"] == "Loss"
        with pytest.raises(ValueError):
            get_top_movers(conn, metric="not_a_column")
