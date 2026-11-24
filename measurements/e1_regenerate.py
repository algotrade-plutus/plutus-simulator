"""E1 regeneration from the Algotrade DB: select, extract, run, publish.

RIVF'26 camera-ready, handoff task T2 / item F3. One script, three stages, and
the **same run** feeds both publication forms the owner is choosing between:

(a) **raw slice** -- the 2022 daily fields E1 reads, for the selected tickers,
    with a ``DATA-MANIFEST.md`` (``extract`` stage; left in the data directory,
    never committed);
(b) **statistics only** -- this script, the selection rule (:data:`SELECTION_SQL`)
    and the aggregate outputs (``run`` stage: by-intent x by-policy agreement and
    fill tables, executed-quantity totals, indeterminate shares, N, Wilson 95%
    CIs) as committed JSON + markdown, plus a per-decision outcome table with
    **no price or volume column** (ticker, date, intent, policy, outcome,
    evidence, missing) written to the data directory, *not* the repo.

Stages
======

``select``  Apply the selection rule to the DB (HSX ``instrumenttype='stock'``
            tickers in the ticker master with >= 200 distinct ``quote.close``
            sessions in the year) and write ``selection.json``. This is the only
            whole-universe DB read; it returns ticker names and session counts.
``extract`` Run ``scripts/rivf26_extract.py declared`` for exactly the fields
            ``measurements/fill_divergence.py`` reads (close, open, max, min,
            ceil, floor, reference, dailyvolume, ticker master) over
            ``[year-01-01, year+1-01-01)`` for the selected tickers, then fill in
            the manifest's "why minimal" section.
``run``     Run E1 on the slice (``--data-root`` or ``PLUTUS_DATA_ROOT``),
            check the slice's own universe equals ``selection.json``, and write
            the aggregates (repo) and the per-decision table (data directory).
``all``     The three in order.

Credentials are read by the extraction tool at runtime and never printed.

RUN
    PY=.venv/bin/python
    PYTHONPATH=src $PY -m measurements.e1_regenerate all \\
        --data-dir /path/to/rivf26/data/t2-e1
    # statistics only, from an existing slice:
    PYTHONPATH=src $PY -m measurements.e1_regenerate run --data-dir <slice dir>
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
for _p in (_REPO, _REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from measurements.fill_divergence import (INTENTS, MIN_SESSIONS, YEAR,  # noqa: E402
                                          FillOutcome, discover_universe,
                                          measure_fill_divergence)

EXPERIMENT = "t2-e1"
#: Exactly the daily files ``fill_divergence._load_bars`` / ``discover_universe``
#: / ``DataHubSource.instrument`` read. Nothing else is extracted.
FILES = ("quote_close", "quote_open", "quote_max", "quote_min", "quote_ceil",
         "quote_floor", "quote_reference", "quote_dailyvolume")
AGG_JSON = _REPO / "docs" / "reference" / "tables" / "t2" / "e1_aggregates.json"
AGG_MD = _REPO / "docs" / "reference" / "tables" / "t2" / "e1_aggregates.md"
BOOT_REPS = 2000
BOOT_SEED = 20221
Z95 = 1.959963984540054

#: The selection rule, as run against the DB. Same rule as
#: ``fill_divergence.discover_universe`` runs on a corpus, so the slice
#: re-derives the same universe (checked in ``run``).
SELECTION_SQL = """
SELECT c.tickersymbol, count(DISTINCT c.datetime) AS n
FROM quote.close c JOIN quote.ticker t USING (tickersymbol)
WHERE t.exchangeid = 'HSX' AND t.instrumenttype = 'stock'
  AND c.datetime >= %s AND c.datetime < %s
