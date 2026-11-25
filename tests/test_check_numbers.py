"""The camera-ready headline-number checker (``measurements/check_numbers.py``).

It reads committed result files only (this repo, and the proto strategy repos via ``--proto-root``) and
reports PASS / FAIL / PENDING per registered number. These tests pin that it finds no FAIL on the
committed results, that it does catch a wrong value, and that the headline map lists every entry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from measurements import check_numbers as cn

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "camera-ready-numbers.md"


def _proto_root() -> Path:
    return (REPO / cn.DEFAULT_PROTO_ROOT).resolve()


def _run_all():
    proto = _proto_root()
    return cn.run(cn.REGISTRY, repo_root=REPO, proto_root=proto, skip_missing_proto=not proto.is_dir())


def test_registry_is_well_formed():
    ids = [e.id for e in cn.REGISTRY]
    assert len(ids) == len(set(ids)), "duplicate entry ids"
    assert len(ids) >= 100
    for e in cn.REGISTRY:
        assert re.fullmatch(r"[a-z0-9_.\-]+", e.id), e.id
        assert e.status in {"check", "pending"}, e.id
        assert e.group in cn.GROUPS, (e.id, e.group)
        if e.status == "check":
            assert e.get is not None, e.id
        else:
            assert e.note, f"{e.id}: a pending entry must say why"


def test_no_fail_on_committed_results():
    results = _run_all()
    fails = [(r.entry.id, r.detail) for r in results if r.verdict == "FAIL"]
    assert not fails, fails
    verdicts = {r.verdict for r in results}
    assert "PASS" in verdicts   # PENDING is allowed but no longer expected: every number has a source


def test_a_wrong_value_fails(tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({"a": {"b": 0.3143}}))
    good = cn.Entry("t.good", "e1", "x", "", "31.43%", expected=31.43, tol=0.005, scale=100,
                    get=cn.J("sim", "r.json", "a", "b"), source="r.json :: a.b")
    bad = cn.Entry("t.bad", "e1", "x", "", "31.6%", expected=31.6, tol=0.05, scale=100,
                   get=cn.J("sim", "r.json", "a", "b"), source="r.json :: a.b")
    missing = cn.Entry("t.missing", "e1", "x", "", "1", expected=1,
                       get=cn.J("sim", "nope.json", "a"), source="nope.json :: a")
    pending = cn.Entry("t.pending", "e1", "x", "", "?", status="pending", note="not run yet")
    res = {r.entry.id: r.verdict for r in cn.run([good, bad, missing, pending], repo_root=tmp_path,
                                                 proto_root=tmp_path / "proto")}
    assert res == {"t.good": "PASS", "t.bad": "FAIL", "t.missing": "FAIL", "t.pending": "PENDING"}


def test_markdown_cell_and_regex_extractors(tmp_path):
    (tmp_path / "t.md").write_text(
        "| rung | fills | HPR |\n|---|--:|--:|\n| N0 | 129 | -12.93% |\n| N3 | 129 | −16.42% |\n"
        "Mean **22,995,748đ (+30.0%)** here\n")
    cell = cn.MDCELL("sim", "t.md", r"^\| N3 \|", 2)
    rx = cn.MDRE("sim", "t.md", r"\*\*([\d,]+)đ \(")
    ctx = cn.Ctx(tmp_path, tmp_path)
    assert cell(ctx) == pytest.approx(-16.42)
    assert rx(ctx) == 22995748


def test_cli_exit_code_and_output(capsys):
    proto = _proto_root()
    argv = ["--proto-root", str(proto)]
    if not proto.is_dir():
        argv.append("--skip-missing-proto")
    assert cn.main(argv) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "PENDING" in out
    assert re.search(r"\d+ entries: \d+ PASS, 0 FAIL, \d+ PENDING", out)


def test_headline_map_lists_every_entry():
    text = DOC.read_text()
    missing = [e.id for e in cn.REGISTRY if f"`{e.id}`" not in text]
    assert not missing, missing


def test_no_local_paths_in_committed_files():
    for p in (DOC, REPO / "measurements" / "check_numbers.py"):
        text = p.read_text()
        assert "/Users/" not in text and "/home/" not in text, p
