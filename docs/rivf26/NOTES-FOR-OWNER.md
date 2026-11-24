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
