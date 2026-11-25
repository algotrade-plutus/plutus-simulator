# Notes for the owner: read later (RIVF'26 camera-ready)

## 1. F3 figure: why the conservative queue went from 16.7% undecided to 0%, and why that is not bad (2026-11-24)

**What the 16.7% was.** S8 is an intraday market maker on FPT for one day (2022-11-09). A few of its orders
are marketable (they act as takers). The conservative queue's *taker* path had no trade-size data wired in, so
it marked those orders "undecided". That was an engine wiring gap, not a property of the data: the sized tape
existed and the maker path already used it. Change 2 (`e528633`) wired the tape into the taker path too, so
those orders are now decided: 0%.

**What the figure actually shows is unchanged: the 18.9% swing.** The same strategy on the same data fills
152,600 shares assuming it is first in the queue, and 123,700 assuming it is last. "0% undecided" means the
engine can compute an answer under *each* assumption. It does not mean the answer is known: which assumption
is true cannot be observed, because the data has no order IDs or queue positions. The uncertainty did not
disappear. It moved from "can't decide" to "depends on an assumption you must declare", and the 18.9% spread is
its size.

**Tick data does not make ignorance vanish in general.** On the wider 90-day probe (T2 group D,
`docs/reference/tables/t2/indeterminate.md`), with tick data:

| Queue assumption | Undecided |
|---|---|
| optimistic | 10.1% |
| conservative | 60.2% |

The causes are missing book sizes at deeper levels, missing tape, and the band-edge gap. S8's FPT day is simply
a day where the data is complete.

**Suggested paper wording:** "With a sized tape the conservative arm decides its whole flow on this day; what
remains is the 18.9% the queue assumption alone moves the fill, which no amount of tick data can adjudicate."
Also note that across the 90-day population, tick data still leaves 10–60% undecided depending on the queue
assumption.

**Paper text to change:** any sentence saying the conservative arm "leaves a sixth of its flow undecided" (the
F3 caption and the T4 queue-axis row).

## 2. MarketMaker (T5): results and four decisions for you (2026-11-24)

Repo `proto/ProtoMarketMaker`, `rivf26`, commits `6121ef3`, `b9f4b0b` (local). The rerun to verify is in progress.

| Window | Fills naive → faithful (conservative) | Return naive → faithful |
|---|---|---|
| krx2025 (20 sessions either side of 2025-05-05, DB) | 693 → 116 (16.7%; 50.9% on the 20 pre-cutover sessions it quoted) | +29.6% → −6.0% (pre-cutover only: −5.2% → −6.0%) |
| im2022 (20 sessions either side of 2022-12-15, archive book) | 129 → 70 (54.3%) | **−12.9% → +2.2%** (faithful earns more) |

Mechanisms visible:
- queue spread 27.5% / 28.6%;
- dated-IM capacity 36 → 28 contracts (the paper says 37 → 28);
- post-cutover refusal in 20 of 20 sessions.

**Decisions for you:**

1. **im2022 fails "faithful return ≤ naive".** The naive arm carries inventory overnight and loses there; the faithful
   arm closes out every session, by design (the handoff already says Sharpe is not a criterion for MM because of
   this). Nothing was tuned. Options: report as is, with that explanation; or compare like for like (both arms
   flat overnight). The second needs a naive change.
2. **The conservative queue still can't decide ~99.8% of MM's resting orders.** MM quotes about 31 ticks from the
   last print, beyond the 3 observed book levels, so the queue ahead at its price is unobservable. This is
   different from change 2, which fixed takers: on krx2025, conservative taker fills went 0 → 102. Options:
   keep it as a stated finding (the optimistic arm and the queue spread carry the result); or add an explicit,
   declared engine assumption for orders beyond the observed depth. That is an engine change.
3. **The engine admits derivatives orders after the KRX cutover**, even though its margin model is unresolved
   there. Only the strategy's own guard refuses (S6 style). The paper's "refuses to invent a margin rule" is
   true of the strategy, not of the engine's admission. Options: word the paper that way; or make admission
   return INDETERMINATE when the margin model is unresolved (engine change).
4. **Headline f/n for krx2025:** 16.7% over all 40 sessions (it includes the 20 refused sessions) or 50.9% like
   for like on the 20 it quoted. I'd quote both.

Also:
- MM's committed slices are 16,352,393 B (krx2025) and 8,726,352 B (im2022), 25,078,745 B in all (L2 depth 1–3 with sizes plus tape, 40 sessions). Both are over the
  size flag and need your sign-off before any push.
- ceil/floor are missing for VN30F2212 on 2022-12-02, 12-05 and 12-06, in both the DB and the archive.

## 3. T8 findings that touch the paper (2026-11-24)

1. **A broker profile can relax VSDC on derivatives** (equity is protected: `BrokerTermLooserThanLaw`). Two paths:
   - a negative `BrokerProfile.margin_buffer` margins below VSDC's rate;
   - a `forced_close_utilisation` above 1.00 grades a full QĐ 26 Điều 13 breach as CALL instead of FORCED.

   Behaviour is unchanged; 3 strict-xfail tests show it (`tests/market/session/test_broker_cannot_relax.py`,
   FEATURES D72). **Decide:** add guards (small engine change: the xfails then pass), or disclose. If the paper
   says brokers "can only tighten", it must say "on equity" or the guard must land first.
2. **The 2016-09-12 tick revision is not in the engine.** The rulebook starts 2020-01-01; before that every order is
   INDETERMINATE. The paper (`main.tex:203`) claims "the Vietnamese tick grid with its dated 2016-09-12 revision".
   **Decide:** reword, or encode the pre-2020 grid (needs a source; `dated_rules.py` says the pre-2016 grid was
   never sourced).
