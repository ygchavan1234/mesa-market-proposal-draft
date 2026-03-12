"""Smoke tests for the Limit Order Book."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from src.order_book import ReflexiveMarketModel


def test_partial_fill():
    m = ReflexiveMarketModel()

    # 1. Place a sell order
    m.order_book.add_order("sell", 105, 10)
    depth = m.order_book.get_market_depth()
    print("After SELL 10@105:", depth)
    assert depth["best_ask"] == 105
    assert depth["volume"] == 10

    # 2. Partial fill — buy 5 of the 10 offered
    m.order_book.add_order("buy", 105, 5)
    depth = m.order_book.get_market_depth()
    print("After BUY  5@105:", depth)
    assert m.order_book.last_price == 105.0, f"Expected 105.0, got {m.order_book.last_price}"
    assert m.order_book.asks.get(105, 0) == 5, f"Expected 5 remaining, got {m.order_book.asks.get(105, 0)}"
    assert len(m.order_book.trade_history) == 1
    assert m.order_book.trade_history[0]["qty"] == 5
    assert m.order_book.trade_history[0]["price"] == 105
    print("  -> last_price:", m.order_book.last_price, "  PASS")


def test_full_fill_and_cleanup():
    m = ReflexiveMarketModel()
    m.order_book.add_order("sell", 105, 10)
    m.order_book.add_order("buy", 105, 5)

    # Exhaust the remaining 5
    m.order_book.add_order("buy", 106, 5)
    depth = m.order_book.get_market_depth()
    print("After BUY  5@106:", depth)
    assert 105 not in m.order_book.asks, "Price level 105 should have been deleted"
    assert m.order_book.last_price == 105.0
    print("  -> price-level cleanup  PASS")


def test_no_match_when_spread_exists():
    m = ReflexiveMarketModel()
    m.order_book.add_order("buy", 99, 10)
    m.order_book.add_order("sell", 101, 10)
    assert len(m.order_book.trade_history) == 0
    depth = m.order_book.get_market_depth()
    assert depth["spread"] == 2.0
    print("No-match spread test:  PASS")


def test_validation():
    m = ReflexiveMarketModel()
    try:
        m.order_book.add_order("hold", 100, 1)
        assert False, "Should have raised ValueError for invalid side"
    except ValueError:
        pass

    try:
        m.order_book.add_order("buy", 100, -5)
        assert False, "Should have raised ValueError for negative qty"
    except ValueError:
        pass

    print("Validation tests:      PASS")


if __name__ == "__main__":
    test_partial_fill()
    test_full_fill_and_cleanup()
    test_no_match_when_spread_exists()
    test_validation()
    print()
    print("=== ALL TESTS PASSED ===")
