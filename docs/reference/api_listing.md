# API listing (RIVF'26 T8.4)

The whole user-facing loop in eight lines of public API: create a session at a dated instant, submit an
order, read the outcome with its fill evidence level (PROVEN / ASSUMED / UNEVIDENCED), and read the
account state. It runs on the shipped fixture `scenarios/fixtures/daily/` (no corpus needed), from the
repository root.

```python
from decimal import Decimal
from plutus.market import Order, Side
from plutus.market.session import ExchangeSession, event_evidence_level
s = ExchangeSession.from_config("scenarios/fixtures/api_listing.json")  # HSX, from 2022-11-09
s.submit(Order("FPT", Side.BUY, 1000, limit_price=Decimal("74.0")))
fill = s.advance_to(s.now().replace(hour=15))[-1]
print(fill.kind.value, fill.price, event_evidence_level(fill).name)
print(s.cash().settled_balance, s.holdings("FPT").unsettled)
```

Output:

```
filled 74.0 PROVEN
125980020.0 (HoldingTranche(quantity=1000, settles_at=datetime.datetime(2022, 11, 11, 13, 0), acquired_at=datetime.datetime(2022, 11, 9, 15, 0), source_order_id='PLU-00000001'),)
```

What each line shows:

- **Session at a dated instant.** `scenarios/fixtures/api_listing.json` sets the period (2022-11-09 to
  2022-11-15), the venue (HSX), 200,000,000 VND of cash, the `hard` fill policy and the daily data
  adapter. Every rule the session applies is resolved at its clock, which starts at 2022-11-09 00:00.
- **Outcome and evidence.** The buy limit at 74.0 fills at 74.0 for 1,000 shares. The market traded
  through the limit that day, so the fill's evidence is `TRADED_THROUGH` and its level is **PROVEN**.
  `event_evidence_level` grades any event `advance_to` returns: FILLED/PARTIALLY_FILLED by the evidence
  they carry (PROVEN or ASSUMED), INDETERMINATE as UNEVIDENCED, other kinds `None`.
- **Account state.** Settled cash is 200,000,000 − 74,000,000 − 19,980 charges = 125,980,020 VND. The 1,000
  shares sit in an unsettled tranche that becomes sellable at 13:00 on T+2 (2022-11-11), the post-2022-08-29
  settlement instant.

Executed verbatim by `tests/test_api_listing.py`, which reads the code block above from this file, checks
that it is at most eight lines, runs it from the repository root and checks the output.
