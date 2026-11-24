"""Execution adapters: drive a Plutus market from an external strategy.

The paper's claim in code — a strategy pairs Plutus (the counterparty) with
its own signal/portfolio tooling. :class:`PlutusBackend` is the thin, reusable
facade over :class:`~plutus.market.session.ExchangeSession` that every
reference strategy drives, so the same signal code can run against either its
own naive engine or the faithful Plutus market.
"""
from plutus.execution.backend import PlutusBackend

__all__ = ["PlutusBackend"]
