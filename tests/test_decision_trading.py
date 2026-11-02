import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.decision_agent import portfolio, trading
from src.decision_agent.schemas import Decision


@pytest.fixture
def setup_trading(monkeypatch, tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text('[{"ticker":"AAPL","number_of_stocks":5}]')
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", path)
    client = MagicMock()
    client.get_clock.return_value = SimpleNamespace(is_open=True)
    client.get_all_positions.return_value = [SimpleNamespace(symbol="AAPL", qty="5")]
    monkeypatch.setattr(trading, "get_client", lambda: client)
    monkeypatch.setattr(trading, "sleep", lambda _: None)

    def order(status="filled", filled="2", **kwargs):
        request = client.submit_order.call_args.kwargs["order_data"]
        return SimpleNamespace(
            id="broker-order",
            symbol=request.symbol,
            side=request.side,
            client_order_id=request.client_order_id,
            status=status,
            filled_qty=filled,
            **kwargs,
        )

    client.submit_order.side_effect = lambda order_data: order()
    return client, path, order


@pytest.mark.parametrize("action,expected", [("buy", 7), ("sell", 3)])
def test_sends_market_order_and_records_fill(setup_trading, action, expected):
    client, _path, _ = setup_trading
    trading.execute_decision(
        Decision(ticker="AAPL", action=action, number_of_stocks=2), 5
    )
    request = client.submit_order.call_args.kwargs["order_data"]
    assert request.symbol == "AAPL"
    assert request.qty == 2
    assert request.side == action
    assert request.time_in_force == "day"
    assert request.client_order_id.startswith("decision-")
    assert portfolio.get_number_of_stocks("AAPL") == expected
    assert not trading._pending_path().exists()


@pytest.mark.parametrize("quantity", [50, 51])
def test_buy_limit_is_enforced_before_submission(setup_trading, quantity):
    client, _path, order = setup_trading
    client.submit_order.side_effect = lambda order_data: order(filled=str(quantity))
    decision = Decision(ticker="AAPL", action="buy", number_of_stocks=quantity)
    if quantity > 50:
        with pytest.raises(ValueError, match="more than 50"):
            trading.execute_decision(decision, 5)
        client.submit_order.assert_not_called()
        assert portfolio.get_number_of_stocks("AAPL") == 5
        assert not trading._pending_path().exists()
    else:
        trading.execute_decision(decision, 5)
        assert client.submit_order.call_args.kwargs["order_data"].qty == 50
        assert portfolio.get_number_of_stocks("AAPL") == 55


def test_pending_partial_fill_then_recovery_does_not_resubmit(setup_trading):
    client, _path, order = setup_trading
    client.submit_order.side_effect = lambda order_data: order("partially_filled", "1")
    decision = Decision(ticker="AAPL", action="buy", number_of_stocks=2)
    with pytest.raises(TimeoutError, match="pending"):
        trading.execute_decision(decision, 5, timeout=0)
    assert portfolio.get_number_of_stocks("AAPL") == 6
    client.get_order_by_client_id.return_value = order("partially_filled", "1")
    with pytest.raises(RuntimeError, match="still pending"):
        trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 6
    client.get_order_by_client_id.return_value = order()
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 7
    assert client.submit_order.call_count == 1
    assert not trading._pending_path().exists()


def test_waits_for_fill_before_updating(setup_trading):
    client, path, order = setup_trading
    before = path.read_bytes()
    client.submit_order.side_effect = lambda order_data: order("new", "0")

    def filled(order_id):
        assert path.read_bytes() == before
        assert order_id == "broker-order"
        return order()

    client.get_order_by_id.side_effect = filled
    trading.execute_decision(
        Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5
    )
    assert portfolio.get_number_of_stocks("AAPL") == 7


@pytest.mark.parametrize(
    "status,filled,expected",
    [
        ("rejected", "0", 5),
        ("canceled", "1", 6),
        ("expired", "0", 5),
    ],
)
def test_terminal_failure_records_only_actual_fills(
    setup_trading, status, filled, expected
):
    client, _path, order = setup_trading
    client.submit_order.side_effect = lambda order_data: order(status, filled)
    with pytest.raises(RuntimeError, match=status):
        trading.execute_decision(
            Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5
        )
    assert portfolio.get_number_of_stocks("AAPL") == expected
    assert not trading._pending_path().exists()


def test_network_failure_keeps_client_id_for_recovery(setup_trading):
    client, _path, order = setup_trading
    client.submit_order.side_effect = ConnectionError("connection lost")
    with pytest.raises(RuntimeError, match="uncertain"):
        trading.execute_decision(
            Decision(ticker="AAPL", action="sell", number_of_stocks=2), 5
        )
    saved = json.loads(trading._pending_path().read_text())
    request = client.submit_order.call_args.kwargs["order_data"]
    assert saved["client_order_id"] == request.client_order_id
    assert portfolio.get_number_of_stocks("AAPL") == 5
    client.get_order_by_client_id.return_value = order()
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 3
    assert client.submit_order.call_count == 1


def test_http_rejection_leaves_no_pending_order(setup_trading):
    from alpaca.common.exceptions import APIError
    from requests import HTTPError, Response

    client, _path, _order = setup_trading
    response = Response()
    response.status_code = 403
    client.submit_order.side_effect = APIError(
        '{"message":"insufficient buying power"}', HTTPError(response=response)
    )
    with pytest.raises(RuntimeError, match="rejected"):
        trading.execute_decision(
            Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5
        )
    assert portfolio.get_number_of_stocks("AAPL") == 5
    assert not trading._pending_path().exists()


def test_failed_status_lookup_preserves_recovery_record(setup_trading):
    client, _path, order = setup_trading
    client.submit_order.side_effect = lambda order_data: order("new", "0")
    client.get_order_by_id.side_effect = ConnectionError("status unavailable")
    with pytest.raises(ConnectionError):
        trading.execute_decision(
            Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5
        )
    assert trading._pending_path().exists()
    assert portfolio.get_number_of_stocks("AAPL") == 5
    client.get_order_by_client_id.return_value = order()
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 7
    assert client.submit_order.call_count == 1


def test_portfolio_write_failure_recovers_without_double_trade(
    setup_trading, monkeypatch
):
    client, _path, order = setup_trading
    original = portfolio.set_holding
    monkeypatch.setattr(
        portfolio, "set_holding", MagicMock(side_effect=OSError("disk full"))
    )
    with pytest.raises(OSError, match="disk full"):
        trading.execute_decision(
            Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5
        )
    assert trading._pending_path().exists()
    monkeypatch.setattr(portfolio, "set_holding", original)
    client.get_order_by_client_id.return_value = order()
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 7
    assert client.submit_order.call_count == 1


def test_local_and_broker_holdings_must_match(setup_trading):
    client, _path, _order = setup_trading
    client.get_all_positions.return_value = []
    with pytest.raises(ValueError, match="differs"):
        trading.execute_decision(
            Decision(ticker="AAPL", action="sell", number_of_stocks=2), 5
        )
    client.submit_order.assert_not_called()


def test_hold_does_not_contact_alpaca(setup_trading):
    client, _path, _order = setup_trading
    trading.execute_decision(
        Decision(ticker="AAPL", action="hold", number_of_stocks=0), 5
    )
    assert client.mock_calls == []


def test_client_is_configured_for_paper_trading(monkeypatch):
    from src.alpaca_tools import client

    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    constructor = MagicMock()
    monkeypatch.setattr(client, "TradingClient", constructor)
    client.get_trading_client.cache_clear()
    try:
        client.get_trading_client()
        assert constructor.call_args.kwargs["paper"] is True
    finally:
        client.get_trading_client.cache_clear()


@pytest.mark.parametrize("action,expected", [("buy", 7), ("sell", 3)])
def test_closed_market_books_received_order_without_waiting(setup_trading, action, expected):
    client, path, order = setup_trading
    client.get_clock.return_value = SimpleNamespace(is_open=False)
    client.get_all_positions.return_value = []
    client.submit_order.side_effect = lambda order_data: order("accepted", "0")
    trading.execute_decision(Decision(ticker="AAPL", action=action, number_of_stocks=2), 5)
    assert json.loads(path.read_text()) == [{"ticker": "AAPL", "number_of_stocks": expected}]
    assert not trading._pending_path().exists()
    client.get_order_by_id.assert_not_called()
    client.get_all_positions.assert_not_called()
    trading.sync_pending_order()
    assert client.submit_order.call_count == 1


def test_closed_market_continues_to_another_ticker_and_accepts_local_holding(setup_trading):
    client, _path, order = setup_trading
    client.get_clock.return_value = SimpleNamespace(is_open=False)
    client.submit_order.side_effect = lambda order_data: order("new", "0")
    for ticker, current in [("AAPL", 5), ("MSFT", 0), ("AAPL", 7)]:
        trading.execute_decision(Decision(ticker=ticker, action="buy", number_of_stocks=2), current)
    assert portfolio.get_number_of_stocks("AAPL") == 9
    assert portfolio.get_number_of_stocks("MSFT") == 2
    assert client.submit_order.call_count == 3
    assert not trading._pending_path().exists()


@pytest.mark.parametrize("status", ["rejected", "canceled", "expired"])
def test_closed_market_does_not_book_a_rejected_or_canceled_order(setup_trading, status):
    client, _path, order = setup_trading
    client.get_clock.return_value = SimpleNamespace(is_open=False)
    client.submit_order.side_effect = lambda order_data: order(status, "0")
    with pytest.raises(RuntimeError, match=status):
        trading.execute_decision(Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5)
    assert portfolio.get_number_of_stocks("AAPL") == 5


def test_closed_market_write_failure_recovers_once_even_after_opening(setup_trading, monkeypatch):
    client, _path, order = setup_trading
    client.get_clock.return_value = SimpleNamespace(is_open=False)
    client.submit_order.side_effect = lambda order_data: order("accepted", "0")
    original = portfolio.set_holding

    def write_then_fail(ticker, quantity):
        original(ticker, quantity)
        raise OSError("Interrupted after portfolio write")

    monkeypatch.setattr(portfolio, "set_holding", write_then_fail)
    with pytest.raises(OSError):
        trading.execute_decision(Decision(ticker="AAPL", action="buy", number_of_stocks=2), 5)
    assert portfolio.get_number_of_stocks("AAPL") == 7
    monkeypatch.setattr(portfolio, "set_holding", original)
    client.get_clock.return_value = SimpleNamespace(is_open=True)
    client.get_order_by_client_id.return_value = order("accepted", "0")
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("AAPL") == 7
    assert client.submit_order.call_count == 1
    assert not trading._pending_path().exists()


def test_old_saved_order_is_booked_during_closed_market(setup_trading):
    client, _path, _order = setup_trading
    saved = {"client_order_id": "old-order", "previous_holding": 0,
             "decision": {"ticker": "EQT", "action": "buy", "number_of_stocks": 20}}
    trading._pending_path().write_text(json.dumps(saved))
    client.get_clock.return_value = SimpleNamespace(is_open=False)
    client.get_order_by_client_id.return_value = SimpleNamespace(
        id="existing-eqt", symbol="EQT", side="buy", client_order_id="old-order",
        status="accepted", filled_qty="0",
    )
    trading.sync_pending_order()
    assert portfolio.get_number_of_stocks("EQT") == 20
    client.submit_order.assert_not_called()
    assert not trading._pending_path().exists()
