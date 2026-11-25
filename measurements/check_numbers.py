"""Check every camera-ready headline number against the committed result file it comes from.

RIVF'26 camera-ready, handoff task T9 (the headline map, ``docs/camera-ready-numbers.md``). The registry below
holds one entry per number the paper states: the value as stated, a tolerance (half a unit in the last stated
digit unless noted), and an extractor that reads the value from a committed result file (JSON key, markdown
table cell, markdown regex, CSV column sum) or a committed data slice (sha256 against its DATA-MANIFEST).

Cheap by design: it reads committed files only, in this repo and in the proto strategy repos (``--proto-root``,
default ``../proto`` relative to this repo). It never reruns an experiment and never touches the database.

Verdicts:
- PASS    the source holds the stated value (within tolerance);
- FAIL    the source disagrees, or the source file or key is missing;
- PENDING the number is not final yet (a run in progress, a count to refresh at freeze, or no committed result
          file yet); the entry says why and what value is currently recorded, if any;
- SKIP    only with ``--skip-missing-proto`` when the proto root does not exist (a bare clone of this repo).

RUN
    PYTHONPATH=src:. python measurements/check_numbers.py [--proto-root ../proto] [--only <id-prefix>]
        [--skip-missing-proto] [--json out.json] [--markdown] [--write-doc]

Exit status is 1 if any entry FAILs, else 0. ``--markdown`` prints the generated tables of the headline map;
``--write-doc`` rewrites the generated block of ``docs/camera-ready-numbers.md`` in place.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PROTO_ROOT = Path("..") / "proto"
DOC = Path("docs") / "camera-ready-numbers.md"
BEGIN, END = "<!-- BEGIN GENERATED: measurements/check_numbers.py --write-doc -->", "<!-- END GENERATED -->"
SIM = "sim"   # source key for this repo; any other key is a repo directory under the proto root


class CheckError(Exception):
    """A source exists but does not hold what the entry expects (wrong key, sha256 mismatch, ...)."""


# --------------------------------------------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, repo_root: Path, proto_root: Path):
        self.repo_root, self.proto_root = Path(repo_root), Path(proto_root)
        self._cache: dict[Path, Any] = {}

    def root(self, src: str) -> Path:
        return self.repo_root if src == SIM else self.proto_root / src

    def file(self, src: str, rel: str) -> Path:
        p = self.root(src) / rel
        if not p.is_file():
            raise FileNotFoundError(f"{src}:{rel}")
        return p

    def text(self, src: str, rel: str) -> str:
        p = self.file(src, rel)
        if p not in self._cache:
            self._cache[p] = p.read_text(encoding="utf-8")
        return self._cache[p]

    def json(self, src: str, rel: str) -> Any:
        key = self.file(src, rel).with_suffix(".json#parsed")
        if key not in self._cache:
            self._cache[key] = json.loads(self.text(src, rel))
        return self._cache[key]


_NUM = re.compile(r"[-−]?\d[\d,]*(?:\.\d+)?")


def parse_number(s: str) -> float:
    """First number in a cell or match: handles thousands commas, the Unicode minus, **bold**, %, đ, +."""
    m = _NUM.search(str(s).replace("**", ""))
    if not m:
        raise CheckError(f"no number in {s!r}")
    t = m.group(0).replace("−", "-").replace(",", "")
    v = float(t)
    return int(v) if re.fullmatch(r"-?\d+", t) else v


@dataclass
class Extractor:
    src: str
    path: str
    desc: str
    fn: Callable[[Ctx], Any]

    def __call__(self, ctx: Ctx) -> Any:
        return self.fn(ctx)


def _walk(obj: Any, keys: tuple) -> Any:
    for k in keys:
        if isinstance(k, tuple):                       # (field, value): the list element whose field == value
            hits = [x for x in obj if isinstance(x, dict) and x.get(k[0]) == k[1]]
            if len(hits) != 1:
                raise CheckError(f"{len(hits)} elements with {k[0]} == {k[1]!r}")
            obj = hits[0]
        else:
            try:
                obj = obj[k]
            except (KeyError, IndexError, TypeError) as e:
                raise CheckError(f"no key {k!r}") from e
    return obj


def _keydesc(keys: tuple) -> str:
    return ".".join(f"[{k[0]}={k[1]}]" if isinstance(k, tuple) else str(k) for k in keys)


def J(src: str, path: str, *keys) -> Extractor:
    """A JSON value at ``keys`` (a tuple key selects the list element whose field equals the value)."""
    return Extractor(src, path, f"`{_keydesc(keys)}`", lambda c: _walk(c.json(src, path), keys))


def MDCELL(src: str, path: str, row: str, col: int) -> Extractor:
    """The number in cell ``col`` (0-based) of the first markdown table row matching regex ``row``."""
    def fn(c: Ctx):
        for line in c.text(src, path).splitlines():
            if line.lstrip().startswith("|") and re.search(row, line):
                cells = [x.strip() for x in line.strip().strip("|").split("|")]
                return parse_number(cells[col])
        raise CheckError(f"no row matching /{row}/")
    return Extractor(src, path, f"row /{row}/ cell {col}", fn)


def MDRE(src: str, path: str, regex: str, group: int = 1) -> Extractor:
    """The number captured by ``regex`` (first match in the file)."""
    def fn(c: Ctx):
        m = re.search(regex, c.text(src, path), flags=re.S)
        if not m:
            raise CheckError(f"no match for /{regex}/")
        return parse_number(m.group(group))
    return Extractor(src, path, f"regex /{regex}/", fn)


def CSVSUM(src: str, path: str, column: str) -> Extractor:
    def fn(c: Ctx):
        rows = list(csv.DictReader(c.text(src, path).splitlines()))
        return sum(int(r[column]) for r in rows)
    return Extractor(src, path, f"sum of column `{column}`", fn)


def CALC(fn: Callable[..., Any], *parts: Extractor, desc: str = "") -> Extractor:
    """A value computed from other extractors (shown against the first part's file)."""
    first = parts[0]
    d = desc or "computed from " + "; ".join(f"`{p.path}` {p.desc}" for p in parts)
    return Extractor(first.src, first.path, d, lambda c: fn(*(p(c) for p in parts)))


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_MANIFEST_ROW = re.compile(r"^\|\s*`?([^`|]+?)`?\s*\|.*`([0-9a-f]{64})`")


def SLICE(src: str, manifest: str, allow_missing: tuple[str, ...] = ()) -> Extractor:
    """Number of files listed in a committed DATA-MANIFEST whose committed copy has the listed sha256.

    A listed file is looked up beside the manifest, then at the repo root (MarketMaker lists repo-relative
    paths), then, for ProtoGrid's ``data/manifest/<window>/`` layout, under ``data/*/<window>/``. A sha256
    mismatch is an error; a missing file is an error unless it is named in ``allow_missing``.
    """
    def fn(c: Ctx):
        mpath = c.file(src, manifest)
        root, mdir = c.root(src), mpath.parent
        ok = 0
        for line in c.text(src, manifest).splitlines():
            m = _MANIFEST_ROW.match(line.strip())
            if not m:
                continue
            name, sha = m.group(1).strip(), m.group(2)
            cands = [mdir / name, root / name]
            if mdir.parent.name == "manifest":
                cands += sorted(root.glob(f"data/*/{mdir.name}/{name}"))
            f = next((p for p in cands if p.is_file()), None)
            if f is None:
                if name in allow_missing:
                    continue
                raise CheckError(f"listed file not found: {name}")
            if _sha256(f) != sha:
                raise CheckError(f"sha256 mismatch: {f.relative_to(root)}")
            ok += 1
        return ok
    return Extractor(src, manifest, "files whose sha256 matches the manifest", fn)


def RESULT_SLICES(src: str, result: str, *keys, base: str = "") -> Extractor:
    """Number of slice files a result JSON records ({path: {sha256}}) whose committed copy matches.

    Paths are taken relative to the repo root, or to ``base`` (a repo-relative directory) when the result
    records bare file names.
    """
    def fn(c: Ctx):
        recorded = _walk(c.json(src, result), keys)
        root = c.root(src) / base
        ok = 0
        for rel, meta in recorded.items():
            p = root / rel
            if not p.is_file():
                raise CheckError(f"recorded slice file not found: {rel}")
            if _sha256(p) != meta["sha256"]:
                raise CheckError(f"sha256 of {rel} differs from the result's record")
            ok += 1
        return ok
    return Extractor(src, result, f"`{_keydesc(keys)}` sha256 vs the committed files", fn)


def SOURCE_SHA(src: str, result: str, keys: tuple, target_keys: tuple) -> Extractor:
    """1 if the file a result JSON names (``target_keys`` → path) has the sha256 it records (``keys``)."""
    def fn(c: Ctx):
        doc = c.json(src, result)
        rel, sha = _walk(doc, target_keys), _walk(doc, keys)
        if _sha256(c.file(src, rel)) != sha:
            raise CheckError(f"sha256 of {rel} differs from {result}")
        return 1
    return Extractor(src, result, f"sha256 of the file at `{_keydesc(target_keys)}` vs `{_keydesc(keys)}`", fn)


# --------------------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------------------

@dataclass
class Group:
    title: str
    repo: str            # SIM or a proto repo directory name
    command: str
    slice: str


@dataclass
class Entry:
    id: str
    group: str
    claim: str
    old: str
    new: str                                   # the value as the paper states it
    expected: Any = None                       # number or string; numbers are compared after ``scale``
    tol: float = 0.0
    scale: float = 1.0
    get: Extractor | None = None
    source: str = ""                           # display override for the field/cell
    macro: str = ""
    status: str = "check"                      # "check" | "pending"
    note: str = ""


@dataclass
class Result:
    entry: Entry
    verdict: str
    value: Any = None
    detail: str = ""


# Data slices (see the "Data slices" section of the headline map for their sha256 values).
SL_E1 = "`rivf26/data/t2-e1/` (391 HSX tickers, 2022; not shipped, statistics only; sha256 in the map's slice table)"
SL_F2 = "`rivf26/data/t2-indeterminate/{daily,book}` (FPT, HPG, HTV, 2022-10-20..11-30; not shipped)"
SL_FUT = "`rivf26/data/t2-futures-margin/` (VN30F front month, 2021-06-01..2022-12-30; sha256 in `docs/reference/tables/t2/futures_margin.md`)"
SL_HSX = "`rivf26/data/t2-hsx-daily/` and `t2-hsx-daily-grid-history/` (sha256 in `docs/reference/tables/t2/hsx_daily.md`)"

A_E1 = "docs/reference/tables/t2/e1_aggregates.json"
T_E1 = "docs/reference/tables/t2/e1_published/totals.json"
F_E1 = "figures/e1_fill_divergence.json"
P_E1 = "docs/reference/tables/t2/e1_published"
F2A = "docs/reference/tables/t2/indeterminate_after_change2.json"
F2B = "docs/reference/tables/t2/indeterminate_before_change2.json"
F3 = "figures/f3_cross_policy_divergence.json"
FUT = "docs/reference/tables/t2/futures_margin.md"
HSX = "docs/reference/tables/t2/hsx_daily"
T8C = "docs/reference/tables/t8_counts.md"
T8M = "docs/reference/tables/t8_maintenance_effort.md"
BENCH = "docs/reference/tables/t8_perf_benchmark.json"

GROUPS: dict[str, Group] = {
    "e1": Group("E1: fill-policy divergence over the 2022 HSX population", SIM,
                "`PYTHONPATH=src:. python -m measurements.e1_regenerate run --data-dir <rivf26-data>/t2-e1`, then "
                "`python measurements/e1_publish.py --data-root <rivf26-data>/t2-e1 --out docs/reference/tables/t2/e1_published`",
                SL_E1),
    "f2": Group("F2: the indeterminate rate, bar vs tick", SIM,
                "`PYTHONPATH=src:. python measurements/indeterminate_rate.py` on the T2 group D slices "
                "(see `docs/reference/tables/t2/indeterminate.md`); the figure and its JSON are re-rendered with "
                "`measurements/indeterminate_rate.py --from-json docs/reference/tables/t2/indeterminate_after_change2.json`",
                SL_F2),
    "f3": Group("F3: fill-policy axis (S1) and queue axis (S9)", SIM,
                "`env -u PLUTUS_DATA_ROOT pytest strategies/test_f3_cross_policy.py strategies/test_s9_queue_sensitivity.py` "
                "(writes `figures/f3_cross_policy_divergence.json`)",
                "`strategies/fixtures/parquet/` (DATA-MANIFEST, checked below) and `strategies/fixtures/extract/` "
                "(no sha256 manifest; `PROVENANCE.md` only)"),
    "margin": Group("Derivatives margin: regime split, the IM step, margin-call incidence", SIM,
                    "`PYTHONPATH=src:. python measurements/t2_futures_margin.py <rivf26-data>/t2-futures-margin`", SL_FUT),
    "hsx": Group("Equity admission, band agreement, tick-grid conformity", SIM,
                 "`measurements/equity_admission.py`, `band_conformance.py`, `grid_conformity.py` "
                 "(exact invocations in `docs/reference/tables/t2/hsx_daily.md`)", SL_HSX),
    "t8": Group("T8: rule versions, broker fields, maintenance effort, validator, properties, benchmark", SIM,
                "`PYTHONPATH=src python measurements/t8_counts.py`; `python measurements/maintenance_effort.py --markdown`; "
                "`PYTHONPATH=src:. python measurements/perf_benchmark.py`", "none (engine source and git history)"),
    "tests": Group("Test-suite counts (F4)", SIM,
                   "`env -u PLUTUS_DATA_ROOT pytest tests`; `pytest scenarios`; `pytest strategies` (each on its own)",
                   "shipped fixtures"),
    "findings": Group("Scenario and strategy findings quoted in the text", SIM,
                      "`env -u PLUTUS_DATA_ROOT pytest strategies/test_s2_*.py scenarios`", "shipped fixtures"),
    "sb": Group("Table II, ProtoSmartBeta (null anchor)", "ProtoSmartBeta",
                "`.venv/bin/python -m proto_smart_beta.experiments.null_anchor`",
                "`data/market/<w>/`, `data/signal/<w>/` (DATA-MANIFESTs, checked under `slice.*`)"),
    "grid": Group("Table II, ProtoGrid", "ProtoGrid", "`.venv/bin/pg-anchor`",
                  "`data/{band,tick}/<w>/` (DATA-MANIFEST in `data/manifest/<w>/`, checked under `slice.*`)"),
    "pair": Group("Table II, ProtoPair", "ProtoPair", "`.venv/bin/pp-anchor`; `.venv/bin/pp-credibility`",
                  "`data/market/<w>/` (DATA-MANIFEST, checked under `slice.*`)"),
    "mm": Group("Table II, ProtoMarketMaker: anchor (faithful arm flat each session)", "ProtoMarketMaker",
                "`.venv/bin/python -m proto_market_maker.experiments.mm_anchor <window>`",
                "`data/{band,l2,market}/<window>/` (`data/<window>-MANIFEST.md`, checked under `slice.*`)"),
    "ladder": Group("ProtoMarketMaker attribution ladder (algorithm A fixed)", "ProtoMarketMaker",
                    "`.venv/bin/python -m proto_market_maker.experiments.mm_faithful_a <window> --queue <q>`, then "
                    "`.venv/bin/python -m proto_market_maker.experiments.mm_ladder <window>`",
                    "as the MM anchor"),
    "slices": Group("Data-slice integrity (sha256 of every committed slice file vs its manifest)", SIM,
                    "this checker", "each manifest named in the row"),
}


def pct(eid, group, claim, old, new_display, get, *, decimals, macro="", note="", scale=100.0):
    """A percentage stated with ``decimals`` decimals, read as a fraction (``scale`` 100) or a percent (1)."""
    v = float(re.sub(r"[^\d.\-]", "", new_display.replace("−", "-")))
    return Entry(eid, group, claim, old, new_display, expected=v, tol=0.5 * 10 ** -decimals + 1e-9,
                 scale=scale, get=get, macro=macro, note=note)


def num(eid, group, claim, old, new_display, get, *, tol=0.0, macro="", note="", scale=1.0):
    v = parse_number(new_display)
    return Entry(eid, group, claim, old, new_display, expected=v, tol=tol, scale=scale, get=get,
                 macro=macro, note=note)


def pending(eid, group, claim, old, new_display, note, macro=""):
    return Entry(eid, group, claim, old, new_display, status="pending", note=note, macro=macro)


def _registry() -> list[Entry]:
    R: list[Entry] = []
    a = lambda *k: J(SIM, A_E1, *k)

    # ---- E1 ---------------------------------------------------------------------------------------------------
    R += [
        num("e1.decisions", "e1", "decisions (5 intents × ticker-days)", "477,537", "484,949",
            J(SIM, T_E1, "questions"), macro=r"\nDecisions"),
        num("e1.agreed", "e1", "decisions on which all three policies agree", "—", "332,549", J(SIM, T_E1, "agreed")),
        num("e1.tickers", "e1", "tickers (HSX stocks, ≥200 sessions in 2022)", "385", "391", J(SIM, T_E1, "tickers"),
            macro=r"\nEoneTickers"),
        num("e1.ticker_days", "e1", "ticker-days", "95,815", "97,269", J(SIM, T_E1, "ticker_days")),
        pct("e1.agree", "e1", "policies agree", "68.4%", "68.57%", a("agreement", "p"), decimals=2,
            macro=r"\pctPolicyAgree"),
        pct("e1.disagree", "e1", "policies disagree", "31.6%", "31.43%", a("disagreement", "p"), decimals=2,
            macro=r"\pctPolicyDisagree"),
        pct("e1.disagree.wilson_lo", "e1", "disagree, Wilson 95% low", "31.50", "31.30%",
            a("disagreement", "wilson95", 0), decimals=2),
        pct("e1.disagree.wilson_hi", "e1", "disagree, Wilson 95% high", "31.76", "31.56%",
            a("disagreement", "wilson95", 1), decimals=2),
        pct("e1.disagree.boot_lo", "e1", "disagree, ticker-cluster bootstrap 95% low", "—", "30.97%",
            a("disagreement", "cluster_boot95", 0), decimals=2),
        pct("e1.disagree.boot_hi", "e1", "disagree, ticker-cluster bootstrap 95% high", "—", "31.84%",
            a("disagreement", "cluster_boot95", 1), decimals=2),
        num("e1.published.n_sum_month", "e1", "published by-month table sums to the decisions", "—", "484,949",
            CSVSUM(SIM, f"{P_E1}/by_month_intent.csv", "n")),
        num("e1.published.agreed_sum_month", "e1", "published by-month table sums to the agreed", "—", "332,549",
            CSVSUM(SIM, f"{P_E1}/by_month_intent.csv", "agreed")),
        num("e1.published.n_sum_ticker", "e1", "published by-ticker table sums to the decisions", "—", "484,949",
            CSVSUM(SIM, f"{P_E1}/by_ticker_intent.csv", "n")),
        num("e1.published.agreed_sum_ticker", "e1", "published by-ticker table sums to the agreed", "—", "332,549",
            CSVSUM(SIM, f"{P_E1}/by_ticker_intent.csv", "agreed")),
        num("e1.figure.decisions", "e1", "figure data (`figures/e1_fill_divergence.json`) carries the same N", "477,537",
            "484,949", J(SIM, F_E1, "questions")),
        pct("e1.figure.agree", "e1", "figure data agreement rate", "68.4%", "68.57%", J(SIM, F_E1, "agreement_rate"),
            decimals=2),
    ]
    intents = [("market_buy", "market order", "95.5%", "95.44%"),
               ("limit_buy_at_close", "limit buy at close", "23.1%", "23.13%"),
               ("limit_sell_at_close", "limit sell at close", "23.3%", "23.52%"),
               ("limit_buy_at_floor", "limit buy at floor", "9.9%", "9.15%"),
               ("limit_sell_at_ceil", "limit sell at ceiling", "6.0%", "5.55%")]
    for key, label, old, new in intents:
        R.append(pct(f"e1.disagree.{key}", "e1", f"policies disagree: {label}", old, new,
                     a("by_intent", key, "disagreement", "p"), decimals=2))
    fills = {  # intent: (old soft/hard/prob as published, new soft, hard, prob)
        "market_buy": (("89.21%", "0%", "0%"), ("89.14%", "0.00%", "0.00%")),
        "limit_buy_at_close": (("89.20%", "72.32%", "80.73%"), ("89.13%", "72.30%", "80.68%")),
        "limit_sell_at_close": (("89.21%", "72.81%", "81.11%"), ("89.14%", "72.55%", "80.92%")),
        "limit_buy_at_floor": (("9.47%", "0%", "4.74%"), ("8.74%", "0.00%", "4.39%")),
        "limit_sell_at_ceil": (("5.64%", "0%", "2.76%"), ("5.21%", "0.00%", "2.55%")),
    }
    for key, (olds, news) in fills.items():
        for pol, o, n in zip(("soft", "hard", "probabilistic"), olds, news):
            R.append(pct(f"e1.fill.{key}.{pol}", "e1", f"fill rate, {key}, `{pol}`", o, n,
                         a("by_intent", key, "fill", pol, "p"), decimals=2))
    for pol, old, new in (("hard", "33.4%", "33.26%"), ("soft", "2.7%", "2.75%"), ("probabilistic", "21.0%", "20.97%")):
        R.append(pct(f"e1.undecided.{pol}", "e1", f"undecided share, `{pol}`", old, new,
                     a("by_policy", pol, "indeterminate", "p"), decimals=2))
    R += [
        num("e1.shares.soft", "e1", "filled shares, `soft`", "245.8M", "247,376,400", a("executed_quantity", "soft"),
            macro=r"\sharesSoft"),
        num("e1.shares.hard", "e1", "filled shares, `hard`", "128.5M", "129,818,200", a("executed_quantity", "hard"),
            macro=r"\sharesHard"),
        num("e1.shares.probabilistic", "e1", "filled shares, `probabilistic`", "148M", "149,450,400",
            a("executed_quantity", "probabilistic")),
        num("e1.shares.ratio", "e1", "filled shares, soft / hard", "1.91×", "1.91", a("soft_over_hard_quantity", "ratio"),
            tol=0.005, macro=r"\xSharesSoftHard"),
        num("e1.shares.ratio.boot_lo", "e1", "soft / hard ratio, bootstrap 95% low", "—", "1.89",
            a("soft_over_hard_quantity", "cluster_boot95", 0), tol=0.005),
        num("e1.shares.ratio.boot_hi", "e1", "soft / hard ratio, bootstrap 95% high", "—", "1.92",
            a("soft_over_hard_quantity", "cluster_boot95", 1), tol=0.005),
    ]

    # ---- F2 ---------------------------------------------------------------------------------------------------
    arm = lambda path, label, *k: J(SIM, path, "arms", ("label", label), *k)
    BAR, OPT, CON = "BAR / hard", "TICK / book-walk (optimistic)", "TICK / book-walk (conservative)"
    R += [
        num("f2.days", "f2", "instrument-days (FPT, HPG, HTV)", "66", "90", J(SIM, F2A, "instrument_days")),
        pct("f2.bar", "f2", "undecided, `hard` at the daily bar", "35.8%", "32.6%", arm(F2A, BAR, "rate"), decimals=1),
        pct("f2.bar.ci_lo", "f2", "bar, Wilson 95% low", "32.3", "29.7%", arm(F2A, BAR, "ci_low"), decimals=1),
        pct("f2.bar.ci_hi", "f2", "bar, Wilson 95% high", "39.4", "35.7%", arm(F2A, BAR, "ci_high"), decimals=1),
        num("f2.bar.n", "f2", "bar, fill evaluations", "698", "950", arm(F2A, BAR, "evaluations")),
        pct("f2.tick_opt", "f2", "undecided, `book_walk` tick, optimistic queue", "85.6%", "10.1%",
            arm(F2A, OPT, "rate"), decimals=1),
        pct("f2.tick_opt.ci_lo", "f2", "tick optimistic, Wilson 95% low", "83.5", "8.7%", arm(F2A, OPT, "ci_low"),
            decimals=1),
        pct("f2.tick_opt.ci_hi", "f2", "tick optimistic, Wilson 95% high", "87.4", "11.7%", arm(F2A, OPT, "ci_high"),
            decimals=1),
        num("f2.tick_opt.n", "f2", "tick optimistic, fill evaluations", "1,212", "1,484", arm(F2A, OPT, "evaluations")),
        pct("f2.tick_con", "f2", "undecided, `book_walk` tick, conservative queue", "99.7%", "60.2%",
            arm(F2A, CON, "rate"), decimals=1),
        num("f2.tick_con.n", "f2", "tick conservative, fill evaluations", "1,545", "1,650", arm(F2A, CON, "evaluations")),
        pct("f2.tick_con.before_change2", "f2", "tick conservative before change 2 (`e528633`)", "99.7%", "78.2%",
            arm(F2B, CON, "rate"), decimals=1),
        pct("f2.bar.resolution_limit", "f2", "bar: share whose cause is the resolution limit", "35.8%", "32.6%",
            arm(F2A, BAR, "resolution_limit_share"), decimals=1),
        num("f2.figure.days", "f2", "figure data (`figures/f2_indeterminate_rate.json`) carries the same days",
            "66", "90", J(SIM, "figures/f2_indeterminate_rate.json", "instrument_days")),
        pct("f2.figure.bar", "f2", "figure data: bar", "35.8%", "32.6%",
            arm("figures/f2_indeterminate_rate.json", BAR, "rate"), decimals=1),
        pct("f2.figure.tick_opt", "f2", "figure data: tick optimistic", "85.6%", "10.1%",
            arm("figures/f2_indeterminate_rate.json", OPT, "rate"), decimals=1),
        pct("f2.figure.tick_con", "f2", "figure data: tick conservative", "99.7%", "60.2%",
            arm("figures/f2_indeterminate_rate.json", CON, "rate"), decimals=1),
        num("f2.tick.resolution_limit", "f2", "tick (both queues): resolution-limit share", "0", "0",
            CALC(lambda x, y: x + y, arm(F2A, OPT, "resolution_limit_share"), arm(F2A, CON, "resolution_limit_share"))),
    ]

    # ---- F3 ---------------------------------------------------------------------------------------------------
    R += [
        pct("f3.s1.soft.return", "f3", "S1 return under `soft`", "−75.5%", "−76.4%",
            J(SIM, F3, "fill_axis", "soft", "return_pct"), decimals=1),
        num("f3.s1.soft.fills", "f3", "S1 fills under `soft`", "5", "5", J(SIM, F3, "fill_axis", "soft", "fills")),
        num("f3.s1.soft.forced", "f3", "S1 forced liquidations under `soft`", "2", "3",
            J(SIM, F3, "fill_axis", "soft", "forced")),
        pct("f3.s1.soft.undecided", "f3", "S1 undecided under `soft`", "0%", "0%",
            J(SIM, F3, "fill_axis", "soft", "indeterminate_rate"), decimals=0),
        pct("f3.s1.hard.return", "f3", "S1 return under `hard`", "0.0%", "0.0%",
            J(SIM, F3, "fill_axis", "hard", "return_pct"), decimals=1),
        pct("f3.s1.hard.undecided", "f3", "S1 undecided under `hard`", "50%", "50%",
            J(SIM, F3, "fill_axis", "hard", "indeterminate_rate"), decimals=0),
        pct("f3.s1.probabilistic.undecided", "f3", "S1 undecided under `probabilistic`", "50%", "50%",
            J(SIM, F3, "fill_axis", "probabilistic", "indeterminate_rate"), decimals=0),
        num("f3.queue.optimistic", "f3", "S9 maker shares, optimistic queue", "152,600", "152,600",
            J(SIM, F3, "queue_axis", "optimistic", "maker_shares"), macro=r"\sharesQueueOpt"),
        num("f3.queue.conservative", "f3", "S9 maker shares, conservative queue", "123,700", "123,700",
            J(SIM, F3, "queue_axis", "conservative", "maker_shares"), macro=r"\sharesQueueCons"),
        num("f3.queue.probabilistic", "f3", "S9 maker shares, probabilistic queue", "137,600", "137,600",
            J(SIM, F3, "queue_axis", "probabilistic", "maker_shares")),
        pct("f3.queue.swing", "f3", "queue swing (optimistic − conservative) / optimistic (F5)", "18.9%", "18.9%",
            CALC(lambda o, c: (o - c) / o, J(SIM, F3, "queue_axis", "optimistic", "maker_shares"),
                 J(SIM, F3, "queue_axis", "conservative", "maker_shares")), decimals=1, macro=r"\pctQueueSwing"),
        pct("f3.queue.conservative.undecided", "f3", "S9 conservative queue undecided", "16.7%", "0%",
            J(SIM, F3, "queue_axis", "conservative", "indeterminate_rate"), decimals=0),
    ]

    # ---- Derivatives margin -----------------------------------------------------------------------------------
    inc = lambda kind, hold: MDCELL(SIM, FUT, rf"^\| {kind} incidence \| {hold} \|", 3)
    R += [
        num("margin.entries", "margin", "entries in the VN30F front-month book", "381", "381",
            MDRE(SIM, FUT, r"N = ([\d,]+) entries")),
        num("margin.pre", "margin", "mean requirement, pre-KRX IM+VM", "17,692,385đ", "17,692,385",
            MDCELL(SIM, FUT, r"^\| mean margin requirement \| pre-KRX", 3), macro=r"\marginPre"),
        num("margin.post", "margin", "mean requirement, post-KRX scenario grid", "22,995,748đ", "22,995,748",
            MDCELL(SIM, FUT, r"^\| mean margin requirement \| post-KRX", 3), macro=r"\marginPost"),
        pct("margin.regime_split", "margin", "regime split, post-KRX grid vs pre-KRX IM+VM", "+30.0%", "+30.0%",
            CALC(lambda pre, post: post / pre - 1, MDCELL(SIM, FUT, r"^\| mean margin requirement \| pre-KRX", 3),
                 MDCELL(SIM, FUT, r"^\| mean margin requirement \| post-KRX", 3)), decimals=1,
            macro=r"\pctMarginSwing"),
        pct("margin.regime_split.table", "margin", "regime split as stated in the F1 table", "+30.0%", "+30.0%",
            MDCELL(SIM, FUT, r"^\| \(1\) \*\*Regime split", 3), decimals=1, scale=1.0),
        pct("margin.im_step", "margin", "the 13% → 17% IM step alone (F1)", "(shown as +30.0%)", "+30.8%",
            MDCELL(SIM, FUT, r"^\| \(2\) \*\*13% → 17% IM step", 3), decimals=1, scale=1.0),
        pct("margin.im_step.formula", "margin", "IM step = 17/13 − 1 (book-independent)", "—", "+30.8%",
            CALC(lambda a_, b_: b_ / a_ - 1, MDRE(SIM, FUT, r"(17,584,984)đ → 22,995,748đ"),
                 MDRE(SIM, FUT, r"17,584,984đ → (22,995,748)đ")), decimals=1),
    ]
    for hold, call_old, forced_old in ((5, "6.30%", "1.84%"), (10, "11.55%", "8.66%"), (20, "13.12%", "9.71%")):
        R.append(pct(f"margin.call.h{hold}", "margin", f"margin-call incidence, hold {hold}", call_old, call_old,
                     inc("margin-call", hold), decimals=2, scale=1.0,
                     macro={5: r"\pctCallFive", 20: r"\pctCallTwenty"}.get(hold, "")))
        R.append(pct(f"margin.forced.h{hold}", "margin", f"forced-close incidence, hold {hold}", forced_old,
                     forced_old, inc("forced-close", hold), decimals=2, scale=1.0))

    # ---- HSX daily --------------------------------------------------------------------------------------------
    adm = lambda k, f: J(SIM, f"{HSX}/equity_admission.json", k, f)
    band = lambda f: J(SIM, f"{HSX}/band_conformance.json", "HSX stock", f)
    gh = lambda f: J(SIM, f"{HSX}/grid_conformity_history.json", "HSX stocks", f)
    gw = lambda f: J(SIM, f"{HSX}/grid_conformity_window.json", "HSX stocks", f)
    R += [
        pct("hsx.admission.lag0", "hsx", "blocked entry, lag 0 (look-ahead)", "12.90%", "13.16%",
            adm("stocks_lag0", "rate"), decimals=2),
        num("hsx.admission.lag0.n", "hsx", "lag 0 attempts", "197,337", "205,755", adm("stocks_lag0", "attempts")),
        pct("hsx.admission.lag1", "hsx", "blocked entry, lag 1 (honest)", "5.84%", "6.03%",
            adm("stocks_lag1", "rate"), decimals=2),
        num("hsx.admission.lag1.n", "hsx", "lag 1 attempts", "197,521", "205,958", adm("stocks_lag1", "attempts")),
        pct("hsx.band.agree", "hsx", "band agreement, HSX stock", "97.59%", "91.90%", band("agreement_rate"),
            decimals=2, macro=r"\pctBandAgree"),
        pct("hsx.band.ci_lo", "hsx", "band agreement, Wilson 95% low", "97.52", "91.78%", band("ci_low"), decimals=2,
            macro=r"\ciBandAgree"),
        pct("hsx.band.ci_hi", "hsx", "band agreement, Wilson 95% high", "97.66", "92.03%", band("ci_high"), decimals=2,
            macro=r"\ciBandAgree"),
        num("hsx.band.n", "hsx", "band agreement, HSX stock ticker-days", "179,784", "182,367", band("rows"),
            macro=r"\nBandDays"),
        num("hsx.band.disagree", "hsx", "band disagreements", "4,324", "14,769", band("disagree")),
        num("hsx.band.disagree_same_width", "hsx", "disagreements with the band width right", "—", "2",
            band("disagree_same_width")),
        pct("hsx.grid.history", "hsx", "tick-grid conformity, library rule, all history", "99.999%", "99.9992%",
            gh("library_rate"), decimals=4, macro=r"\pctGridConform"),
        pct("hsx.grid.history.naive", "hsx", "tick-grid conformity, naive flat 0.1, all history", "84.51%", "85.38%",
            gh("naive_rate"), decimals=2, macro=r"\pctGridNaive"),
        num("hsx.grid.history.n", "hsx", "closes, all history", "1,086,518", "1,073,191", gh("observations")),
        pct("hsx.grid.window", "hsx", "tick-grid conformity, library rule, 2021–22", "(not measured)", "100.000%",
            gw("library_rate"), decimals=3),
        pct("hsx.grid.window.naive", "hsx", "tick-grid conformity, naive, 2021–22", "(not measured)", "72.94%",
            gw("naive_rate"), decimals=2),
        num("hsx.grid.window.n", "hsx", "closes, 2021–22", "—", "186,271", gw("observations")),
    ]

    # ---- T8 ---------------------------------------------------------------------------------------------------
    tot = r"^\| \*\*Total \(12 families\)\*\*"
    btot = r"^\| \*\*Total\*\* \| \*\*244\*\*"
    R += [
        num("t8.rule_versions", "t8", "enforced rule versions (runtime rulebook rows)", "97", "114",
            MDCELL(SIM, T8C, tot, 2), macro=r"\nRuleRows"),
        num("t8.rule_keys", "t8", "rule keys", "—", "93", MDCELL(SIM, T8C, tot, 1)),
        num("t8.rule_families", "t8", "rule families (tables)", "12", "12",
            MDRE(SIM, T8C, r"\*\*Total \((\d+) families\)\*\*"), macro=r"\nRuleTables"),
        num("t8.rule_high", "t8", "rule versions graded HIGH", "—", "87", MDCELL(SIM, T8C, tot, 4)),
        num("t8.rule_not_high", "t8", "rule versions graded MEDIUM, LOW or UNVERIFIED", "a handful", "27",
            CALC(lambda m, l, u: m + l + u, MDCELL(SIM, T8C, tot, 5), MDCELL(SIM, T8C, tot, 6),
                 MDCELL(SIM, T8C, tot, 7)), macro=r"\nEnforcedBelowHigh"),
        num("t8.rule_unknown", "t8", "rows that record an absence (UNKNOWN)", "11", "11", MDCELL(SIM, T8C, tot, 10)),
        num("t8.broker_fields", "t8", "broker fields", "244", "244", MDCELL(SIM, T8C, btot, 1)),
        num("t8.broker_published", "t8", "broker fields published by the firm", "—", "110", MDCELL(SIM, T8C, btot, 2)),
        num("t8.broker_supplied", "t8", "broker fields supplied by us (as shipped)", "—", "0",
            MDCELL(SIM, T8C, btot, 3), macro=r"\nBrokerSupplied"),
        num("t8.broker_inferred", "t8", "broker fields inferred", "—", "21", MDCELL(SIM, T8C, btot, 4)),
        num("t8.broker_unpublished", "t8", "broker fields recorded as not published", "—", "113",
            MDCELL(SIM, T8C, btot, 5)),
        num("t8.encoded_total", "t8", "rules + broker fields encoded in the engine", "341", "358",
            CALC(lambda r, b: r + b, MDCELL(SIM, T8C, tot, 2), MDCELL(SIM, T8C, btot, 1))),
        num("t8.maint.im.data", "t8", "IM 13% → 17%: rule-data lines", "—", "15",
            MDCELL(SIM, T8M, r"^\| VSD initial margin 13% -> 17%", 2), macro=r"\nMaintDataLines"),
        num("t8.maint.im.engine", "t8", "IM 13% → 17%: change-specific engine lines", "—", "0",
            MDCELL(SIM, T8M, r"^\| VSD initial margin 13% -> 17%", 4), macro=r"\nMaintCodeLines"),
        num("t8.maint.im.dup", "t8", "IM 13% → 17%: undated duplicate scalars", "—", "3",
            MDCELL(SIM, T8M, r"^\| VSD initial margin 13% -> 17%", 3)),
        num("t8.maint.lot.data", "t8", "HOSE lot 10 → 100: rule-data lines", "—", "13",
            MDCELL(SIM, T8M, r"^\| HOSE round lot 10 -> 100", 2)),
        num("t8.maint.lot.engine", "t8", "HOSE lot 10 → 100: engine lines", "—", "4",
            MDCELL(SIM, T8M, r"^\| HOSE round lot 10 -> 100", 4)),
        num("t8.maint.krx.data", "t8", "KRX cutover: rule-data lines", "—", "79",
            MDCELL(SIM, T8M, r"^\| KRX trading-system cutover", 2)),
        num("t8.maint.krx.engine", "t8", "KRX cutover: engine lines", "—", "20",
            MDCELL(SIM, T8M, r"^\| KRX trading-system cutover", 4)),
        pending("t8.validator.edges", "t8", "uncovered rule edges, all resolving to UNKNOWN", "—", "12",
                "Prose only (`docs/rivf26/NOTES-FOR-OWNER.md` §3.4, `LIMITATIONS.md` #8); pinned in "
                "`tests/market/session/test_rule_tables.py::OPEN_EDGES` but no committed result file."),
        pending("t8.properties", "t8", "Hypothesis properties", "—", "14",
                "Prose only (`NOTES-FOR-OWNER.md` §3.5). No committed result file; count from "
                "`tests/properties/` at freeze.", macro=r"\nProperties"),
        pending("t8.property_examples", "t8", "Hypothesis examples (plus 26 boundary cases)", "—", "3,850",
                "Prose only (`NOTES-FOR-OWNER.md` §3.5). No committed result file.", macro=r"\nPropertyExamples"),
        num("t8.bench.at_per_sec", "t8", "`Rulebook.at(ts)` resolutions per second (warm)", "—", "3,912,146",
            J(SIM, BENCH, "rulebook", "at_per_second"), tol=0.5, macro=r"\nAtPerSec"),
        num("t8.bench.orders_per_sec", "t8", "daily fill evaluations per second through `ExchangeSession`", "—",
            "13,223", J(SIM, BENCH, "daily", "fill_evaluations_per_second"), tol=0.5, macro=r"\nOrdersPerSec"),
        num("t8.bench.e1_wall", "t8", "E1 wall time, full 2022 population (s)", "—", "7.14",
            J(SIM, BENCH, "e1", "wall_s"), tol=0.005, macro=r"\EoneWall"),
        num("t8.bench.e1_rss", "t8", "E1 peak RSS (MB)", "—", "285.8", J(SIM, BENCH, "e1", "peak_rss_mb"), tol=0.05),
        Entry("t8.bench.commit", "t8", "benchmark ran on plutus-simulator", "—", "373f9a7", expected="373f9a7",
              get=J(SIM, BENCH, "machine", "plutus_simulator_commit")),
    ]

    # ---- Test counts ------------------------------------------------------------------------------------------
    freeze = ("To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4i (after `67f18fa`/`dcaecb9`: the 2 strict "
              "xfails now pass): 2,180 passed, 0 xfailed, 453 skipped. That count predates `tests/test_check_numbers.py` "
              "(`11ba6cd`, 7 tests) and any later commit.")
    R += [
        pending("tests.unit.passed", "tests", "unit tests passed", "1,646", "2,180", freeze, macro=r"\nUnitTests"),
        pending("tests.unit.xfailed", "tests", "unit tests xfailed (strict)", "—", "0", freeze),
        pending("tests.unit.skipped", "tests", "unit tests skipped (corpus-gated)", "—", "453", freeze),
        pending("tests.scenarios", "tests", "scenario tests passed (0 skipped)", "38", "39",
                "To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d.", macro=r"\nScenarioTests"),
        pending("tests.strategies.passed", "tests", "strategy tests passed", "11", "18",
                "To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d.", macro=r"\nStrategyTests"),
        pending("tests.strategies.skipped", "tests", "strategy tests skipped (E1, F2 need corpus slices)", "—", "2",
                "To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d."),
    ]

    # ---- Findings quoted in the text, no committed result file -----------------------------------------------
    nofile = "No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` %s) and the test only " \
             "pins it qualitatively. Needs a result file (or an exact pin) before freeze."
    R += [
        pending("s2.loss", "findings", "S2 leveraged long: loss", "—", "−77% (100M → 23.3M)", nofile % "§4b, §4d"),
        pending("s2.margin_calls", "findings", "S2 margin calls", "—", "10", nofile % "§4b, §4d"),
        pending("s2.forced_tranches", "findings", "S2 forced-sale tranches", "three sales", "7",
                nofile % "§4b", macro=r"\nStopSales"),
        pending("s2.queue_ahead", "findings", "S2 2022-11-07: floor queue ahead at 10:00 vs volume after", "—",
                "8,657,000 vs 775,000", nofile % "§4b (lock-queue table)"),
        pending("j18.deposit_step", "findings", "J18: deposit change at the 13% → 17% IM step", "—", "+30.8%",
                nofile % "§4d"),
    ]

    # ---- ProtoSmartBeta ---------------------------------------------------------------------------------------
    for w, nf, ff, fn_, hn, hf in (("w2022", "457", "457", "100.0%", "−26.21%", "−27.08%"),
                                   ("w2023", "727", "724", "99.6%", "+19.66%", "+17.68%")):
        r = f"result/null_anchor/{w}.json"
        R += [
            num(f"sb.{w}.fills_naive", "sb", f"{w}: naive fills", "—", nf, J("ProtoSmartBeta", r, "naive", "fills")),
            num(f"sb.{w}.fills_faithful", "sb", f"{w}: faithful fills", "2,257 (old OOS run)", ff,
                J("ProtoSmartBeta", r, "faithful", "fills")),
            pct(f"sb.{w}.fn", "sb", f"{w}: f/n fills", "—", fn_,
                J("ProtoSmartBeta", r, "comparison", "fill_ratio_f_over_n"), decimals=1, macro=r"\sbFillRange"),
            pct(f"sb.{w}.hpr_naive", "sb", f"{w}: HPR naive", "−3.17%", hn, J("ProtoSmartBeta", r, "naive", "hpr"),
                decimals=2, macro=r"\sbHPRRange"),
            pct(f"sb.{w}.hpr_faithful", "sb", f"{w}: HPR faithful", "−8.39%", hf,
                J("ProtoSmartBeta", r, "faithful", "hpr"), decimals=2, macro=r"\sbHPRRange"),
            num(f"sb.{w}.band_lock_no_fills", "sb", f"{w}: band-lock no-fills (of 10 candidates)", "0", "0",
                J("ProtoSmartBeta", r, "tier1", "band_lock_no_fills")),
        ]

    # ---- ProtoGrid --------------------------------------------------------------------------------------------
    for w, nf, ff, fn_, hn, hf, band_, unset, t2 in (
            ("w2022_10", "136", "62", "45.6%", "−2.40%", "−2.65%", "828", "58", "28"),
            ("w2021_11", "124", "57", "46.0%", "+1.47%", "+1.18%", "784", "68", "3")):
        r = f"result/grid_anchor/{w}.json"
        g = lambda *k: J("ProtoGrid", r, *k)
        R += [
            num(f"grid.{w}.fills_naive", "grid", f"{w}: naive fills", "1,457", nf, g("naive", "fills")),
            num(f"grid.{w}.fills_faithful", "grid", f"{w}: faithful fills", "151", ff, g("faithful", "fills")),
            pct(f"grid.{w}.fn", "grid", f"{w}: f/n fills", "≈10%", fn_, g("gap", "fill_ratio_f_over_n"), decimals=1,
                macro=r"\gridFillRange"),
            pct(f"grid.{w}.hpr_naive", "grid", f"{w}: HPR naive", "−19.0%", hn, g("naive", "hpr"), decimals=2,
                macro=r"\gridHPRRange"),
            pct(f"grid.{w}.hpr_faithful", "grid", f"{w}: HPR faithful", "−34.2%", hf, g("faithful", "hpr"), decimals=2,
                macro=r"\gridHPRRange"),
            num(f"grid.{w}.band_limit", "grid", f"{w}: BAND_LIMIT refusals", "—", band_,
                g("tier1", "band_limit_refusals")),
            num(f"grid.{w}.tick_grid", "grid", f"{w}: TICK_GRID refusals", "2,409", "0",
                g("tier1", "tick_grid_refusals")),
            num(f"grid.{w}.unsettled", "grid", f"{w}: UNSETTLED_HOLDING refusals (T+2)", "—", unset,
                g("tier1", "unsettled_holding_refusals")),
            num(f"grid.{w}.t2_locked", "grid", f"{w}: T+2-locked re-buys (INSUFFICIENT_CASH)", "248", t2,
                g("tier1", "t2_locked_rebuys")),
        ]
    R.append(pct("grid.min_fn", "grid", "Grid f/n, minimum over windows (abstract)", "≈10%", "45.6%",
                 CALC(min, J("ProtoGrid", "result/grid_anchor/w2022_10.json", "gap", "fill_ratio_f_over_n"),
                      J("ProtoGrid", "result/grid_anchor/w2021_11.json", "gap", "fill_ratio_f_over_n")),
                 decimals=1, macro=r"\gridFill"))

    # ---- ProtoPair --------------------------------------------------------------------------------------------
    for w, nf, ff, fn_, hn, hf, blk, want, nd, fg, sig, hfill, hind in (
            ("w1", "1,209", "651", "53.8%", "+1.03%", "−2.15%", "8", "10", "420", "9", "9", "583", "71"),
            ("w2", "775", "403", "52.0%", "+0.28%", "−0.31%", "4", "6", "180", "6", "6", "377", "27")):
        r = f"result/pair_anchor/{w}.json"
        p = lambda *k: J("ProtoPair", r, *k)
        R += [
            num(f"pair.{w}.fills_naive", "pair", f"{w}: naive fills", "2,298", nf, p("naive", "fills")),
            num(f"pair.{w}.fills_faithful", "pair", f"{w}: faithful fills", "1,236", ff, p("faithful", "fills")),
            pct(f"pair.{w}.fn", "pair", f"{w}: f/n fills", "53.8%", fn_, p("gap", "fills_f_over_n"), decimals=1,
                macro=r"\pairFillRange"),
            pct(f"pair.{w}.hpr_naive", "pair", f"{w}: HPR naive", "+3.5%", hn, p("gap", "hpr_naive_pct"), decimals=2,
                scale=1.0, macro=r"\pairHPRn" if w == "w1" else r"\pairHPRRange"),
            pct(f"pair.{w}.hpr_faithful", "pair", f"{w}: HPR faithful", "−3.2%", hf, p("gap", "hpr_faithful_pct"),
                decimals=2, scale=1.0, macro=r"\pairHPRf" if w == "w1" else r"\pairHPRRange"),
            num(f"pair.{w}.exits_blocked", "pair", f"{w}: exits blocked by T+2", "16", blk,
                p("tier1", "settlement_asymmetry", "exits_blocked_by_t2"), macro=r"\pairStuck"),
            num(f"pair.{w}.exits_wanted", "pair", f"{w}: exits wanted", "22", want,
                p("tier1", "settlement_asymmetry", "exits_wanted")),
            num(f"pair.{w}.name_days", "pair", f"{w}: name-days held open", "758", nd,
                p("tier1", "settlement_asymmetry", "name_days_held_open"), macro=r"\pairNameDays"),
            num(f"pair.{w}.forgone", "pair", f"{w}: opposite-side trades forgone", "17", fg,
                p("tier1", "opposite_side", "forgone"), macro=r"\pairSkipped"),
            num(f"pair.{w}.signalled", "pair", f"{w}: opposite-side trades signalled", "17", sig,
                p("tier1", "opposite_side", "mirror_trades_signalled")),
            num(f"pair.{w}.soft_undecided_events", "pair", f"{w}: fill-time undecided events, `soft`", "2.2%", "0",
                p("variants", "headline", "fill_time_indeterminate_events"), macro=r"\pctPairUndecSoft"),
            num(f"pair.{w}.hard_fills", "pair", f"{w}: `hard` variant fills", "0", hfill, p("variants", "hard", "fills")),
            num(f"pair.{w}.hard_undecided_events", "pair", f"{w}: fill-time undecided events, `hard`", "96.8%", hind,
                p("variants", "hard", "fill_time_indeterminate_events"), macro=r"\pctPairUndecHard",
                note="An event count; the old value was a rate. The result has no denominator for a `hard` rate."),
        ]
    R += [
        num("pair.w1.adf_p", "pair", "w1 basis ADF p-value", "—", "0.0000434",
            J("ProtoPair", "result/credibility/w1.json", "adf_pvalue"), tol=5e-8),
        num("pair.w2.adf_p", "pair", "w2 basis ADF p-value (does not reject a unit root)", "—", "0.537",
            J("ProtoPair", "result/credibility/w2.json", "adf_pvalue"), tol=0.0005),
    ]

    # ---- ProtoMarketMaker anchor (flat each session) ----------------------------------------------------------
    mk = lambda w, *k: J("ProtoMarketMaker", f"result/mm_anchor/{w}.json", *k)
    R += [
        num("mm.krx2025.fills_naive", "mm", "krx2025, all 40 sessions: naive fills", "910", "693",
            mk("krx2025", "naive", "fills")),
        pct("mm.krx2025.hpr_naive", "mm", "krx2025, 40 sessions: HPR naive", "56.75%", "+29.57%",
            mk("krx2025", "naive", "hpr"), decimals=2),
        num("mm.krx2025.fills_naive_pre", "mm", "krx2025, 20 pre-cutover sessions: naive fills", "—", "228",
            mk("krx2025", "naive_pre_cutover_only", "fills")),
        pct("mm.krx2025.hpr_naive_pre", "mm", "krx2025, pre-cutover: HPR naive", "—", "−5.22%",
            mk("krx2025", "naive_pre_cutover_only", "hpr"), decimals=2),
        num("mm.krx2025.fills_faithful", "mm", "krx2025, 40 sessions: faithful fills, conservative",
            "402 (submission); 116 (before the rerun)", "366", mk("krx2025", "faithful", "fills"), macro=r"\mmFillsF"),
        num("mm.krx2025.fills_opt", "mm", "krx2025, 40 sessions: faithful fills, optimistic", "160 (before the rerun)",
            "444", mk("krx2025", "faithful_by_queue", "optimistic", "fills"), macro=r"\mmFillsOpt"),
        pct("mm.krx2025.hpr_faithful", "mm", "krx2025, 40 sessions: HPR faithful, conservative",
            "31.62% (submission); −6.03% (before the rerun)", "−0.73%", mk("krx2025", "faithful", "hpr"), decimals=2),
        pct("mm.krx2025.fn", "mm", "krx2025: f/n, all 40 sessions", "44% (submission); 16.7% (before the rerun)",
            "52.8%", mk("krx2025", "fills_ratio_f_over_n"), decimals=1, macro=r"\mmFillRange"),
        num("mm.krx2025.fills_faithful_pre", "mm", "krx2025, 20 pre-cutover sessions: faithful fills, conservative",
            "116", "116", mk("krx2025", "faithful", "krx", "pre", "fills")),
        num("mm.krx2025.fills_faithful_post", "mm", "krx2025, 20 post-cutover sessions: faithful fills, conservative",
            "0 (refused, before the rerun)", "250", mk("krx2025", "faithful", "krx", "post", "fills")),
        pct("mm.krx2025.fn_pre", "mm", "krx2025: f/n, 20 pre-cutover sessions (like for like)", "50.9%", "50.9%",
            CALC(lambda f, n: f / n, mk("krx2025", "faithful", "krx", "pre", "fills"),
                 mk("krx2025", "naive_pre_cutover_only", "fills")), decimals=1, macro=r"\mmFillRange"),
        pct("mm.krx2025.queue_spread", "mm", "krx2025: queue spread (opt − cons) / opt", "27.5% (before the rerun)",
            "17.6%", mk("krx2025", "tier1", "queue_fill_spread", "conservative_vs_optimistic_pct"), decimals=1,
            scale=1.0, macro=r"\pctMMQueueSwing"),
        pct("mm.krx2025.undecided_pre", "mm", "krx2025: conservative undecided orders, pre-cutover",
            "99.94% (submission, events)", "99.76%", mk("krx2025", "faithful", "krx", "pre", "indeterminate_order_rate"),
            decimals=2, macro=r"\pctMMUndecPre",
            note="Counts orders; the submission's 99.94% / 99.92% counted fill-evaluation events."),
        pct("mm.krx2025.undecided_post", "mm", "krx2025: conservative undecided orders, post-cutover",
            "99.92% (submission, events); none (refused, before the rerun)", "99.21%",
            mk("krx2025", "faithful", "krx", "post", "indeterminate_order_rate"), decimals=2,
            macro=r"\pctMMUndecPost"),
        num("mm.krx2025.refused_post", "mm", "krx2025: post-cutover sessions refused (of 20)", "20 (before the rerun)",
            "0", mk("krx2025", "tier1", "post_cutover_refused_sessions")),
        Entry("mm.krx2025.engine_commit", "mm", "krx2025 anchor ran on plutus-simulator", "fc94743", "373f9a7",
              expected="373f9a7", get=CALC(lambda c: c[:7], mk("krx2025", "plutus_simulator_commit"),
                                           desc="`plutus_simulator_commit` (first 7 characters)")),
        num("mm.im2022.fills_naive", "mm", "im2022: naive fills", "—", "129", mk("im2022", "naive", "fills")),
        pct("mm.im2022.hpr_naive", "mm", "im2022: HPR naive", "—", "−12.93%", mk("im2022", "naive", "hpr"), decimals=2),
        num("mm.im2022.fills_faithful", "mm", "im2022: faithful fills, conservative", "—", "70",
            mk("im2022", "faithful", "fills")),
        num("mm.im2022.fills_opt", "mm", "im2022: faithful fills, optimistic", "—", "98",
            mk("im2022", "faithful_by_queue", "optimistic", "fills")),
        pct("mm.im2022.hpr_faithful", "mm", "im2022: HPR faithful, conservative (flat each session)", "—", "+2.19%",
            mk("im2022", "faithful", "hpr"), decimals=2),
        pct("mm.im2022.fn", "mm", "im2022: f/n", "—", "54.3%", mk("im2022", "fills_ratio_f_over_n"), decimals=1,
            macro=r"\mmFillRange"),
        pct("mm.im2022.queue_spread", "mm", "im2022: queue spread", "—", "28.6%",
            mk("im2022", "tier1", "queue_fill_spread", "conservative_vs_optimistic_pct"), decimals=1, scale=1.0),
        pct("mm.im2022.undecided_pre", "mm", "im2022: conservative undecided orders, before 2022-12-15", "—", "99.87%",
            mk("im2022", "faithful", "im_step", "pre", "indeterminate_order_rate"), decimals=2),
        pct("mm.im2022.undecided_post", "mm", "im2022: conservative undecided orders, from 2022-12-15", "—", "99.99%",
            mk("im2022", "faithful", "im_step", "post", "indeterminate_order_rate"), decimals=2),
        num("mm.deposit", "mm", "MM deposit (đ)", "—", "500,000,000", mk("im2022", "faithful", "deposit_dong"),
            macro=r"\mmDeposit"),
        num("mm.contracts_pre", "mm", "dated-IM capacity on 2022-12-14 (13%)", "37", "36",
            mk("im2022", "faithful", "capacity", ("date", "2022-12-14"), "contracts"), macro=r"\mmContractsPre"),
        num("mm.contracts_post", "mm", "dated-IM capacity on 2022-12-15 (17%)", "28", "28",
            mk("im2022", "faithful", "capacity", ("date", "2022-12-15"), "contracts"), macro=r"\mmContractsPost"),
    ]

    # ---- ProtoMarketMaker ladder ------------------------------------------------------------------------------
    PM = "ProtoMarketMaker"

    def _json_agrees(rs, text):
        n = 0
        for x in rs:
            v = x["hpr"] * 100
            sign = "-" if v < 0 else r"\+?"
            pat = rf"\| {re.escape(x['rung'])} \|.*\| {sign}{abs(v):.2f}% \|"
            n += any(re.match(pat, l) for l in text.splitlines())
        return n

    # im2022: the markdown's first table (whole window), cross-checked against the JSON.
    md = "result/mm_ladder/im2022.md"
    for rung, (hpr, fills_) in {"N0": ("−12.93%", "129"), "N1": ("−15.90%", "129"), "N2": ("−15.90%", "129"),
                                "N3": ("−16.42%", "129"), "F-opt": ("−2.52%", "198"),
                                "F-con": ("−11.47%", "116")}.items():
        row = rf"^\| {re.escape(rung)} \|"
        R.append(pct(f"ladder.im2022.{rung.lower()}.hpr", "ladder", f"im2022: {rung} HPR", "—", hpr,
                     MDCELL(PM, md, row, 5), decimals=2, scale=1.0))
        R.append(num(f"ladder.im2022.{rung.lower()}.fills", "ladder", f"im2022: {rung} fills", "—", fills_,
                     MDCELL(PM, md, row, 2)))

    # krx2025: whole window (40 sessions), and the pre-/post-cutover views, all from the JSON.
    KJ = "result/mm_ladder/krx2025.json"
    krx = {
        "": ("all 40 sessions", [], {"N0": ("+29.57%", "693"), "N1": ("−41.99%", "693"), "N2": ("−41.99%", "693"),
                                     "N3": ("−44.77%", "693"), "F-opt": ("−12.02%", "575"),
                                     "F-con": ("−42.96%", "358")}),
        "pre.": ("20 pre-cutover sessions", ["views", "pre_cutover"],
                 {"N0": ("−5.22%", "228"), "N1": ("−14.09%", "228"), "N2": ("−14.09%", "228"),
                  "N3": ("−15.02%", "228"), "F-opt": ("−7.58%", "261"), "F-con": ("−25.55%", "153")}),
        "post.": ("20 post-cutover sessions", ["views", "post_cutover"],
                  {"N0": ("+36.70%", "465"), "N1": ("−32.47%", "465"), "N2": ("−32.47%", "465"),
                   "N3": ("−35.01%", "465"), "F-opt": ("−4.81%", "314"), "F-con": ("−23.39%", "205")}),
    }
    pre_old = {"": "pre-cutover values (this id held the pre-cutover table before the rerun)", "pre.": "—",
               "post.": "— (refused before the rerun)"}
    for vid, (label, path, rungs) in krx.items():
        for rung, (hpr, fills_) in rungs.items():
            R.append(pct(f"ladder.krx2025.{vid}{rung.lower()}.hpr", "ladder", f"krx2025, {label}: {rung} HPR",
                          pre_old[vid] if vid == "post." else "—", hpr,
                          J(PM, KJ, *path, "rungs", ("rung", rung), "hpr"), decimals=2))
            R.append(num(f"ladder.krx2025.{vid}{rung.lower()}.fills", "ladder", f"krx2025, {label}: {rung} fills",
                         "—", fills_, J(PM, KJ, *path, "rungs", ("rung", rung), "fills")))
    fn_stated = {("im2022", "", "F-opt"): "153.5%", ("im2022", "", "F-con"): "89.9%",
                 ("krx2025", "", "F-opt"): "83.0%", ("krx2025", "", "F-con"): "51.7%",
                 ("krx2025", "pre.", "F-opt"): "114.5%", ("krx2025", "pre.", "F-con"): "67.1%",
                 ("krx2025", "post.", "F-opt"): "67.5%", ("krx2025", "post.", "F-con"): "44.1%"}
    for (w, vid, arm_), stated in fn_stated.items():
        if w == "im2022":
            f_, n_ = MDCELL(PM, md, rf"^\| {arm_} \|", 2), MDCELL(PM, md, r"^\| N0 \|", 2)
        else:
            path = krx[vid][1]
            f_ = J(PM, KJ, *path, "rungs", ("rung", arm_), "fills")
            n_ = J(PM, KJ, *path, "rungs", ("rung", "N0"), "fills")
        over = float(stated.rstrip("%")) > 100
        R.append(pct(f"ladder.{w}.{vid}{arm_.lower()}.fn", "ladder",
                     f"{w}{', ' + krx[vid][0] if w == 'krx2025' else ''}: {arm_} fills / N0 fills", "—", stated,
                     CALC(lambda f, n: f / n, f_, n_), decimals=1,
                     note="Above 100%: §6 criterion 1 (faithful fills < naive) fails for this arm." if over else ""))
    for w in ("im2022", "krx2025"):
        R.append(num(f"ladder.{w}.json_agrees", "ladder", f"{w}: ladder JSON HPRs equal the markdown's first table",
                     "—", "6", CALC(_json_agrees, J(PM, f"result/mm_ladder/{w}.json", "rungs"),
                                    Extractor(PM, f"result/mm_ladder/{w}.md", "",
                                              lambda c, w=w: c.text(PM, f"result/mm_ladder/{w}.md")),
                                    desc=f"`result/mm_ladder/{w}.json` `rungs[].hpr` vs `result/mm_ladder/{w}.md`")))
        for arm_ in ("F-opt", "F-con"):
            R.append(num(f"ladder.{w}.{arm_.lower()}.source_sha", "ladder",
                         f"{w}: {arm_} faithful-A result file matches the sha256 the ladder records", "—", "1",
                         SOURCE_SHA(PM, f"result/mm_ladder/{w}.json",
                                    ("faithful_sources", arm_, "sha256"), ("faithful_sources", arm_, "path"))))
    R += [
        pct("ladder.im2022.f-con.undecided", "ladder", "im2022: F-con undecided orders", "—", "99.88%",
            MDCELL(PM, md, r"^\| F-con \|", 7), decimals=2, scale=1.0),
        pct("ladder.krx2025.f-con.undecided", "ladder", "krx2025, all 40 sessions: F-con undecided orders",
            "99.63% (pre-cutover, before the rerun)", "99.54%",
            J(PM, KJ, "rungs", ("rung", "F-con"), "undecided_order_rate"), decimals=2),
        pct("ladder.krx2025.pre.f-con.undecided", "ladder", "krx2025, pre-cutover: F-con undecided orders", "99.63%",
            "99.63%", J(PM, KJ, "views", "pre_cutover", "rungs", ("rung", "F-con"), "undecided_order_rate"),
            decimals=2),
        num("ladder.krx2025.f-con.margin_calls", "ladder", "krx2025, all 40 sessions: F-con margin calls", "—", "31",
            J(PM, KJ, "rungs", ("rung", "F-con"), "margin_calls")),
        num("ladder.krx2025.f-con.forced_executed", "ladder", "krx2025: F-con forced liquidations executed", "—", "3",
            J(PM, KJ, "rungs", ("rung", "F-con"), "forced_liquidations_executed")),
    ]
    for arm_, nights in (("F-opt", "20"), ("F-con", "19")):
        a_ = arm_.lower()
        R += [
            num(f"ladder.krx2025.{a_}.ccp_nights", "ladder", f"krx2025: {arm_} post-KRX CCP nights with a position",
                "—", nights, J(PM, KJ, "rungs", ("rung", arm_), "ccp_nights")),
            num(f"ladder.krx2025.{a_}.ccp_indeterminate", "ladder", f"krx2025: {arm_} CCP nights indeterminate", "—",
                "0", J(PM, KJ, "rungs", ("rung", arm_), "ccp_indeterminate_nights")),
            num(f"ladder.krx2025.{a_}.ccp_calendar_unknown", "ladder",
                f"krx2025: {arm_} calendar-spread charge UNKNOWN", "—", "0",
                J(PM, KJ, "rungs", ("rung", arm_), "ccp_calendar_spread_unknown")),
        ]
    mo = lambda w, arm_, h: J(PM, f"result/mm_markout/{w}_markout.json", "arms", arm_, "markout_mean_points", h)
    for w, label, vals in (("im2022", "im2022, all 40 sessions", ("−0.71", "+0.41", "−0.57")),
                           ("krx2025", "krx2025, all 40 sessions", ("−2.22", "−0.68", "−0.31"))):
        for arm_, v in zip(("N3", "F-opt", "F-con"), vals):
            R.append(num(f"ladder.markout.{w}.{arm_.lower()}.5m", "ladder",
                         f"{label}: mean 5-min markout per fill, {arm_} (index pts; + good for the maker)",
                         "−2.24 naive / −0.78 faithful (first 6 im2022 sessions, prose)" if w == "im2022" and
                         arm_ == "N3" else "—", v, mo(w, arm_, "5m"), tol=0.005))
    for w, v in (("im2022", "+0.21"), ("krx2025", "+0.06")):
        R.append(num(f"ladder.markout.{w}.f-opt.1m", "ladder",
                     f"{w}: mean 1-min markout per fill, F-opt (record for the WITHDRAWN 'no ghost fills' claim)",
                     "—", v, mo(w, "F-opt", "1m"), tol=0.005,
                     note="Withdrawn claim: kept as the record only; the paper does not state 'no ghost fills'."))

    # ---- Slice integrity ----------------------------------------------------------------------------------------
    for m in ("scenarios/fixtures/daily/DATA-MANIFEST.md", "scenarios/fixtures/book/DATA-MANIFEST.md",
              "strategies/fixtures/parquet/DATA-MANIFEST.md", "strategies/fixtures/s2_lock/daily/DATA-MANIFEST.md",
              "strategies/fixtures/s2_lock/book/DATA-MANIFEST.md",
              "tests/market/session/fixtures/book_walk/DATA-MANIFEST.md"):
        n = {"scenarios/fixtures/daily": 9, "scenarios/fixtures/book": 12, "strategies/fixtures/parquet": 9,
             "strategies/fixtures/s2_lock/daily": 4, "strategies/fixtures/s2_lock/book": 4,
             "tests/market/session/fixtures/book_walk": 8}[m.rsplit("/", 1)[0]]
        R.append(num("slice.sim." + m.rsplit("/", 1)[0].replace("/", "."), "slices",
                     f"`{m}`: files matching sha256", "—", str(n), SLICE(SIM, m)))
    proto_manifests = [
        ("ProtoSmartBeta", "data/market/w2022/DATA-MANIFEST.md", 9, ()),
        ("ProtoSmartBeta", "data/market/w2023/DATA-MANIFEST.md", 9, ()),
        ("ProtoSmartBeta", "data/signal/w2022/DATA-MANIFEST.md", 1, ("quote_ticker.parquet",)),
        ("ProtoSmartBeta", "data/signal/w2023/DATA-MANIFEST.md", 1, ("quote_ticker.parquet",)),
        ("ProtoSmartBeta", "data/signal/w2022/DATA-MANIFEST-financial.md", 1, ()),
        ("ProtoSmartBeta", "data/signal/w2023/DATA-MANIFEST-financial.md", 1, ()),
        ("ProtoPair", "data/market/w1/DATA-MANIFEST.md", 11, ()),
        ("ProtoPair", "data/market/w2/DATA-MANIFEST.md", 11, ()),
        ("ProtoGrid", "data/manifest/w2021_11/DATA-MANIFEST.md", 8, ()),
        ("ProtoGrid", "data/manifest/w2022_10/DATA-MANIFEST.md", 8, ()),
        ("ProtoMarketMaker", "data/im2022-MANIFEST.md", 12, ()),
        ("ProtoMarketMaker", "data/krx2025-MANIFEST.md", 12, ()),
    ]
    for repo, m, n, allow in proto_manifests:
        sid = "slice." + repo.lower().replace("proto", "") + "." + m.replace("data/", "").replace("/", ".") \
            .replace("DATA-MANIFEST", "manifest").replace(".md", "").replace("-MANIFEST", ".manifest")
        R.append(num(sid, "slices", f"{repo} `{m}`: files matching sha256", "—", str(n), SLICE(repo, m, allow),
                     note="The manifest lists an empty (0-row) ticker master that was not copied into the repo."
                     if allow else ""))
    for w, n in (("w2022", 11), ("w2023", 11)):
        R.append(num(f"slice.smartbeta.result.{w}", "slices", f"SB `result/null_anchor/{w}.json` recorded slice sha256 "
                     "match the committed files", "—", str(n),
                     RESULT_SLICES("ProtoSmartBeta", f"result/null_anchor/{w}.json", "provenance", "slices")))
    for w in ("w1", "w2"):
        R.append(num(f"slice.pair.result.{w}", "slices", f"Pair `result/pair_anchor/{w}.json` recorded slice sha256 "
                     "match the committed files", "—", "11",
                     RESULT_SLICES("ProtoPair", f"result/pair_anchor/{w}.json", "slice", base=f"data/market/{w}")))
    return R


REGISTRY: list[Entry] = _registry()


# --------------------------------------------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------------------------------------------

def _compare(e: Entry, value: Any) -> bool:
    if isinstance(e.expected, str):
        return str(value) == e.expected
    return abs(float(value) * e.scale - float(e.expected)) <= e.tol + 1e-9 * max(1.0, abs(float(e.expected)))


def run(entries: list[Entry], *, repo_root: Path = REPO, proto_root: Path | None = None,
        skip_missing_proto: bool = False) -> list[Result]:
    proto_root = Path(proto_root) if proto_root is not None else (Path(repo_root) / DEFAULT_PROTO_ROOT)
    ctx = Ctx(Path(repo_root), proto_root)
    out: list[Result] = []
    for e in entries:
        if e.status == "pending":
            out.append(Result(e, "PENDING", e.new, e.note))
            continue
        src = e.get.src if e.get is not None else SIM
        if src != SIM and skip_missing_proto and not proto_root.is_dir():
            out.append(Result(e, "SKIP", None, "proto root not present"))
            continue
        try:
            value = e.get(ctx)
        except FileNotFoundError as x:
            out.append(Result(e, "FAIL", None, f"missing file {x}"))
            continue
        except CheckError as x:
            out.append(Result(e, "FAIL", None, str(x)))
            continue
        ok = _compare(e, value)
        shown = value * e.scale if isinstance(value, float) and e.scale != 1 else value
        out.append(Result(e, "PASS" if ok else "FAIL", value,
                          "" if ok else f"source gives {shown!r}, stated {e.new} (tol {e.tol})"))
    return out


def summary(results: list[Result]) -> str:
    c = {v: sum(r.verdict == v for r in results) for v in ("PASS", "FAIL", "PENDING", "SKIP")}
    return (f"{len(results)} entries: {c['PASS']} PASS, {c['FAIL']} FAIL, {c['PENDING']} PENDING, "
            f"{c['SKIP']} SKIP")


# --------------------------------------------------------------------------------------------------------------
# Markdown (the generated block of the headline map)
# --------------------------------------------------------------------------------------------------------------

def _commit(root: Path, rel: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "log", "-1", "--format=%h", "--", rel],
                                       text=True, stderr=subprocess.DEVNULL).strip() or "uncommitted"
    except Exception:
        return "?"


