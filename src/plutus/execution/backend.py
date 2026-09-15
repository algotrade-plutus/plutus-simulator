"""A reusable execution backend over a Plutus :class:`ExchangeSession`.

``PlutusBackend`` is deliberately thin: it adds a dict-config convenience
builder, a ``fills`` helper, and a stable surface a strategy codes against, and
holds no strategy logic of its own. Every reference strategy (SmartBeta, Grid,
MarketMaker, Pair) drives this same facade, so the faithful-execution path is
written and tested once.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import List, Mapping, Optional, Union

from plutus.market.session import (ExchangeSession, Accepted, Rejected, Event,
                                    Cancelled, Amended, OrderId)
from plutus.market.protocol import Order


def _kind(event: Event) -> str:
    """The event's kind as a plain string (``EventKind`` is a str-mixed enum)."""
    return getattr(getattr(event, "kind", None), "value", getattr(event, "kind", ""))


class PlutusBackend:
    """Submit orders and read account truth against a Plutus session.

    Construct with :meth:`from_config` (the public config path), or wrap an
    already-built :class:`ExchangeSession` directly. The surface mirrors the
    session's own broker-facing API; strategies never import the session type.
    """

    def __init__(self, session: ExchangeSession) -> None:
        self.session = session

    @classmethod
    def from_config(cls, config: Mapping, *, source=None) -> "PlutusBackend":
        """Build from a config dict, exactly the public ``from_config`` path —
        the dict is written to a temp JSON and loaded, no privileged injection.
        Pass ``source`` to share one :class:`DataHubSource` with a signal feed
        so admission price and signal price cannot diverge.
        """
        cfg = json.loads(json.dumps(config))  # deep copy; never mutate caller's
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(cfg, handle)
            path = handle.name
        if source is not None:
            return cls(ExchangeSession.from_config(path, source=source))
        return cls(ExchangeSession.from_config(path))

    # -- operations --------------------------------------------------------
    def submit(self, order: Order) -> Union[Accepted, Rejected]:
        return self.session.submit(order)

    def cancel(self, order_id: OrderId) -> Union[Cancelled, Rejected]:
        """Cancel a resting order — the maker requote / risk-pull seam.

        A derivatives requote is cancel-and-resubmit (not amend): the session
        refuses a derivatives ``amend`` so the margin requirement is re-run on a
        fresh submit. Feed ``ack.order_id`` from the order's ``submit`` Accepted.
        """
        return self.session.cancel(order_id)

    def amend(self, order_id: OrderId, *, quantity: Optional[int] = None,
              limit_price: Optional[Decimal] = None) -> Union[Amended, Rejected]:
        """Amend a resting order in place (equity strategies).

        Re-runs admission and funding. Refused for derivatives orders by the
        session — cancel and resubmit there.
        """
        return self.session.amend(order_id, quantity=quantity,
                                  limit_price=limit_price)

    def advance_to(self, ts: datetime) -> List[Event]:
        return self.session.advance_to(ts)

    @staticmethod
    def fills(events) -> List[Event]:
        """The FILLED / PARTIALLY_FILLED events in an event list."""
        return [e for e in events if _kind(e) in ("filled", "partially_filled")]

    # -- read models -------------------------------------------------------
    def cash(self):
        return self.session.cash()

    def holdings(self, ticker: str):
        return self.session.holdings(ticker)

    def positions(self):
        return self.session.positions()

    def margin(self):
        return self.session.margin()

    def indeterminate_report(self):
        return self.session.indeterminate_report()