GROUP BY c.tickersymbol HAVING count(DISTINCT c.datetime) >= %s
ORDER BY n DESC, c.tickersymbol
""".strip()


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = Z95) -> Tuple[float, float, float]:
    """``(p, lo, hi)``: the Wilson score interval for ``k`` successes in ``n``."""
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def _prop(k: int, n: int) -> dict:
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": p, "wilson95": [lo, hi]}


def _cluster_boot(per_ticker: List[Tuple[float, float]], reps: int = BOOT_REPS,
                  seed: int = BOOT_SEED) -> Tuple[float, float]:
    """Percentile 95% CI of ``sum(a)/sum(b)`` resampling whole tickers.

    Decisions are not independent (five intents share a ticker-day; a ticker's
    days share a stock), so the Wilson interval -- which assumes independent
    Bernoulli trials -- is too narrow. The ticker-cluster bootstrap is reported
    beside it for the headline numbers.
    """
    rng = random.Random(seed)
    m = len(per_ticker)
    stats = []
    for _ in range(reps):
        a = b = 0.0
        for _ in range(m):
            x, y = per_ticker[rng.randrange(m)]
            a += x
            b += y
        stats.append(a / b if b else float("nan"))
    stats.sort()
    return stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1]


# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------

def stage_select(data_dir: Path, year: int, min_sessions: int,
                 cred_file: Optional[Path] = None) -> List[str]:
    import rivf26_extract as rx
    db = rx.PgClient(cred_file or rx.CRED_FILE)
    try:
        rows = db.fetch(SELECTION_SQL, [date(year, 1, 1), date(year + 1, 1, 1),
                                        min_sessions])
    finally:
        db.close()
    sel = {
        "rule": (f"HSX instrumenttype='stock' tickers in the DB ticker master with "
                 f">= {min_sessions} distinct quote.close sessions in "
                 f"[{year}-01-01, {year + 1}-01-01)"),
        "sql": SELECTION_SQL,
        "year": year, "min_sessions": min_sessions,
        "tickers": [r[0] for r in rows],
        "sessions": {r[0]: int(r[1]) for r in rows},
        "ticker_days": int(sum(r[1] for r in rows)),
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "selection.json").write_text(json.dumps(sel, indent=2) + "\n")
    print(f"selected {len(rows)} tickers, {sel['ticker_days']:,} ticker-days")
    return sel["tickers"]


_MINIMAL = """## Why this window is minimal

E1 asks five fill questions per (ticker, day) over one calendar year, 2022 (the
handoff keeps 2022 as the E1 year: post the 2021-01-04 HSX lot change, so one
undated `HSX_EXCHANGE` is correct). The tickers are exactly the selection rule's
output (`selection.json`: HSX `instrumenttype='stock'` in the DB ticker master,
>= 200 distinct `quote.close` sessions in 2022). The fields are exactly what
`measurements/fill_divergence.py` reads per ticker-day: close (the at-close limit
price and the bar close), open/max/min (the bar the fill policies judge), ceil
and floor (the band-edge limit prices), reference (band reconstruction when a
published band is missing), dailyvolume (the 10% participation cap), and the
ticker-master row (instrument typing). No warm-up is needed: every question is
judged against its own day's bar. Dropping any ticker, day or field changes the
population the result is stated over.
"""

_SIZE = """## Size flag