def _head(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "?"


def markdown(results: list[Result], ctx: Ctx) -> str:
    esc = lambda s: str(s).replace("\\|", "|").replace("|", "\\|")   # a regex's \| shows as one escaped pipe
    lines: list[str] = []
    for gid, g in GROUPS.items():
        rs = [r for r in results if r.entry.group == gid]
        if not rs:
            continue
        repo_name = "plutus-simulator" if g.repo == SIM else g.repo
        lines += [f"### {g.title}", "",
                  f"- **Repo:** `{repo_name}` (branch `rivf26`, HEAD `{_head(ctx.root(g.repo))}` when generated)",
                  f"- **Command:** {g.command}", f"- **Data slice:** {g.slice}", "",
                  "| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |",
                  "|---|---|---|---|---|---|"]
        for r in rs:
            e = r.entry
            if e.get is not None:
                root = ctx.root(e.get.src)
                where = (f"`{e.get.path}` @ `{_commit(root, e.get.path)}` :: "
                         f"{e.source or e.get.desc}")
                if e.get.src != SIM:
                    where = f"{e.get.src}: " + where
            else:
                where = "—"
            old = e.old if e.old not in ("", "—") else "—"
            val = f"{old} → **{e.new}**" if old != e.new else f"**{e.new}** (unchanged)"
            check = r.verdict + (f": {e.note}" if e.note else "")
            macro = f"`{e.macro}`" if e.macro else ""
            lines.append(f"| `{e.id}` | {macro} | {esc(e.claim)} | {esc(val)} | {esc(where)} | {esc(check)} |")
        lines.append("")
    return "\n".join(lines)


def write_doc(md: str, doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    i, j = text.index(BEGIN), text.index(END)
    doc.write_text(text[: i + len(BEGIN)] + "\n\n" + md + "\n" + text[j:], encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--proto-root", type=Path, default=None,
                    help="directory holding the Proto* repos (default: ../proto relative to this repo)")
    ap.add_argument("--only", default="", help="check only entries whose id starts with this prefix")
    ap.add_argument("--skip-missing-proto", action="store_true",
                    help="report proto entries as SKIP when the proto root does not exist")
    ap.add_argument("--json", type=Path, help="also write the results as JSON")
    ap.add_argument("--markdown", action="store_true", help="print the headline-map tables")
    ap.add_argument("--write-doc", action="store_true", help=f"rewrite the generated block of {DOC}")
    a = ap.parse_args(argv)
    proto = a.proto_root if a.proto_root is not None else (REPO / DEFAULT_PROTO_ROOT)
    entries = [e for e in REGISTRY if e.id.startswith(a.only)]
    results = run(entries, repo_root=REPO, proto_root=proto, skip_missing_proto=a.skip_missing_proto)
    if a.markdown or a.write_doc:
        md = markdown(results, Ctx(REPO, proto))
        if a.write_doc:
            write_doc(md, REPO / DOC)
        if a.markdown:
            print(md)
    else:
        w = max(len(e.id) for e in entries) if entries else 10
        for r in results:
            v = r.value
            if isinstance(v, float) and r.entry.scale != 1:
                v = round(v * r.entry.scale, 6)
            extra = r.detail if r.verdict != "PASS" else ""
            print(f"{r.verdict:<7} {r.entry.id:<{w}}  stated {r.entry.new:<22} source {v!s:<22} {extra}".rstrip())
    print(summary(results))
    if a.json:
        a.json.write_text(json.dumps([{"id": r.entry.id, "verdict": r.verdict, "stated": r.entry.new,
                                       "value": r.value, "detail": r.detail} for r in results], indent=1,
                                     default=str))
    return 1 if any(r.verdict == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
