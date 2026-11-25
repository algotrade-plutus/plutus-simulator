"""J19 — Straddle the KRX cutover (2025-05-05): a different margin MODEL each side.

Scenario **J19** of ``docs/reference/SCENARIO-CATALOGUE.md``, as user code.
The same futures position is margined by two different MECHANISMS depending on
the date: the pre-KRX ``MR = IM + VM`` before 2025-05-05, and QĐ 26's two
layers (broker IM intraday; VSDC's post-close scenario grid) from the cutover.

MECHANISM — the margin MODEL is a dated rule, resolved at the instant. The
rulebook returns the pre-KRX mechanism before the cutover and QD 26's two-layer
mechanism from 2025-05-05 — never the pre-KRX shape run on across the boundary.
(Until 2026-11-25 the post-KRX row was unsourced and raised; the signed QD 26
package has since been read, ``docs/reference/krx-margin-research.md``.)

POLICY (oracle — SCENARIO-CATALOGUE.md J19)
    * Pre-KRX (2017-05-01 → 2025-05-04): one layer, MR = IM + VM, VM loss-only
      — VSDC "Thông tin về ký quỹ"; QĐ 61 (high).
    * Post-KRX (2025-05-05 →): two layers — the broker margins IM on VSDC's
      published ratio intraday (QĐ 26 Điều 5.1.1.b), and VSDC computes
      MR = Max(ΣPgm, 0), Pgm = Max(Rm+Sm+Dm, MM) once after the close (Điều
      5.5, Phụ lục 2), tested binarily (Điều 13).
    * "Any blanket claim that nothing in this domain changed at KRX is false."

EXPECTED — Tier 2
    * A pre-KRX date resolves the margin model to the pre-KRX mechanism.
    * A post-KRX date resolves to the two-layer mechanism, not the pre-KRX one.
    * The two dates are in different rule editions (pre_krx vs post_krx).

RUN
    python scenarios/test_j19_krx_cutover.py
    pytest scenarios/test_j19_krx_cutover.py -v
"""
from __future__ import annotations

from datetime import datetime

import pytest

from plutus.market.session.rulebook import Rulebook

PRE_KRX = datetime(2022, 11, 9, 10, 0)    # in-corpus, MR = IM + VM
POST_KRX = datetime(2025, 5, 5, 10, 0)    # the cutover day


def run_j19():
    book = Rulebook()

    return {
        "pre_model": book.at(PRE_KRX).margin_model(),
        "post_model": book.at(POST_KRX).margin_model(),
        "pre_edition": book.edition_at(PRE_KRX).value,
        "post_edition": book.edition_at(POST_KRX).value,
    }


def test_j19_krx_cutover():
    obs = run_j19()

    # Pre-KRX: the margin mechanism resolves (the IM + VM shape).
    assert obs["pre_model"] == "pre_margin", obs["pre_model"]

    # Post-KRX: QD 26's two layers, a different mechanism from the pre-KRX one.
    assert obs["post_model"] == "krx_two_layer", obs["post_model"]

    # The two dates sit in different rule editions.
    assert obs["pre_edition"] != obs["post_edition"], obs


if __name__ == "__main__":
    obs = run_j19()
    print("J19 — KRX cutover margin models (2025-05-05)")
    print(f"  pre-KRX  (2022-11-09): margin_model = {obs['pre_model']!r}  "
          f"[{obs['pre_edition']}]")
    print(f"  post-KRX (2025-05-05): margin_model = {obs['post_model']!r}  "
          f"[{obs['post_edition']}]")
    print("  -> the model is dated: a different mechanism each side of the "
          "cutover")
    try:
        test_j19_krx_cutover()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