Over the flag threshold because the population *is* the result: ~391 tickers x
~249 sessions x 8 daily fields. Each file is a single float/int column per
ticker-day; nothing intraday is included. Publish only if the owner chooses form
(a); form (b) publishes none of these files.
"""


def stage_extract(data_dir: Path, tickers: List[str], year: int,
                  force: bool = False) -> None:
    import rivf26_extract as rx
    argv = ["declared", "--experiment", data_dir.name,
            "--out-root", str(data_dir.parent),
            "--reproduces", ("E1 population fill-policy divergence, 2022 "
                             "(docs/reference/tables/t2/e1.md)"),
            "--files", ",".join(FILES), "--tickers", ",".join(tickers),
            "--start", f"{year}-01-01", "--end", f"{year + 1}-01-01"]
    if force:
        argv.append("--force")
    # The tool refuses a directory holding files it did not write: set our own
    # aside for the extraction and put them back after.
    kept = {}
    (data_dir / "e1_decisions.parquet").unlink(missing_ok=True)  # now stale
    for name in ("selection.json",):
        f = data_dir / name
        if f.exists():
            kept[name] = f.read_bytes()
            f.unlink()
    try:
        rx.main(argv)
    finally:
        for name, blob in kept.items():
            (data_dir / name).write_bytes(blob)
    man = data_dir / "DATA-MANIFEST.md"
    text = man.read_text()
    head, _, rest = text.partition("## Why this window is minimal")
    _, _, rest = rest.partition("\n## ")
    text = head + _MINIMAL + "\n## " + rest
    if "## Size flag" in text:
        head, _, rest = text.partition("## Size flag")
        _, _, rest = rest.partition("\n## ")
        text = head + _SIZE + "\n## " + rest
    # The --tickers argument is 391 names long; keep the manifest readable.
    text = text.replace(",".join(tickers), "<selection.json tickers>")
    man.write_text(text)


def stage_run(data_dir: Path, year: int, min_sessions: int,
              agg_json: Path = AGG_JSON, agg_md: Path = AGG_MD,
              decisions: bool = True) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from plutus.market.adapters.datahub import DataHubSource

    sel_path = data_dir / "selection.json"
    selection = json.loads(sel_path.read_text()) if sel_path.exists() else None
    universe = discover_universe(DataHubSource.for_root(str(data_dir)), year=year,
                                 min_sessions=min_sessions)
    if selection is not None and sorted(universe) != sorted(selection["tickers"]):
        raise SystemExit("slice universe != DB selection; re-extract")

    cols: Dict[str, list] = defaultdict(list)
    # per ticker: [questions, agreed, soft_qty, hard_qty]
    per_ticker: Dict[str, List[int]] = defaultdict(lambda: [0, 0, 0, 0])

    def on_row(row):
        t = per_ticker[row.ticker]
        t[0] += 1
        t[1] += int(row.agreed)
        for sig, d in row.decisions.items():
            if sig.startswith("soft"):
                t[2] += d.quantity
            elif sig.startswith("hard"):
                t[3] += d.quantity
            if decisions:
                cols["ticker"].append(row.ticker)
                cols["date"].append(row.start.date())
                cols["intent"].append(row.name)
                cols["policy"].append(sig.split("(")[0])
                cols["outcome"].append(d.outcome.value)
                cols["evidence"].append(d.evidence.value if d.evidence else None)
                cols["missing"].append(",".join(sorted(m.value for m in d.missing))
                                       or None)

    r = measure_fill_divergence(str(data_dir), year=year,
                                min_sessions=min_sessions, on_row=on_row)
    d = r.to_dict()
    sigs = d["signatures"]
    short = {s: s.split("(")[0] for s in sigs}
    q = r.questions

    pt = list(per_ticker.values())
    dis_lo, dis_hi = _cluster_boot([(x[0] - x[1], x[0]) for x in pt])
    rat_lo, rat_hi = _cluster_boot([(x[2], x[3]) for x in pt])
    soft = next(s for s in sigs if s.startswith("soft"))
    hard = next(s for s in sigs if s.startswith("hard"))

    out = {
        "experiment": "E1 population fill-policy divergence (RIVF'26 T2/F3)",
        "data_source": "Algotrade DB (read-only), extracted with "
                       "scripts/rivf26_extract.py declared",
        "selection_rule": (selection or {}).get("rule"),
        "selection_sql": SELECTION_SQL,
        "population": d["population"],
        "window": [str(year) + "-01-01", str(year + 1) + "-01-01"],
        "tickers": d["tickers"], "ticker_days": d["ticker_days"],
        "questions": q, "signatures": sigs,
        "ci_method": ("Wilson score 95% on each proportion (assumes independent "
                      "decisions); ticker-cluster percentile bootstrap 95% "
                      f"({BOOT_REPS} reps, seed {BOOT_SEED}) on the headline "
                      "disagreement and the soft/hard quantity ratio"),
        "disagreement": {**_prop(q - r.agreed, q),
                         "cluster_boot95": [dis_lo, dis_hi]},
        "agreement": _prop(r.agreed, q),
        "by_intent": {},
        "by_policy": {},
        "executed_quantity": {
            short[s]: d["by_policy"][s]["filled_quantity"] for s in sigs},
        "soft_over_hard_quantity": {
            "ratio": (d["by_policy"][soft]["filled_quantity"]
                      / d["by_policy"][hard]["filled_quantity"]),
            "cluster_boot95": [rat_lo, rat_hi]},
    }
    for s in sigs:
        oc = d["by_policy"][s]["outcomes"]
        out["by_policy"][short[s]] = {
            "signature": s,
            "fill": _prop(oc["fill"], q), "no_fill": _prop(oc["no_fill"], q),
            "indeterminate": _prop(oc["indeterminate"], q),
            "filled_quantity": d["by_policy"][s]["filled_quantity"],
        }
    for intent, a in d["by_intent"].items():
        n = a["n"]
        out["by_intent"][intent] = {
            "n": n,
            "disagreement": _prop(n - round(a["agreement_rate"] * n), n),
            "fill": {short[s]: _prop(a["filled_by_policy"][s], n) for s in sigs},
            "indeterminate": {short[s]: _prop(a["indeterminate_by_policy"][s], n)
                              for s in sigs},
            "filled_quantity": {short[s]: a["filled_quantity_by_policy"][s]
                                for s in sigs},
        }
    # exact integer agreed count per intent (avoid float round-trip)
    for intent, a in r.by_intent.items():
        out["by_intent"][intent]["disagreement"] = _prop(a.n - a.agreed, a.n)

    agg_json.parent.mkdir(parents=True, exist_ok=True)
    agg_json.write_text(json.dumps(out, indent=2) + "\n")
    agg_md.write_text(render_md(out))
    print(f"wrote {agg_json}\nwrote {agg_md}")

    if decisions:
        tbl = pa.table({
            "ticker": pa.array(cols["ticker"], pa.string()),
            "date": pa.array(cols["date"], pa.date32()),
            "intent": pa.array(cols["intent"], pa.string()),
            "policy": pa.array(cols["policy"], pa.string()),
            "outcome": pa.array(cols["outcome"], pa.string()),
            "evidence": pa.array(cols["evidence"], pa.string()),
            "missing": pa.array(cols["missing"], pa.string()),
        })
        path = data_dir / "e1_decisions.parquet"
        pq.write_table(tbl, path, compression="zstd", compression_level=9)
        print(f"wrote {path} ({tbl.num_rows:,} rows)")
    return out


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def _pc(x: dict) -> str:
    lo, hi = x["wilson95"]
    return f"{100 * x['p']:.2f}% [{100 * lo:.2f}, {100 * hi:.2f}]"


def render_md(o: dict) -> str:
    pols = list(o["by_policy"])
    L = ["# E1 aggregates (statistics-only form)", "",
         "Generated by `measurements/e1_regenerate.py run`; do not edit by hand. "
         "Every proportion is `p [Wilson 95% lo, hi]` over N decisions.", "",
         f"- **Population:** {o['population']}",
         f"- **Selection rule:** {o['selection_rule']}",
         f"- **Window:** [{o['window'][0]}, {o['window'][1]})",
         f"- **N:** {o['tickers']} tickers, {o['ticker_days']:,} ticker-days, "
         f"{o['questions']:,} decisions (each under {len(pols)} policies)",
         f"- **CIs:** {o['ci_method']}", "",
         "## Headline", "",
         f"- Disagreement: {_pc(o['disagreement'])}; ticker-cluster bootstrap "
         f"[{100 * o['disagreement']['cluster_boot95'][0]:.2f}, "
         f"{100 * o['disagreement']['cluster_boot95'][1]:.2f}]",
         f"- Executed quantity soft / hard: "
         f"{o['executed_quantity']['soft']:,} / {o['executed_quantity']['hard']:,} "
         f"= {o['soft_over_hard_quantity']['ratio']:.2f}x; ticker-cluster bootstrap "
         f"[{o['soft_over_hard_quantity']['cluster_boot95'][0]:.2f}, "
         f"{o['soft_over_hard_quantity']['cluster_boot95'][1]:.2f}]", "",
         "## By intent: disagreement and fill rate per policy", "",
         "| Intent | N | Disagree | " + " | ".join(f"fill `{p}`" for p in pols)
         + " |", "|---|--:|--:|" + "--:|" * len(pols)]
    for i, a in o["by_intent"].items():
        L.append(f"| `{i}` | {a['n']:,} | {_pc(a['disagreement'])} | "
                 + " | ".join(_pc(a["fill"][p]) for p in pols) + " |")
    L += ["", "## By intent: indeterminate share per policy", "",
          "| Intent | " + " | ".join(f"`{p}`" for p in pols) + " |",
          "|---|" + "--:|" * len(pols)]
    for i, a in o["by_intent"].items():
        L.append(f"| `{i}` | " + " | ".join(_pc(a["indeterminate"][p])
                                            for p in pols) + " |")
    L += ["", "## By intent: executed quantity (shares) per policy", "",
          "| Intent | " + " | ".join(f"`{p}`" for p in pols) + " |",
          "|---|" + "--:|" * len(pols)]
    for i, a in o["by_intent"].items():
        L.append(f"| `{i}` | " + " | ".join(f"{a['filled_quantity'][p]:,}"
                                            for p in pols) + " |")
    L += ["", "## By policy (all intents)", "",
          "| Policy | Fill | No fill | Indeterminate | Executed qty |",
          "|---|--:|--:|--:|--:|"]
    for p, a in o["by_policy"].items():
        L.append(f"| `{a['signature']}` | {_pc(a['fill'])} | {_pc(a['no_fill'])} | "
                 f"{_pc(a['indeterminate'])} | {a['filled_quantity']:,} |")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("select", "extract", "run", "all"))
    ap.add_argument("--data-dir", type=Path, required=True,
                    help=f"slice directory (its name is the experiment, e.g. "
                         f"{EXPERIMENT})")
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--min-sessions", type=int, default=MIN_SESSIONS)
    ap.add_argument("--force", action="store_true",
                    help="let the extraction tool replace an earlier slice")
    ap.add_argument("--no-decisions", action="store_true",
                    help="skip the per-decision outcome table")
    a = ap.parse_args(argv)
    if a.stage in ("select", "all"):
        tickers = stage_select(a.data_dir, a.year, a.min_sessions)
    if a.stage in ("extract", "all"):
        if a.stage == "extract":
            tickers = json.loads((a.data_dir / "selection.json").read_text())["tickers"]
        stage_extract(a.data_dir, tickers, a.year, force=a.force)
    if a.stage in ("run", "all"):
        stage_run(a.data_dir, a.year, a.min_sessions,
                  decisions=not a.no_decisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
