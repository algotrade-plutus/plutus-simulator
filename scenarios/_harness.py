"""Shared plumbing for the scenario acceptance suite.

The scenarios themselves are written **as a user writes them** — public API
only, the way a ``pip install``'d strategy developer interacts with Plutus.
The only thing they share is this: finding the market-data corpus, and
building a session from a config the way :meth:`ExchangeSession.from_config`
expects. Keeping that here lets each scenario read as the user's own program.

Reproducibility: point ``PLUTUS_DATA_ROOT`` at your corpus (a directory of
``quote_*.parquet`` files). If it is unset we fall back to the corpus on the
author's machine, so the suite runs out of the box here and is one env var
away from running anywhere.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from plutus.core.order import Side
from plutus.market.adapters.base import MarketDataSource
from plutus.market.adapters.datahub import DataHubSource
from plutus.market.protocol import LockEvidence, Resolution
from plutus.market.session import ExchangeSession
from plutus.market.session.types import DataField

#: Fallback corpus (author's machine). Override with PLUTUS_DATA_ROOT.
DEFAULT_DATA_ROOT = str(Path.home() / "algotrade-research/dataset/hermes-parquet")

#: The daily-resolution adapter over the corpus. A scenario may override it.
DEFAULT_ADAPTER = "plutus.market.adapters.datahub.DataHubSource"


def data_root() -> str:
    """The market-data corpus root — ``PLUTUS_DATA_ROOT`` or the fallback."""
    return os.environ.get("PLUTUS_DATA_ROOT", DEFAULT_DATA_ROOT)


def data_available() -> bool:
    """Whether a usable corpus is present, so a scenario can skip cleanly."""
    root = Path(data_root())
    return root.is_dir() and any(root.glob("quote_close*.parquet"))


def build_session(config: dict, *,
                  source: Optional[MarketDataSource] = None) -> ExchangeSession:
    """Build a session from a config dict, exactly the user's ``from_config``
    path — the config is written to a file and loaded, no privileged
    injection. The one substitution is ``data.root``, filled from
    ``PLUTUS_DATA_ROOT`` so the same scenario runs on any machine with the
    corpus. ``data.adapter`` defaults to the daily corpus adapter.

    ``source``, forwarded verbatim to ``ExchangeSession.from_config``, is the
    same keyword-only injection point that method documents as existing for
    "a test needs a data source that is not on disk" — ``data.adapter`` and
    ``data.root`` are then unused (``from_mapping`` only calls
    ``load_data_source`` when ``source`` is ``None``). A scenario reaches for
    it only when a fact under test is one the shipped corpus cannot record at
    all (see ``FrozenLockSource`` below, shared by the J2/J11/J10 scenarios):
    every other scenario leaves it unset and reads the live corpus exactly as
    before.
    """
    cfg = json.loads(json.dumps(config))  # deep copy; never mutate the caller's
    data = cfg.setdefault("data", {})
    data.setdefault("adapter", DEFAULT_ADAPTER)
    data["root"] = data_root()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(cfg, handle)
        path = handle.name
    return ExchangeSession.from_config(path, source=source)


class FrozenLockSource(DataHubSource):
    """The live corpus, with one ticker-day's bar overridden to a **proven**
    zero-volume band lock.

    ``band_lock_decision``'s NO_FILL branch requires ``interval.volume == 0``
    exactly — a *proven* lock, distinct from a lock whose volume is merely
    unknown (INDETERMINATE). The Hermes corpus's ``quote_dailyvolume`` table
    never records a literal 0 anywhere (corpus-wide minimum non-null
    quantity is 1 share): a no-trade day simply carries no row, which this
    adapter reports as ``volume=None`` — UNKNOWN, not zero. So no ticker-day
    in the live corpus can produce that proof, and this task's brief
    sanctions the fallback: "if it hand-builds the interval/state: set
    open==high==low==close==ceiling/floor and volume=0."

    Every ticker-day except the one named here is served untouched, straight
    off the real corpus — the instrument spec, admission, and every other
    day's fill all stay genuine. Only the named day's bar is overridden, and
    only ``open``/``high``/``low``/``close``/``volume``/``last`` change: the
    real ceiling/floor/reference for that day (already real HSX ±7% band
    arithmetic) are kept as-is.

    Shared by the J2, J10, and J11 scenarios — each supplies its own
    ``ticker``/``day``/``side`` through the constructor below; that is the
    only thing that ever varied between them.
    """

    def __init__(self, root, *, ticker: str, day: str, side: Side):
        super().__init__(root)
        self._ticker = ticker
        self._day = date.fromisoformat(day)
        self._side = side

    def _is_locked(self, ticker, ts) -> bool:
        d = ts.date() if isinstance(ts, datetime) else ts
        return ticker == self._ticker and d == self._day

    def _frozen(self, state):
        edge = state.ceiling if self._side is Side.BUY else state.floor
        return replace(state, last=edge, locked_side=self._side,
                       lock_evidence=LockEvidence.BAR_PROXY)

    def state_at(self, ticker, ts):
        state = super().state_at(ticker, ts)
        if state is None or not self._is_locked(ticker, ts):
            return state
        return self._frozen(state)

    def states(self, ticker, start, end, *, resolution=Resolution.DAILY):
        for state in super().states(ticker, start, end, resolution=resolution):
            yield self._frozen(state) if self._is_locked(ticker, state.ts) else state

    def interval(self, ticker, start, end, *, resolution=Resolution.DAILY):
        interval = super().interval(ticker, start, end, resolution=resolution)
        if interval is None or not self._is_locked(ticker, start):
            return interval
        state = self._frozen(interval.state)
        edge = state.last  # _frozen already resolved ceiling/floor into `last`
        return replace(
            interval, state=state, open=edge, high=edge, low=edge, close=edge,
            volume=0,
            missing=interval.missing - {DataField.VOLUME, DataField.OPEN,
                                        DataField.HIGH, DataField.LOW,
                                        DataField.CLOSE, DataField.LAST})
