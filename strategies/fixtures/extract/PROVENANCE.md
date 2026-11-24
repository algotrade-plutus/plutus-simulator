# PROVENANCE: strategies/fixtures/extract (book + tape)

Shipped since 2026-08-29 (W7) from the old dev extract, and **kept unchanged** at RIVF'26 camera-ready after
checking each part against the current sources (2026-11-24):

| Part | Read by | Check | Result |
|---|---|---|---|
| `quote_*` VN30F2504, 2025-04-08 (book, tape, bands) | S8 (futures variant) | vs Algotrade DB, every table | **identical**, row for row and value for value |
| `local_quote_{bid,ask}{price,size}` FPT, 2022-11-09 | S8, S9, F3 | vs the Algotrade Vietnam market dataset archive (the DB has no sizes before 2023) | **identical values** in the same sequence; the archive's timestamps are ~45 ms earlier (its book comes from backup dumps) |
| `local_quote_total` FPT, 2022-11-09 | S8, S9, F3 | vs DB and archive | **identical** |
| `local_quote_matched` FPT, 2022-11-09 | S8, S9, F3 | vs DB and archive | identical prices; this file stamps each price change ~70 us *after* the trade that caused it, the DB at the same instant |

S9's 18.9% queue swing reproduces exactly (152,600 / 123,700 / 137,600 shares) with the archive's book in place of
this one. The `matched` stamping matters for maker fills that rest on price-moving trades: the scenario fixture
(`scenarios/fixtures/book/`, DB/archive tape) moves J32 and J33 for that reason (see their docstrings). S8/S9's
pinned results were checked on this file only.