3. **Corrected counts:** 114 rule versions, not 97 (341 → 358); 244 broker fields confirmed, but
   published/supplied/inferred is three-way (110 / 0 / 21, plus 113 not published).
4. **Rule-table validator:** 12 tables, 93 keys, 114 rows; no overlaps or gaps; 12 uncovered edges (widened bands
   and some ticks before their source dates; two deliberate VSDC charge switches), all resolving to UNKNOWN.
   `_pick()` now raises on overlap.
5. **Property tests:** 14 Hypothesis properties, 3,850 examples plus 26 boundary cases, none falsified.
6. **Maintenance effort** (`docs/reference/tables/t8_maintenance_effort.md`): the 13% → 17% IM step is 15 rule-data
   lines in 2 units (the dated tuple line plus its 14-line cited rulebook row) and 0 engine lines, plus 3 undated
   copies of 0.17. So `\nMaintDataLines` = 15 and `\nMaintCodeLines` = 0; "one line" is true only of the value.

## 4. MarketMaker: the stronger framing (owner idea, 2026-11-25)

With the algorithm A (naive MM) held fixed and only the environment changed:
1. **Fill assumptions dominate the result.** Return ranges from −2.5% to −16.4% (im2022) and from −5.2% to −25.6%
   (krx2025 pre-cutover) across N0–N3, F-opt and F-con. For a market maker the fill model *is* the P&L.
2. **Naive's bias has no fixed sign.** It flatters takers and grids (SB, Pair, Grid) but penalises this MM through
   adverse selection: its touch-fill rule fills A as the market runs through the quote. Full im2022 window
   (40 sessions, ProtoMarketMaker `result/mm_markout/im2022_markout.md`): 5-min markout per contract N3 −0.71 pts,
   F-opt +0.41, F-con −0.57; trading P&L N3 −27.9M đ, F-opt +72.4M, F-con +34.7M. The faithful arms take liquidity
   in 65% / 91% of contracts (median improvement +0.50 / +0.30 pt). **Correction (2026-11-25):** the earlier
   6-session figures (−2.24 vs −0.78; +76.5M vs −27.3M) came from a script that marked every fill against the F1
   price on a roll day and zeroed carry at contract switches; they are withdrawn. The effect holds but is smaller,
   and at 5 min N3 is close to F-con.
3. **The faithful simulator gives a measured band with attribution**, not one misleading number.

**To claim "closest to the true environment"**, compare with real fills: the handoff's open item, whether the
Algotrade desk can share real fill or slippage statistics (R3.1). Even aggregates for an MM book on similar VN30F
days would show which arm lands closest. Until then, the defensible claim is that the truth lies within F's band
and naive can fall outside it in either direction.

**Decision (owner, 2026-11-25): no real fill data (R3.1 closed as not available).** Credibility instead rests on:
(a) **the queue band is a bound by construction:** optimistic = first in the queue, conservative = behind everything
displayed, so every real queue position lies between them for the given data. Caveat: the conservative arm cannot
place quotes beyond the observed depth (LIMITATIONS #3), which weakens that side of the band.
(b) adverse selection measured from the tape (markouts);
(c) ~~no ghost fills (negative 1-min markouts)~~ withdrawn: F-opt's 1-min markout is +0.21 on the full window;
(d) exact accounting, complete rolls and dated margin.

Paper claim: "naive can fall outside the faithful band in either direction; the band brackets every queue position
the data allows."

## 5. S2: keep the current proof (owner decision, 2026-11-25)

S2 is not rerun on the book. The daily run stands (−77%, forced sale in tranches). The queue measurement
(`measurements/s2_lock_queue.py`, archive book + tape) proves the 2022-11-07 floor sale was blocked by a full lock,
where the daily run assumed a fill (graded `TOUCHED_AT_LIMIT`). No locked-book rule is added to the engine; the
ghost-side limitation (LIMITATIONS item 2) stays disclosed. Not assessed: S2's equity if the 11-07 tranche is carried.

## 6. Decisions of 2026-11-25

- **Principle:** the repos keep every experiment value faithfully, documented in full and easy to follow. The paper
  picks a coherent, succinct subset and a narrative; the details stay in the repo documents.
- **F2:** report the reversal openly (tick 10.1% undecided vs bar 32.6%); it supports the paper's case. Test to be
  rewritten to pin these values.
- **2016 tick revision:** disclose (the rulebook starts on 2020-01-01; earlier dates resolve to UNKNOWN). Not sourced.
- **12 uncovered rule edges:** disclose with the count; pinned by `test_rule_tables.py::OPEN_EDGES`.
- **Slices:** the 6.2 MB indeterminate book slice is approved. The MarketMaker slice (29 MB) is to be trimmed to the
  sessions the ladder and markouts need, after the full-window runs, with a check that no number moves.
- **ProtoPair:** may go public (push still needs the owner's go-ahead).
- **Beyond 3 book levels:** stay undecided; the queue band carries the result (no data in this context).
- **MarketMaker in the paper:** decided later. Meanwhile, the repo gets a full preliminary report
  (`ProtoMarketMaker/result/REPORT.md`).
- **Post-KRX derivatives orders:** KRX admits them, so the engine keeps admitting them. The margin rule is now
  modelled in both layers: the broker checks intraday against VSDC's published initial-margin rate, and VSDC
  computes the binding requirement once after the close (QĐ 26, Phụ lục 2; binary test; top-up by 09:30 T+1).
  Unpublished inputs (calendar-spread rate, haircuts) give UNKNOWN, never a guess.
