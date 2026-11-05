import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import main
from src.decision_agent import portfolio, trading


@pytest.fixture
def broker(monkeypatch, tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text('[{"ticker":"OLD","number_of_stocks":999}]')
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", path)
    client = MagicMock()
    monkeypatch.setattr(trading, "get_client", lambda: client)
    return client, path


@pytest.mark.parametrize("positions,expected", [
    ([("MSFT", "20.0"), ("NVDA", "3"), ("OLD", "0")],
     [{"ticker": "MSFT", "number_of_stocks": 20}, {"ticker": "NVDA", "number_of_stocks": 3}]),
    ([], []),
])
def test_batch_end_syncs_actual_positions_even_with_empty_queue(broker, tmp_path, positions, expected):
    client, path = broker
    client.get_all_positions.return_value = [SimpleNamespace(symbol=s, qty=q) for s, q in positions]
    queue = tmp_path / "queue.json"
    queue.write_text('{"candidates":[]}')
    main.main(queue, execute_review_all=True)
    assert json.loads(path.read_text()) == expected
    client.submit_order.assert_not_called()


@pytest.mark.parametrize("quantity", ["0.5", "-1", "NaN", "Infinity"])
def test_invalid_broker_positions_preserve_local_file(broker, quantity):
    client, path = broker
    before = path.read_bytes()
    client.get_all_positions.return_value = [
        SimpleNamespace(symbol="VALID", qty="3"), SimpleNamespace(symbol="INVALID", qty=quantity)]
    with pytest.raises(ValueError):
        portfolio.sync_from_alpaca()
    assert path.read_bytes() == before


def test_broker_failure_preserves_local_file(broker):
    client, path = broker
    before = path.read_bytes()
    client.get_all_positions.side_effect = ConnectionError("unavailable")
    with pytest.raises(ConnectionError):
        portfolio.sync_from_alpaca()
    assert path.read_bytes() == before
