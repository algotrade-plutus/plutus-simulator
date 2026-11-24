"""T8.5 -- maintenance effort: rule data vs engine code for real dated changes.

The question (RIVF'26 camera-ready, reviewer R1): *what does it cost to add a
dated rule change?* If rules really are data, a dated change should be a few
lines of table rows and citations and close to zero lines of engine code.

**What git history can and cannot show here -- read this first.** No dated
change in this repository was ever added *after* the mechanism that carries it
existed. ``src/plutus/market/session/rulebook.py`` has five commits in all
(``b737f6f`` creates it with 464 lines, ``7ee32b9`` adds 1,913, ``7b56e95`` 327,
``bc7f793`` 150, ``a95d59f`` one path line), and every dated row arrived in one
of those bulk commits together with the resolver, the session and their tests.
The dated series outside the rulebook (``margin.VSD_INITIAL_MARGIN``,
``core.constant.get_trading_unit``) arrived in ``0d91323``, a commit that fixed
six unrelated defects at once. So a per-commit diff count would measure "build
the mechanism and five other things", not "add one dated change", and is not
reported as if it were.

What *can* be shown cleanly, and what this script computes:

1. **The footprint today.** For each change, the source lines at ``HEAD`` that
   encode it, found by an anchor (the date, or the constant that names it) and
   expanded to a syntactic unit with :mod:`ast`:

   * ``rule_data``  -- the dated row(s) themselves: a ``_interval``/``_unsourced``
     /``RuleCitation`` call (value, dates, document, article, confidence, note),
     a dated tuple element, or the module constant naming the date.
   * ``dup_scalar`` -- an *undated* copy of the same value elsewhere (a default
     or a guard constant). Zero for a clean change; each one is a line a future
     step must remember to touch.
   * ``engine_specific`` -- code (comments and docstrings excluded) that names
     this change: a branch on its date, a call that switches on the edition.
   * ``mechanism`` -- the per-family resolver the change needed the first time
     (the function that looks up the dated series). Shared by every past and
     future step of that rule, so it is reported apart from the per-change cost.
   * ``tests`` -- whole test functions (``tests/``, ``scenarios/``,
     ``strategies/``) that name the date or its constant.

2. **Which commits wrote those lines**, by ``git blame -w -M`` on exactly those
   lines, and how big each of those commits was overall -- which is the
   entanglement, shown rather than asserted.

Anchors find only code that *names* a change. Engine work a change motivated
without naming it -- above all the post-KRX margin model in
``scenario_margin.py`` -- is not counted here, and the table says so.

The 2016-09-12 HOSE tick change is not encoded anywhere in ``src/`` (the
rulebook window starts 2020-01-01, ``rulebook.COVERAGE_START``), so it cannot be
measured; the script checks that and reports it.

Run::

    PYTHONPATH=src python measurements/maintenance_effort.py          # table
    PYTHONPATH=src python measurements/maintenance_effort.py --markdown
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]

ROW_FUNCS = {'_interval', '_unsourced', 'RuleCitation'}
TEST_ROOTS = ('tests', 'scenarios', 'strategies')
CLASSES = ('rule_data', 'dup_scalar', 'engine_specific', 'mechanism', 'tests')


@dataclass(frozen=True)
class Anchor:
    path: str
    pattern: str


@dataclass(frozen=True)
class Mechanism:
    path: str
    qualname: str   # 'func' or 'Class.method'


@dataclass
class Change:
    key: str
    title: str
    effective: str
    rule_data: Sequence[Anchor]
    dup_scalar: Sequence[Anchor] = ()
    engine_specific: Sequence[Anchor] = ()
    mechanism: Sequence[Mechanism] = ()
    test_pattern: str = ''
    unanchored_note: str = ''


RB = 'src/plutus/market/session/rulebook.py'
BP = 'src/plutus/market/session/broker_profile.py'
MARGIN = 'src/plutus/market/margin.py'
CONST = 'src/plutus/core/constant.py'
EXCH = 'src/plutus/market/session/exchange.py'
CORP = 'src/plutus/market/session/corporate.py'

CHANGES: Tuple[Change, ...] = (
    Change(
        key='vsd_im_2022_12_15',
        title='VSD initial margin 13% -> 17% (HNXDS index futures)',
        effective='2022-12-15',
        rule_data=(
            Anchor(MARGIN, r'\(date\(2022, 12, 15\), Decimal'),
            Anchor(RB, r"17% from '"),
        ),
        dup_scalar=(
            Anchor(MARGIN, r"vsd_initial: Decimal = Decimal\('0\.17'\)"),
            Anchor(MARGIN, r"maintenance_rate: Decimal = Decimal\('0\.17'\)"),
            Anchor(BP, r"^VSDC_INITIAL_MARGIN_RATIO = "),
        ),
        engine_specific=(),
        mechanism=(
            Mechanism(MARGIN, 'vsd_initial_margin'),
            Mechanism(RB, 'RuleSet.initial_margin_rate'),
        ),
        test_pattern=r'2022, 12, 15',
    ),
    Change(
        key='hsx_lot_2021_01_04',
        title='HOSE round lot 10 -> 100 shares',
        effective='2021-01-04',
        rule_data=(
            Anchor(CONST, r'HSX_ROUND_LOT_RAISED = datetime\.date'),
            Anchor(RB, r'HOSE 10 -> 100 step at 2021-01-04\. '),
        ),
        engine_specific=(
            Anchor(CONST, r'and on < VietnamMarketConstant\.HSX_ROUND_LOT_RAISED'),
        ),
        mechanism=(
            Mechanism(CONST, 'get_trading_unit'),
            Mechanism(RB, 'RuleSet.trading_unit'),
        ),
        test_pattern=r'2021, 1, 4|HSX_ROUND_LOT_RAISED',
    ),
    Change(
        key='krx_cutover_2025_05_05',
        title='KRX trading-system cutover (HOSE/HNX rule set)',
        effective='2025-05-05',
        rule_data=(
            Anchor(RB, r'^KRX_CUTOVER = date'),
            Anchor(RB, r'_interval\(.*KRX_CUTOVER|_unsourced\(KRX_CUTOVER'),
            Anchor(BP, r'^KRX_CUTOVER = date'),
            Anchor(CORP, r'effective_from=date\(2025, 5, 5\)'),
        ),
        engine_specific=(
            Anchor(RB, r'ts\.date\(\) >= KRX_CUTOVER'),
            Anchor(EXCH, r'edition_at\('),
            Anchor(BP, r'if self\.regime is Regime\.PRE_KRX:'),
        ),
        mechanism=(
            Mechanism(RB, 'Rulebook.edition_at'),
        ),
        test_pattern=r'KRX_CUTOVER|2025, 5, 5',
        unanchored_note=(
            'Not counted: the post-KRX margin model (scenario_margin.py, '
            '~3,000 lines) and the broker-profile regime machinery, which the '
            'cutover motivated but which do not name its date. The KRX cutover '
            'is a rule SET: these rows are the dated rows that name it.'),
    ),
)


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def blame(path: str, lines: Sequence[int]) -> Dict[int, str]:
    """``{line: short sha}`` for ``lines`` of ``path`` at HEAD."""
    out: Dict[int, str] = {}
    for start, end in _runs(sorted(set(lines))):
        text = git('blame', '-w', '-M', '--line-porcelain',
                   '-L', f'{start},{end}', 'HEAD', '--', path)
        line_no = None
        for row in text.splitlines():
            m = re.match(r'^([0-9a-f]{40}) \d+ (\d+)', row)
            if m:
                line_no = int(m.group(2))
                out[line_no] = m.group(1)[:7]
    return out


def _runs(xs: Sequence[int]) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    for x in xs:
        if runs and x == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], x)
        else:
            runs.append((x, x))
    return runs


def commit_info(sha: str) -> Tuple[str, str, int, int, int]:
    """(date, subject, files, added, deleted) for the whole commit."""
    head = git('show', '-s', '--format=%ad%x09%s', '--date=short', sha).strip()
    date_s, subject = head.split('\t', 1)
    added = deleted = files = 0
    for row in git('show', '--numstat', '--format=', sha).splitlines():
        parts = row.split('\t')
        if len(parts) == 3:
            files += 1
            if parts[0] != '-':
                added += int(parts[0])
                deleted += int(parts[1])
    return date_s, subject, files, added, deleted


# ---------------------------------------------------------------------------
# source-unit helpers
# ---------------------------------------------------------------------------

class Source:
    """One file at HEAD: its lines, its AST, and which lines are not code."""

    def __init__(self, path: str):
        self.path = path
        text = git('show', f'HEAD:{path}')
        self.lines = text.splitlines()
        self.tree = ast.parse(text)
        self.parents: Dict[ast.AST, ast.AST] = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
        self.docstring_lines: Set[int] = set()
        for node in ast.walk(self.tree):
            body = getattr(node, 'body', None)
            if isinstance(body, list):
                for stmt in body:
                    if (isinstance(stmt, ast.Expr)
                            and isinstance(stmt.value, ast.Constant)
                            and isinstance(stmt.value.value, str)):
                        self.docstring_lines.update(
                            range(stmt.lineno, stmt.end_lineno + 1))

    def find(self, pattern: str) -> List[int]:
        rx = re.compile(pattern)
        return [i + 1 for i, line in enumerate(self.lines) if rx.search(line)]

    def _spans(self, line: int, pred) -> List[ast.AST]:
        return [n for n in ast.walk(self.tree)
                if hasattr(n, 'lineno') and n.lineno <= line <= n.end_lineno
                and pred(n)]

    @staticmethod
    def _smallest(nodes: List[ast.AST]) -> Optional[ast.AST]:
        return min(nodes, key=lambda n: n.end_lineno - n.lineno, default=None)

    def data_unit(self, line: int) -> Tuple[int, int]:
        """The dated row containing ``line``: a row call, a dated tuple
        element, or the assignment statement."""
        def is_row(n):
            return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id in ROW_FUNCS)
        node = self._smallest(self._spans(line, is_row))
        if node is None:
            node = self._smallest(self._spans(
                line, lambda n: isinstance(n, ast.Tuple)
                and isinstance(self.parents.get(n), ast.Tuple)))
        if node is None:
            node = self._smallest(self._spans(
                line, lambda n: isinstance(n, (ast.Assign, ast.AnnAssign))))
        if node is None:
            return line, line
        return node.lineno, node.end_lineno

    def stmt_unit(self, line: int) -> Tuple[int, int]:
        """The smallest statement containing ``line`` (an ``if`` whose test is
        on ``line`` comes with its body)."""
        node = self._smallest(self._spans(
            line, lambda n: isinstance(n, ast.stmt)
            and not isinstance(n, (ast.FunctionDef, ast.ClassDef,
                                   ast.AsyncFunctionDef))))
        if node is None:
            return line, line
        return node.lineno, node.end_lineno

    def function(self, qualname: str) -> Tuple[int, int]:
        parts = qualname.split('.')
        scope: Sequence[ast.AST] = self.tree.body
        node = None
        for part in parts:
            node = next(n for n in scope
                        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                        and n.name == part)
            scope = node.body
        return node.lineno, node.end_lineno

    def test_functions(self, pattern: str) -> List[Tuple[int, int]]:
        rx = re.compile(pattern)
        out = []
        for node in ast.walk(self.tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith('test')):
                body = '\n'.join(self.lines[node.lineno - 1:node.end_lineno])
                if rx.search(body):
                    start = min([d.lineno for d in node.decorator_list]
                                + [node.lineno])
                    out.append((start, node.end_lineno))
        # drop nested duplicates
        out.sort()
        kept: List[Tuple[int, int]] = []
        for span in out:
            if kept and span[1] <= kept[-1][1]:
                continue
            kept.append(span)
        return kept

    def countable(self, start: int, end: int, *, code_only: bool) -> List[int]:
        keep = []
        for ln in range(start, end + 1):
            text = self.lines[ln - 1].strip()
            if not text:
                continue
            if code_only and (text.startswith('#')
                              or ln in self.docstring_lines):
                continue
            keep.append(ln)
        return keep


_SOURCES: Dict[str, Source] = {}


def source(path: str) -> Source:
    if path not in _SOURCES:
        _SOURCES[path] = Source(path)
    return _SOURCES[path]


def test_files() -> List[str]:
    files = git('ls-files', '--', *TEST_ROOTS).split()
    return [f for f in files if f.endswith('.py')]


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------

@dataclass
class Footprint:
    change: Change
    # class -> {(path, line)}
    lines: Dict[str, Set[Tuple[str, int]]] = field(
        default_factory=lambda: {c: set() for c in CLASSES})
    units: Dict[str, int] = field(default_factory=Counter)
    blame: Dict[Tuple[str, int], str] = field(default_factory=dict)

    def count(self, cls: str) -> int:
        return len(self.lines[cls])

    def by_commit(self, cls: str) -> Counter:
        return Counter(self.blame[k] for k in self.lines[cls])


def measure(change: Change) -> Footprint:
    fp = Footprint(change)

    def add(cls: str, path: str, span: Tuple[int, int], *, code_only: bool):
        src = source(path)
        for ln in src.countable(*span, code_only=code_only):
            fp.lines[cls].add((path, ln))
        fp.units[cls] += 1

    for a in change.rule_data:
        hits = source(a.path).find(a.pattern)
        if not hits:
            raise SystemExit(f'{change.key}: rule-data anchor {a} found nothing')
        spans = {source(a.path).data_unit(h) for h in hits}
        for span in sorted(spans):
            add('rule_data', a.path, span, code_only=False)

    for a in change.dup_scalar:
        hits = source(a.path).find(a.pattern)
        if not hits:
            raise SystemExit(f'{change.key}: dup-scalar anchor {a} found nothing')
        for span in sorted({source(a.path).stmt_unit(h) for h in hits}):
            add('dup_scalar', a.path, span, code_only=True)

    data_lines = set(fp.lines['rule_data'])
    for a in change.engine_specific:
        src = source(a.path)
        hits = [h for h in src.find(a.pattern)
                if h not in src.docstring_lines
                and not src.lines[h - 1].strip().startswith('#')
                and (a.path, h) not in data_lines]
        if not hits:
            raise SystemExit(f'{change.key}: engine anchor {a} found nothing')
        for span in sorted({src.stmt_unit(h) for h in hits}):
            add('engine_specific', a.path, span, code_only=True)

    for m in change.mechanism:
        span = source(m.path).function(m.qualname)
        add('mechanism', m.path, span, code_only=True)
    # the mechanism excludes lines already counted as change-specific
    fp.lines['mechanism'] -= fp.lines['engine_specific']

    for path in test_files():
        try:
            src = source(path)
        except SyntaxError:
            continue
        for span in src.test_functions(change.test_pattern):
            add('tests', path, span, code_only=False)

    by_path: Dict[str, List[int]] = {}
    for cls in CLASSES:
        for path, ln in fp.lines[cls]:
            by_path.setdefault(path, []).append(ln)
    for path, lns in by_path.items():
        for ln, sha in blame(path, lns).items():
            fp.blame[(path, ln)] = sha
    return fp


def tick_2016_encoded() -> bool:
    pattern = r'2016, 9, 12|2016-09-12'
    files = [f for f in git('ls-files', '--', 'src').split()
             if f.endswith('.py')]
    return any(source(f).find(pattern) for f in files)


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def _fmt_commits(c: Counter) -> str:
    return ', '.join(f'`{sha}` {n}' for sha, n in c.most_common()) or '--'


def render(footprints: Sequence[Footprint], *, markdown: bool) -> str:
    out: List[str] = []
    w = out.append
    w('| Change | Effective | Rule data | Undated duplicate scalars | '
      'Engine, change-specific | Engine, per-family resolver (shared) | '
      'Tests |')
    w('|---|---|---:|---:|---:|---:|---:|')
    for fp in footprints:
        c = fp.change
        w(f'| {c.title} | {c.effective} | {fp.count("rule_data")} '
          f'({fp.units["rule_data"]} units) | {fp.count("dup_scalar")} | '
          f'{fp.count("engine_specific")} | {fp.count("mechanism")} | '
          f'{fp.count("tests")} ({fp.units["tests"]} test fns) |')
    w('')
    w('Lines are non-blank source lines at `HEAD`. Rule data counts the whole '
      'row (value, dates, document, article, confidence, note); a unit is one '
      'dated row, dated tuple element, citation or date constant. Engine '
      'counts exclude comments and docstrings; the resolver column excludes '
      'lines already counted as change-specific.')
    w('')
    w('### Which commits wrote those lines (`git blame -w -M`)')
    w('')
    w('| Change | Class | Lines by commit |')
    w('|---|---|---|')
    shas: Set[str] = set()
    for fp in footprints:
        for cls in CLASSES:
            bc = fp.by_commit(cls)
            shas.update(bc)
            if bc:
                w(f'| {fp.change.key} | {cls} | {_fmt_commits(bc)} |')
    w('')
    w('### How large those commits were (entanglement)')
    w('')
    w('| Commit | Date | Files | +lines | -lines | Subject |')
    w('|---|---|---:|---:|---:|---|')
    for sha in sorted(shas, key=lambda s: commit_info(s)[0]):
        d, subj, files, a, dl = commit_info(sha)
        w(f'| `{sha}` | {d} | {files} | {a} | {dl} | {subj} |')
    w('')
    for fp in footprints:
        if fp.change.unanchored_note:
            w(f'- **{fp.change.key}**: {fp.change.unanchored_note}')
    w(f'- **HOSE tick change 2016-09-12**: encoded in `src/`: '
      f'{"yes" if tick_2016_encoded() else "no"} -- outside the rulebook '
      f'window (COVERAGE_START 2020-01-01), so not measurable.')
    w('')
    if not markdown:
        w('Per-class line lists:')
        for fp in footprints:
            for cls in CLASSES:
                spans: Dict[str, List[int]] = {}
                for p, ln in sorted(fp.lines[cls]):
                    spans.setdefault(p, []).append(ln)
                for p, lns in spans.items():
                    rng = ', '.join(f'{a}-{b}' if a != b else str(a)
                                    for a, b in _runs(lns))
                    w(f'  {fp.change.key:24s} {cls:16s} {p}:{rng}')
    return '\n'.join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--markdown', action='store_true',
                    help='emit only the markdown tables')
    args = ap.parse_args(argv)
    print(f'Measured at HEAD `{git("rev-parse", "--short", "HEAD").strip()}`.')
    print()
    footprints = [measure(c) for c in CHANGES]
    print(render(footprints, markdown=args.markdown))
    return 0


if __name__ == '__main__':
    sys.exit(main())
