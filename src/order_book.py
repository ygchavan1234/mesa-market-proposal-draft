"""Limit Order Book (LOB) engine for the Reflexive Market Simulation.

This module implements a dictionary-based Limit Order Book using the
Mediator Pattern. Agents never interact directly; they submit orders to
this central engine, which handles price discovery and trade execution.

Optimised for long-running Mesa 3.5.0 simulations:
    - O(1) price-level lookups via Python dicts.
    - Bounded trade history via ``collections.deque(maxlen=100)``.
    - Immediate cleanup of exhausted price levels to prevent memory bloat.

Typical usage::

    model = ReflexiveMarketModel()
    model.order_book.add_order("sell", 105.0, 10)
    model.order_book.add_order("buy", 105.0, 5)
    assert model.order_book.last_price == 105.0
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

import mesa


class OrderBook:
    """A decoupled Limit Order Book acting as the market mediator.

    The ``OrderBook`` aggregates buy (bid) and sell (ask) orders at discrete
    price levels.  After every new order submission the matching engine runs
    automatically, executing trades whenever the best bid >= best ask.

    Attributes:
        model: Reference to the parent ``mesa.Model`` instance.
        bids: Mapping of *price -> aggregate quantity* for buy orders.
        asks: Mapping of *price -> aggregate quantity* for sell orders.
        trade_history: Ring-buffer of the most recent 100 executed trades.
        last_price: The price at which the most recent trade was filled.
    """

    def __init__(self, model: mesa.Model) -> None:
        """Initialises the order book with empty sides and a seed price.

        Args:
            model: The Mesa model that owns this order book.
        """
        self.model: mesa.Model = model

        # Price-level aggregation — {price: total_quantity}.
        self.bids: Dict[float, int] = {}
        self.asks: Dict[float, int] = {}

        # Memory-efficient trade tape; never exceeds 100 entries.
        self.trade_history: deque[Dict[str, Any]] = deque(maxlen=100)

        # Seed price — updated only on actual fills.
        self.last_price: float = 100.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_order(self, side: str, price: float, quantity: int) -> None:
        """Submits a limit order and triggers the matching engine.

        Args:
            side: ``"buy"`` to place a bid, ``"sell"`` to place an ask.
            price: The limit price for this order.
            quantity: Number of units to buy or sell.

        Raises:
            ValueError: If *side* is not ``"buy"`` or ``"sell"``, or if
                *quantity* is not a positive integer.
        """
        if side not in ("buy", "sell"):
            raise ValueError(
                f"Invalid order side '{side}'. Must be 'buy' or 'sell'."
            )
        if quantity <= 0:
            raise ValueError(
                f"Order quantity must be positive, got {quantity}."
            )

        if side == "buy":
            self.bids[price] = self.bids.get(price, 0) + quantity
        else:
            self.asks[price] = self.asks.get(price, 0) + quantity

        # Every new order may unlock a match.
        self._match_orders()

    def get_market_depth(self) -> Dict[str, Any]:
        """Returns an agent-safe snapshot of current market conditions.

        The returned dictionary exposes aggregate statistics without
        revealing individual order data, preserving information symmetry.

        Returns:
            A dict with keys ``last_price``, ``best_bid``, ``best_ask``,
            ``spread``, and ``volume``.
        """
        best_bid: Optional[float] = max(self.bids) if self.bids else None
        best_ask: Optional[float] = min(self.asks) if self.asks else None

        spread: Optional[float] = None
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid

        volume: int = sum(self.bids.values()) + sum(self.asks.values())

        return {
            "last_price": self.last_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "volume": volume,
        }

    # ------------------------------------------------------------------
    # Matching Engine (private)
    # ------------------------------------------------------------------

    def _match_orders(self) -> None:
        """Executes trades while the highest bid >= the lowest ask.

        For every match the engine:
            1. Determines the fill quantity (min of both sides).
            2. Decrements the quantities on each side.
            3. Deletes exhausted price levels immediately.
            4. Records the trade on the bounded tape.

        The trade price is set to the ask (passive) side, consistent with
        price-time priority conventions.
        """
        while self.bids and self.asks:
            # Price discovery — O(N) over the number of distinct levels,
            # which is typically small relative to total order count.
            best_bid: float = max(self.bids)
            best_ask: float = min(self.asks)

            if best_bid < best_ask:
                break  # No crossing — book is uncrossed.

            # Fill the smaller side.
            fill_qty: int = min(self.bids[best_bid], self.asks[best_ask])

            self.bids[best_bid] -= fill_qty
            self.asks[best_ask] -= fill_qty

            # CRITICAL: purge zero-quantity levels to prevent O(N) bloat.
            if self.bids[best_bid] == 0:
                del self.bids[best_bid]
            if self.asks[best_ask] == 0:
                del self.asks[best_ask]

            # Update reflexive signal — agents will react to this.
            self.last_price = best_ask

            self.trade_history.append(
                {
                    "price": best_ask,
                    "qty": fill_qty,
                    "step": (
                        self.model.steps
                        if hasattr(self.model, "steps")
                        else 0
                    ),
                }
            )


class ReflexiveMarketModel(mesa.Model):
    """Top-level Mesa model for the Reflexive Market Simulation.

    This model owns the ``OrderBook`` and will orchestrate agent
    scheduling in later phases (Weeks 3-4).  It is designed to be
    compatible with Mesa 3.5.0's forthcoming Signals infrastructure.
    """

    def __init__(self) -> None:
        """Initialises the model and its central order book."""
        super().__init__()
        self.order_book: OrderBook = OrderBook(self)

    def step(self) -> None:
        """Advances the simulation by one tick.

        The matching engine is event-driven (fires on every
        ``add_order``), so this method currently delegates to the base
        Mesa scheduler.  Model-level analytics and signal hooks will be
        added in Phase II.
        """
        super().step()
