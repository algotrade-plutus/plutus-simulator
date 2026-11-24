# Camera-ready headline map (RIVF'26)

Every number the camera-ready paper states, mapped to the committed result file it comes from: repo, commit,
the command that produces it, the data slice (with sha256 where a DATA-MANIFEST exists), the file and the
field or cell, and the value. Old → new where the value changed (old = the submission, `t4_measured_results.md`
and `experiments_registry.md`). Handoff task T9 (`docs/HANDOFF-2026-11-24-camera-ready.md` §5 T9, §7, §9).

**Check it.** `measurements/check_numbers.py` holds the same entries as a machine-readable registry and reads
each value back from its source. It only reads committed files (this repo, and the four proto repos via
`--proto-root`, default `../proto`); it never reruns an experiment or touches the database.

```
PYTHONPATH=src:. python measurements/check_numbers.py            # PASS / FAIL / PENDING per entry; exit 1 on FAIL
PYTHONPATH=src:. python measurements/check_numbers.py --write-doc  # regenerate the tables below
```

`tests/test_check_numbers.py` runs it against the repo and expects no FAIL.

**Status when generated:** 280 entries: 260 PASS, 0 FAIL, 20 PENDING. The PENDING entries are the T8.3
benchmark, the MM markouts (full-window run in progress), the test counts (to refresh at freeze), and numbers
that so far exist only in prose with no committed result file (S2, J18, the property-test and validator counts).

## Conventions

- **Tolerance.** A stated value passes if the source rounds to it: half a unit in the last stated digit
  (31.43% passes for 0.31426; −76.4% for −0.764458). Counts must match exactly.
- **Queue swing (F5)** is always relative to the optimistic arm: (optimistic − conservative) / optimistic.
- **Commit** in each row is the last commit that touched the source file, in that file's repo, when this map
  was generated. All repos are on branch `rivf26` (local commits only).
- **Macro** is the `paper/numbers.tex` macro the value fills (handoff §9). A blank macro means the number is
  quoted in the text or a table without its own macro, or is a check that backs one.
- The faithful MM arm's commit provenance: the faithful-A runs started at plutus-simulator `b52877e`, and the
  checkout moved to `af55e29` before they ended (`af55e29` only adds a per-day cache and the benchmark script;
  its message says F3 and S2 outputs are byte-identical). The ladder `.md` files record this.

## Table II at a glance (§6 acceptance, per window)

f/n = faithful fills / naive fills. HPR naive → faithful. All values are registry entries below.

| Strategy | Window | f/n | HPR n → f | §6 criteria 1 / 2 |
|---|---|---:|---|---|
| SB | w2022 | 100.0% (457 / 457) | −26.21% → −27.08% | 1 tie (owner: read as ≤ for SB) / pass |
| SB | w2023 | 99.6% (724 / 727) | +19.66% → +17.68% | pass / pass |
| Grid | w2022_10 | 45.6% (62 / 136) | −2.40% → −2.65% | pass / pass |
| Grid | w2021_11 | 46.0% (57 / 124) | +1.47% → +1.18% | pass / pass |
| Pair | w1 | 53.8% (651 / 1,209) | +1.03% → −2.15% (flip) | pass / pass |
| Pair | w2 | 52.0% (403 / 775) | +0.28% → −0.31% (flip) | pass / pass |
| MM anchor (faithful flat each session, conservative) | krx2025, 40 sessions | 16.7% (116 / 693) | +29.57% → −6.03% | pass / pass |
| MM anchor | krx2025, 20 pre-cutover sessions | 50.9% (116 / 228) | −5.22% → −6.03% | pass / pass |
| MM anchor | im2022 | 54.3% (70 / 129) | −12.93% → +2.19% | pass / **fail** |
| MM ladder (A fixed), F-con vs N0 | im2022 | 89.9% (116 / 129) | −12.93% → −11.47% | pass / **fail** |
| MM ladder, F-opt vs N0 | im2022 | 153.5% (198 / 129) | −12.93% → −2.52% | **fail** / **fail** |
| MM ladder, F-con vs N0 | krx2025 pre-cutover | 67.1% (153 / 228) | −5.22% → −25.55% | pass / pass |
| MM ladder, F-opt vs N0 | krx2025 pre-cutover | 114.5% (261 / 228) | −5.22% → −7.58% | **fail** / pass |

Ranges over windows: SB f/n 99.6–100.0%; Grid 45.6–46.0%; Pair 52.0–53.8%. Pair's profitable-to-loss flip
recurs in both windows. Which MM arm is Table II's row (anchor vs ladder, conservative vs optimistic) is an
**OWNER** decision (`docs/rivf26/NOTES-FOR-OWNER.md` §2 and §4); nothing was tuned.

## Data slices

Committed slices are verified by the checker (`slice.*` entries: every listed file's sha256 against its
DATA-MANIFEST). Slices that are not shipped live in the working folder `rivf26/data/<name>/` (outside every
repo), each with its own `DATA-MANIFEST.md`; their sha256 values are copied here so the map is self-contained.

| Slice | Feeds | Where | Manifest | Committed bytes |
|---|---|---|---|---:|
| `strategies/fixtures/parquet/` | F3 fill axis (S1), S1–S7 | this repo | `DATA-MANIFEST.md` (9 files, checked) | 20,875 |
| `strategies/fixtures/extract/` | F3 queue axis (S9), S8 | this repo | **none** (`PROVENANCE.md`, no sha256) | 402,877 |
| `strategies/fixtures/s2_lock/{daily,book}/` | S2 lock-queue measurement | this repo | 2 manifests (checked) | — |
| `scenarios/fixtures/{daily,book}/` | J1–J37 | this repo | 2 manifests (checked) | 65,178 + 192,379 |
| `tests/market/session/fixtures/book_walk/` | `test_book_walk.py` | this repo | manifest (checked) | — |
| `t2-e1` | E1 | working folder only (statistics shipped) | see below | 0 |
| `t2-indeterminate/{daily,book}` | F2 | working folder only | see below | 0 |
| `t2-futures-margin` | regime split, IM step, margin incidence | working folder only | sha256 in `docs/reference/tables/t2/futures_margin.md` | 0 |
| `t2-hsx-daily`, `t2-hsx-daily-grid-history` | admission, band, tick grid | working folder only | sha256 in `docs/reference/tables/t2/hsx_daily.md` | 0 |
| ProtoSmartBeta `data/{market,signal}/<w>/` | SB | ProtoSmartBeta | 6 manifests (checked) | 967,897 |
| ProtoGrid `data/{band,tick}/<w>/` | Grid | ProtoGrid | `data/manifest/<w>/DATA-MANIFEST.md` (checked) | 2,932,667 |
| ProtoPair `data/market/<w>/` | Pair | ProtoPair | 2 manifests (checked) | 359,593 |
| ProtoMarketMaker `data/{band,l2,market}/<w>/` | MM anchor and ladder | ProtoMarketMaker | `data/<w>-MANIFEST.md` (checked) | 25,078,256 (im2022 8,726,352; krx2025 16,351,904): over the size flag, owner sign-off |

sha256 of the unshipped population slices (from their working-folder manifests):

| Slice | File | sha256 |
|---|---|---|
| `t2-e1` | `quote_ceil.parquet` | `c142bd74e68a91d5670fa586c683be7527049b3cb2fddadf5b10ed83a54591fc` |
| `t2-e1` | `quote_close.parquet` | `283ee249eccd12cfd48ecba11cdd3cc9bd77c4bca9cf069cb239cc908861f91c` |
| `t2-e1` | `quote_dailyvolume.parquet` | `f1f5e2454752378220940dbf6f577ab440ca7e153dfad004ba39e389de3095e4` |
| `t2-e1` | `quote_floor.parquet` | `7f2b8f4ebe52432bd005afc1b9f503e3bc5074fdc72dd59d44efb203ebf66f3d` |
| `t2-e1` | `quote_max.parquet` | `b7f8f539cd99cd62e68a1daff49414b5ff11c36b74ce813bea97cd168e27c603` |
| `t2-e1` | `quote_min.parquet` | `6fb62a31eb1efb763ca206fa644f59d648c34a8022b578a1a9c1e7e4d5b6487c` |
| `t2-e1` | `quote_open.parquet` | `9de9cbaef595102f821eeef92fb455c599a3052ed9ff38ac01fa401171f28373` |
| `t2-e1` | `quote_reference.parquet` | `a94f176e0e61b31fdfc21be826cb6d320040b3cf49f74f7884b382d5e7b5ca49` |
| `t2-e1` | `quote_ticker.parquet` | `48cb46522e4d02b6cd1095254e8207acdf683bf67ee1878462307328c632e9f2` |
| `t2-indeterminate/daily` | `quote_ceil.parquet` | `1fb5a5803dd24d02201438e982ba193645af31feaea93745b5bf4f67cf70808d` |
| `t2-indeterminate/daily` | `quote_close.parquet` | `69acb71199534464e3f00fc9d020d46530182d54bea84e52179016a209d63d68` |
| `t2-indeterminate/daily` | `quote_dailyvolume.parquet` | `3882107d5ea1a6bb27a1ed7dbd9afafa0d6b621186407c7c67931768de77bf73` |
| `t2-indeterminate/daily` | `quote_floor.parquet` | `eeaad3debaf7b6bcd712c27f520d22a56dc37f52246c6fff20d8bbaf939c4396` |
| `t2-indeterminate/daily` | `quote_max.parquet` | `d847c2673d8288527e1ee377bbdf07f3123fff5465c42233517e3436509d3dfb` |
| `t2-indeterminate/daily` | `quote_min.parquet` | `09545615ca93f0a0516b8f8ecb4cf201cb641b404e142c639f5fd08426930d68` |
| `t2-indeterminate/daily` | `quote_open.parquet` | `ff4a64dc515198d7d2aefdc25a9e0801b3d719fe509aeb57b95c018172f2be7a` |
| `t2-indeterminate/daily` | `quote_reference.parquet` | `95229ea5f5179a67af1ec4689b20ddef41eb9f883822d682f9a20418b294bea3` |
| `t2-indeterminate/daily` | `quote_ticker.parquet` | `4b62635bf88d2e25f9bb586d550361ce1d0ed4cdb2d26d32bef3ff66217853f0` |
| `t2-indeterminate/book` | `local_quote_askprice.parquet` | `379d490a1d23bf2ff5f98dfaf4a054668ead3472d9dcf847bbc8afbc1eccca99` |
| `t2-indeterminate/book` | `local_quote_asksize.parquet` | `960a8caecf267466ed2e1cfc81042799cce79e43d7fa493e31454e05bb4c98a5` |
| `t2-indeterminate/book` | `local_quote_bidprice.parquet` | `af6e41d82dc67b9c53653cd9d592c6299a65a7e55b2bac4f42b2cf079d6ec1d5` |
| `t2-indeterminate/book` | `local_quote_bidsize.parquet` | `123d7d4a39552d2068fbd2842e5cf96c87ed0349c2f659da06ee7f307822a968` |
| `t2-indeterminate/book` | `local_quote_matched.parquet` | `b78e38d4cedfe2127e4dabb973f1315ec222dd7d14d9a36e47b279a05089773c` |
| `t2-indeterminate/book` | `local_quote_total.parquet` | `b1816d3f4740ea3630f7efebc7a42d51a05c7e3e0507dea3262e5cf1734d97b1` |
| `t2-futures-margin` | `quote_close.parquet` | `a046b87dd4ebb8a1fb37e47f5e77af29f8b5b981df492f0f25ab4dd8a85a1979` |
| `t2-futures-margin` | `quote_futurecontractcode.parquet` | `b181273a32e319a0f5e64b2b0b261af2750ef084752d7fde5fa3db7acaaa0e91` |
| `t2-hsx-daily` | `quote_ceil.parquet` | `d9abf9764bdccadc26298f924cbc2fba299be2cf7d2ea9640ce796cb31474510` |
| `t2-hsx-daily` | `quote_close.parquet` | `7b053c33e701f73c28394e4cc45c511ced9ba9287ff2b443acba9b5f0a152c92` |
| `t2-hsx-daily` | `quote_floor.parquet` | `6d027caf03b195dc15aeb771c59281993db216ecc407b66fb4508bb7a1cfe43a` |
| `t2-hsx-daily` | `quote_reference.parquet` | `7438cd875a091f11ad6a554acaf2e4ef069640c2b8b3956a8673007a7d06e14d` |
| `t2-hsx-daily` | `quote_ticker.parquet` | `4893db2004200ed559658b7bfa33a52318724536751b4f7cbdb8303bcc9d1e18` |
| `t2-hsx-daily-grid-history` | `quote_close.parquet` | `19c2d366d68310bfc78ae427f83a5a5b71f3a0f04de1126a8a3f03f8ac4aaba7` |
| `t2-hsx-daily-grid-history` | `quote_ticker.parquet` | `97523aea1fb75251280b048c0c764c851fb20e2ba830f6ddc177eda3f12ff27d` |

## Discrepancies (prose vs result file; nothing was silently picked)

Each item gives both values and both sources. The registry takes the **result file** in every case; the prose
needs correcting, or the owner decides.

1. **F2 figure data is stale.** `figures/f2_indeterminate_rate.json` (last changed `e1450de`) still holds the
   old 66-day population: bar 35.8%, tick optimistic 85.6%, tick conservative 99.7%. The camera-ready values are
   in `docs/reference/tables/t2/indeterminate_after_change2.json`: 90 days, 32.6% / 10.1% / 60.2%.
   `docs/rivf26/T0-audit.md` §4h says the F2 figure was regenerated; commit `82a68cf` regenerated only the PNG.
   The registry reads the T2 JSON. Regenerate the figure JSON (or check the PNG was drawn from the new data).
2. **Unit-test count.** `docs/rivf26/T0-audit.md` §4h: "2,162 passed, 0 failed, 2 xfailed, 453 skipped". The
   coordinating session's later count is 2,169 passed + 2 xfailed, and `pytest --collect-only tests` at
   `7fbe16b` gives 2,624 = 2,169 + 2 + 453 (7 tests added after §4h). Both are superseded at freeze: the
   engine fix in flight turns the 2 xfails into passes, and `tests/test_check_numbers.py` adds 7 tests.
3. **ProtoPair README engine commit.** `README.md` heads its results "plutus-simulator `0633a5b`"; both
   `result/pair_anchor/w1.json` and `w2.json` record `plutus_simulator_commit` `b62e163`. The JSON is the run's
   own record.
4. **MM contract capacity at the IM step.** The submission (and handoff §5 T5) says 37 → 28. The run gives
   **36 → 28** (`result/mm_anchor/im2022.json` `faithful.capacity`, 2022-12-14 → 2022-12-15). The
   ProtoMarketMaker README also gives a static 36 → **27** at 1,059 points, next to the run's 36 → 28: the two
   differ only in the price used. The registry takes the run (36 → 28).
5. **MM return for im2022 depends on which faithful arm.** `NOTES-FOR-OWNER.md` §2 and the MM README anchor
   table: faithful +2.19% vs naive −12.93% (flat each session, `result/mm_anchor/im2022.json`). The ladder
   (`result/mm_ladder/im2022.md`, algorithm A with overnight carry): F-con −11.47%, F-opt −2.52%. Both are
   committed results of different designs, not a contradiction; the owner picks Table II's arm.
6. **MM undecided pre/post is not the same measure as the submission.** The submission's "99.94% → 99.92%"
   (KRX cutover, fill-evaluation events; the registry text says the rate *fell*, while the paper says "rising")
   compares with krx2025 pre 99.76% (orders) and no post-cutover orders at all (every post-cutover session is
   refused), or with the im2022 IM step: 99.87% → 99.99% (orders). Owner picks the comparison.
7. **Maintenance effort for the IM step.** `T0-audit.md` §4g and `NOTES-FOR-OWNER.md` §3: "data-only (one tuple
   line)". `docs/reference/tables/t8_maintenance_effort.md`: 15 rule-data lines in 2 units (the tuple line plus
   the 14-line cited rulebook row), 0 engine lines, 3 undated copies. `\nMaintDataLines` is registered as 15;
   "one line" is true only of the value itself.
8. **MM slice size.** `docs/reference/tables/data_provenance.md` says the committed MM slices are 29 MB;
   `NOTES-FOR-OWNER.md` §2 says 15.1 MB and 8.2 MB. The committed `data/` files sum to 25,078,256 bytes
   (krx2025 16,351,904; im2022 8,726,352). The smaller fixtures differ too (provenance: strategies parquet
   40 KB, scenarios daily 88 KB, book 224 KB; committed bytes 20,875, 65,178, 192,379), probably disk blocks
   vs bytes. Both need restating as bytes from the manifests.
9. **SB signal manifests list a file that is not committed.** `ProtoSmartBeta/data/signal/w20{22,23}/DATA-MANIFEST.md`
   list an empty (0-row) `quote_ticker.parquet` that is not in the repo (`--no-ticker-master`). Harmless; the
   checker allows it by name.
10. **Acceptance failures, not tuned.** MM ladder F-opt fills more than naive (153.5% im2022, 114.5% krx2025),
    and im2022's faithful arms lose less than naive in both designs (§6 criterion 2). Already raised with the
    owner (`NOTES-FOR-OWNER.md` §2.1, §4); listed so that the paper does not state the criteria hold for MM.

No disagreement was found between the T4 camera-ready table (`docs/reference/tables/t4_camera_ready.md`) and
the result files for any row it covers; nor between the SB, Grid and MM READMEs' result tables and their JSON.

## Not mapped yet

- Macros with no number behind them yet: `\sbWin` `\gridWin` `\mmWin` `\pairWin` (window labels, not
  numbers: w2022/w2023, w2022_10/w2021_11, krx2025/im2022, w1/w2), `\pairFlipWin` (both windows flip),
  `\nAcceptance` (no definition found in the handoff), `\cameraTag` (set at freeze).
- `strategies/fixtures/extract/` has no sha256 manifest, so the S9 queue numbers have no slice hash.
- Numbers that exist only in prose are PENDING with a note (S2, J18, validator edges, property counts); they
  need a committed result file or an exact test pin before they can be checked.

## The map

<!-- BEGIN GENERATED: measurements/check_numbers.py --write-doc -->

### E1: fill-policy divergence over the 2022 HSX population

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `PYTHONPATH=src:. python -m measurements.e1_regenerate run --data-dir <rivf26-data>/t2-e1`, then `python measurements/e1_publish.py --data-root <rivf26-data>/t2-e1 --out docs/reference/tables/t2/e1_published`
- **Data slice:** `rivf26/data/t2-e1/` (391 HSX tickers, 2022; not shipped, statistics only; sha256 in the map's slice table)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `e1.decisions` | `\nDecisions` | decisions (5 intents × ticker-days) | 477,537 → **484,949** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b16aa1` :: `questions` | PASS |
| `e1.agreed` |  | decisions on which all three policies agree | — → **332,549** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b16aa1` :: `agreed` | PASS |
| `e1.tickers` | `\nEoneTickers` | tickers (HSX stocks, ≥200 sessions in 2022) | 385 → **391** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b16aa1` :: `tickers` | PASS |
| `e1.ticker_days` |  | ticker-days | 95,815 → **97,269** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b16aa1` :: `ticker_days` | PASS |
| `e1.agree` | `\pctPolicyAgree` | policies agree | 68.4% → **68.57%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `agreement.p` | PASS |
| `e1.disagree` | `\pctPolicyDisagree` | policies disagree | 31.6% → **31.43%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `disagreement.p` | PASS |
| `e1.disagree.wilson_lo` |  | disagree, Wilson 95% low | 31.50 → **31.30%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `disagreement.wilson95.0` | PASS |
| `e1.disagree.wilson_hi` |  | disagree, Wilson 95% high | 31.76 → **31.56%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `disagreement.wilson95.1` | PASS |
| `e1.disagree.boot_lo` |  | disagree, ticker-cluster bootstrap 95% low | — → **30.97%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `disagreement.cluster_boot95.0` | PASS |
| `e1.disagree.boot_hi` |  | disagree, ticker-cluster bootstrap 95% high | — → **31.84%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `disagreement.cluster_boot95.1` | PASS |
| `e1.published.n_sum_month` |  | published by-month table sums to the decisions | — → **484,949** | `docs/reference/tables/t2/e1_published/by_month_intent.csv` @ `5b16aa1` :: sum of column `n` | PASS |
| `e1.published.agreed_sum_month` |  | published by-month table sums to the agreed | — → **332,549** | `docs/reference/tables/t2/e1_published/by_month_intent.csv` @ `5b16aa1` :: sum of column `agreed` | PASS |
| `e1.published.n_sum_ticker` |  | published by-ticker table sums to the decisions | — → **484,949** | `docs/reference/tables/t2/e1_published/by_ticker_intent.csv` @ `5b16aa1` :: sum of column `n` | PASS |
| `e1.published.agreed_sum_ticker` |  | published by-ticker table sums to the agreed | — → **332,549** | `docs/reference/tables/t2/e1_published/by_ticker_intent.csv` @ `5b16aa1` :: sum of column `agreed` | PASS |
| `e1.figure.decisions` |  | figure data (`figures/e1_fill_divergence.json`) carries the same N | 477,537 → **484,949** | `figures/e1_fill_divergence.json` @ `82a68cf` :: `questions` | PASS |
| `e1.figure.agree` |  | figure data agreement rate | 68.4% → **68.57%** | `figures/e1_fill_divergence.json` @ `82a68cf` :: `agreement_rate` | PASS |
| `e1.disagree.market_buy` |  | policies disagree: market order | 95.5% → **95.44%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.market_buy.disagreement.p` | PASS |
| `e1.disagree.limit_buy_at_close` |  | policies disagree: limit buy at close | 23.1% → **23.13%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_close.disagreement.p` | PASS |
| `e1.disagree.limit_sell_at_close` |  | policies disagree: limit sell at close | 23.3% → **23.52%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_close.disagreement.p` | PASS |
| `e1.disagree.limit_buy_at_floor` |  | policies disagree: limit buy at floor | 9.9% → **9.15%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_floor.disagreement.p` | PASS |
| `e1.disagree.limit_sell_at_ceil` |  | policies disagree: limit sell at ceiling | 6.0% → **5.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_ceil.disagreement.p` | PASS |
| `e1.fill.market_buy.soft` |  | fill rate, market_buy, `soft` | 89.21% → **89.14%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.market_buy.fill.soft.p` | PASS |
| `e1.fill.market_buy.hard` |  | fill rate, market_buy, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.market_buy.fill.hard.p` | PASS |
| `e1.fill.market_buy.probabilistic` |  | fill rate, market_buy, `probabilistic` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.market_buy.fill.probabilistic.p` | PASS |
| `e1.fill.limit_buy_at_close.soft` |  | fill rate, limit_buy_at_close, `soft` | 89.20% → **89.13%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_close.fill.soft.p` | PASS |
| `e1.fill.limit_buy_at_close.hard` |  | fill rate, limit_buy_at_close, `hard` | 72.32% → **72.30%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_close.fill.hard.p` | PASS |
| `e1.fill.limit_buy_at_close.probabilistic` |  | fill rate, limit_buy_at_close, `probabilistic` | 80.73% → **80.68%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_close.fill.probabilistic.p` | PASS |
| `e1.fill.limit_sell_at_close.soft` |  | fill rate, limit_sell_at_close, `soft` | 89.21% → **89.14%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_close.fill.soft.p` | PASS |
| `e1.fill.limit_sell_at_close.hard` |  | fill rate, limit_sell_at_close, `hard` | 72.81% → **72.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_close.fill.hard.p` | PASS |
| `e1.fill.limit_sell_at_close.probabilistic` |  | fill rate, limit_sell_at_close, `probabilistic` | 81.11% → **80.92%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_close.fill.probabilistic.p` | PASS |
| `e1.fill.limit_buy_at_floor.soft` |  | fill rate, limit_buy_at_floor, `soft` | 9.47% → **8.74%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_floor.fill.soft.p` | PASS |
| `e1.fill.limit_buy_at_floor.hard` |  | fill rate, limit_buy_at_floor, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_floor.fill.hard.p` | PASS |
| `e1.fill.limit_buy_at_floor.probabilistic` |  | fill rate, limit_buy_at_floor, `probabilistic` | 4.74% → **4.39%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_buy_at_floor.fill.probabilistic.p` | PASS |
| `e1.fill.limit_sell_at_ceil.soft` |  | fill rate, limit_sell_at_ceil, `soft` | 5.64% → **5.21%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_ceil.fill.soft.p` | PASS |
| `e1.fill.limit_sell_at_ceil.hard` |  | fill rate, limit_sell_at_ceil, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_ceil.fill.hard.p` | PASS |
| `e1.fill.limit_sell_at_ceil.probabilistic` |  | fill rate, limit_sell_at_ceil, `probabilistic` | 2.76% → **2.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_intent.limit_sell_at_ceil.fill.probabilistic.p` | PASS |
| `e1.undecided.hard` |  | undecided share, `hard` | 33.4% → **33.26%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_policy.hard.indeterminate.p` | PASS |
| `e1.undecided.soft` |  | undecided share, `soft` | 2.7% → **2.75%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_policy.soft.indeterminate.p` | PASS |
| `e1.undecided.probabilistic` |  | undecided share, `probabilistic` | 21.0% → **20.97%** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `by_policy.probabilistic.indeterminate.p` | PASS |
| `e1.shares.soft` | `\sharesSoft` | filled shares, `soft` | 245.8M → **247,376,400** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `executed_quantity.soft` | PASS |
| `e1.shares.hard` | `\sharesHard` | filled shares, `hard` | 128.5M → **129,818,200** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `executed_quantity.hard` | PASS |
| `e1.shares.probabilistic` |  | filled shares, `probabilistic` | 148M → **149,450,400** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `executed_quantity.probabilistic` | PASS |
| `e1.shares.ratio` | `\xSharesSoftHard` | filled shares, soft / hard | 1.91× → **1.91** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `soft_over_hard_quantity.ratio` | PASS |
| `e1.shares.ratio.boot_lo` |  | soft / hard ratio, bootstrap 95% low | — → **1.89** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `soft_over_hard_quantity.cluster_boot95.0` | PASS |
| `e1.shares.ratio.boot_hi` |  | soft / hard ratio, bootstrap 95% high | — → **1.92** | `docs/reference/tables/t2/e1_aggregates.json` @ `a42edee` :: `soft_over_hard_quantity.cluster_boot95.1` | PASS |

### F2: the indeterminate rate, bar vs tick

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `PYTHONPATH=src:. python measurements/indeterminate_rate.py` on the T2 group D slices (see `docs/reference/tables/t2/indeterminate.md`)
- **Data slice:** `rivf26/data/t2-indeterminate/{daily,book}` (FPT, HPG, HTV, 2022-10-20..11-30; not shipped)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `f2.days` |  | instrument-days (FPT, HPG, HTV) | 66 → **90** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `instrument_days` | PASS |
| `f2.bar` |  | undecided, `hard` at the daily bar | 35.8% → **32.6%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=BAR / hard].rate` | PASS |
| `f2.bar.ci_lo` |  | bar, Wilson 95% low | 32.3 → **29.7%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=BAR / hard].ci_low` | PASS |
| `f2.bar.ci_hi` |  | bar, Wilson 95% high | 39.4 → **35.7%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=BAR / hard].ci_high` | PASS |
| `f2.bar.n` |  | bar, fill evaluations | 698 → **950** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=BAR / hard].evaluations` | PASS |
| `f2.tick_opt` |  | undecided, `book_walk` tick, optimistic queue | 85.6% → **10.1%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (optimistic)].rate` | PASS |
| `f2.tick_opt.ci_lo` |  | tick optimistic, Wilson 95% low | 83.5 → **8.7%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (optimistic)].ci_low` | PASS |
| `f2.tick_opt.ci_hi` |  | tick optimistic, Wilson 95% high | 87.4 → **11.7%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (optimistic)].ci_high` | PASS |
| `f2.tick_opt.n` |  | tick optimistic, fill evaluations | 1,212 → **1,484** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (optimistic)].evaluations` | PASS |
| `f2.tick_con` |  | undecided, `book_walk` tick, conservative queue | 99.7% → **60.2%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.tick_con.n` |  | tick conservative, fill evaluations | 1,545 → **1,650** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (conservative)].evaluations` | PASS |
| `f2.tick_con.before_change2` |  | tick conservative before change 2 (`e528633`) | 99.7% → **78.2%** | `docs/reference/tables/t2/indeterminate_before_change2.json` @ `270a423` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.bar.resolution_limit` |  | bar: share whose cause is the resolution limit | 35.8% → **32.6%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: `arms.[label=BAR / hard].resolution_limit_share` | PASS |
| `f2.tick.resolution_limit` |  | tick (both queues): resolution-limit share | **0** (unchanged) | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `270a423` :: computed from `docs/reference/tables/t2/indeterminate_after_change2.json` `arms.[label=TICK / book-walk (optimistic)].resolution_limit_share`; `docs/reference/tables/t2/indeterminate_after_change2.json` `arms.[label=TICK / book-walk (conservative)].resolution_limit_share` | PASS |

### F3: fill-policy axis (S1) and queue axis (S9)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest strategies/test_f3_cross_policy.py strategies/test_s9_queue_sensitivity.py` (writes `figures/f3_cross_policy_divergence.json`)
- **Data slice:** `strategies/fixtures/parquet/` (DATA-MANIFEST, checked below) and `strategies/fixtures/extract/` (no sha256 manifest; `PROVENANCE.md` only)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `f3.s1.soft.return` |  | S1 return under `soft` | −75.5% → **−76.4%** | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.soft.return_pct` | PASS |
| `f3.s1.soft.fills` |  | S1 fills under `soft` | **5** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.soft.fills` | PASS |
| `f3.s1.soft.forced` |  | S1 forced liquidations under `soft` | 2 → **3** | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.soft.forced` | PASS |
| `f3.s1.soft.undecided` |  | S1 undecided under `soft` | **0%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.soft.indeterminate_rate` | PASS |
| `f3.s1.hard.return` |  | S1 return under `hard` | **0.0%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.hard.return_pct` | PASS |
| `f3.s1.hard.undecided` |  | S1 undecided under `hard` | **50%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.hard.indeterminate_rate` | PASS |
| `f3.s1.probabilistic.undecided` |  | S1 undecided under `probabilistic` | **50%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `fill_axis.probabilistic.indeterminate_rate` | PASS |
| `f3.queue.optimistic` | `\sharesQueueOpt` | S9 maker shares, optimistic queue | **152,600** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `queue_axis.optimistic.maker_shares` | PASS |
| `f3.queue.conservative` | `\sharesQueueCons` | S9 maker shares, conservative queue | **123,700** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `queue_axis.conservative.maker_shares` | PASS |
| `f3.queue.probabilistic` |  | S9 maker shares, probabilistic queue | **137,600** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `queue_axis.probabilistic.maker_shares` | PASS |
| `f3.queue.swing` | `\pctQueueSwing` | queue swing (optimistic − conservative) / optimistic (F5) | **18.9%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: computed from `figures/f3_cross_policy_divergence.json` `queue_axis.optimistic.maker_shares`; `figures/f3_cross_policy_divergence.json` `queue_axis.conservative.maker_shares` | PASS |
| `f3.queue.conservative.undecided` |  | S9 conservative queue undecided | 16.7% → **0%** | `figures/f3_cross_policy_divergence.json` @ `a1a3c56` :: `queue_axis.conservative.indeterminate_rate` | PASS |

### Derivatives margin: regime split, the IM step, margin-call incidence

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `PYTHONPATH=src:. python measurements/t2_futures_margin.py <rivf26-data>/t2-futures-margin`
- **Data slice:** `rivf26/data/t2-futures-margin/` (VN30F front month, 2021-06-01..2022-12-30; sha256 in `docs/reference/tables/t2/futures_margin.md`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `margin.entries` |  | entries in the VN30F front-month book | **381** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: regex /N = ([\d,]+) entries/ | PASS |
| `margin.pre` | `\marginPre` | mean requirement, pre-KRX IM+VM | 17,692,385đ → **17,692,385** | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| mean margin requirement \| pre-KRX/ cell 3 | PASS |
| `margin.post` | `\marginPost` | mean requirement, post-KRX scenario grid | 22,995,748đ → **22,995,748** | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| mean margin requirement \| post-KRX/ cell 3 | PASS |
| `margin.regime_split` | `\pctMarginSwing` | regime split, post-KRX grid vs pre-KRX IM+VM | **+30.0%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: computed from `docs/reference/tables/t2/futures_margin.md` row /^\| mean margin requirement \| pre-KRX/ cell 3; `docs/reference/tables/t2/futures_margin.md` row /^\| mean margin requirement \| post-KRX/ cell 3 | PASS |
| `margin.regime_split.table` |  | regime split as stated in the F1 table | **+30.0%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| \(1\) \*\*Regime split/ cell 3 | PASS |
| `margin.im_step` |  | the 13% → 17% IM step alone (F1) | (shown as +30.0%) → **+30.8%** | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| \(2\) \*\*13% → 17% IM step/ cell 3 | PASS |
| `margin.im_step.formula` |  | IM step = 17/13 − 1 (book-independent) | — → **+30.8%** | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: computed from `docs/reference/tables/t2/futures_margin.md` regex /(17,584,984)đ → 22,995,748đ/; `docs/reference/tables/t2/futures_margin.md` regex /17,584,984đ → (22,995,748)đ/ | PASS |
| `margin.call.h5` | `\pctCallFive` | margin-call incidence, hold 5 | **6.30%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| margin-call incidence \| 5 \|/ cell 3 | PASS |
| `margin.forced.h5` |  | forced-close incidence, hold 5 | **1.84%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| forced-close incidence \| 5 \|/ cell 3 | PASS |
| `margin.call.h10` |  | margin-call incidence, hold 10 | **11.55%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| margin-call incidence \| 10 \|/ cell 3 | PASS |
| `margin.forced.h10` |  | forced-close incidence, hold 10 | **8.66%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| forced-close incidence \| 10 \|/ cell 3 | PASS |
| `margin.call.h20` | `\pctCallTwenty` | margin-call incidence, hold 20 | **13.12%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| margin-call incidence \| 20 \|/ cell 3 | PASS |
| `margin.forced.h20` |  | forced-close incidence, hold 20 | **9.71%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `62d9308` :: row /^\| forced-close incidence \| 20 \|/ cell 3 | PASS |

### Equity admission, band agreement, tick-grid conformity

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `measurements/equity_admission.py`, `band_conformance.py`, `grid_conformity.py` (exact invocations in `docs/reference/tables/t2/hsx_daily.md`)
- **Data slice:** `rivf26/data/t2-hsx-daily/` and `t2-hsx-daily-grid-history/` (sha256 in `docs/reference/tables/t2/hsx_daily.md`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `hsx.admission.lag0` |  | blocked entry, lag 0 (look-ahead) | 12.90% → **13.16%** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `3b3d765` :: `stocks_lag0.rate` | PASS |
| `hsx.admission.lag0.n` |  | lag 0 attempts | 197,337 → **205,755** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `3b3d765` :: `stocks_lag0.attempts` | PASS |
| `hsx.admission.lag1` |  | blocked entry, lag 1 (honest) | 5.84% → **6.03%** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `3b3d765` :: `stocks_lag1.rate` | PASS |
| `hsx.admission.lag1.n` |  | lag 1 attempts | 197,521 → **205,958** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `3b3d765` :: `stocks_lag1.attempts` | PASS |
| `hsx.band.agree` | `\pctBandAgree` | band agreement, HSX stock | 97.59% → **91.90%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.agreement_rate` | PASS |
| `hsx.band.ci_lo` | `\ciBandAgree` | band agreement, Wilson 95% low | 97.52 → **91.78%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.ci_low` | PASS |
| `hsx.band.ci_hi` | `\ciBandAgree` | band agreement, Wilson 95% high | 97.66 → **92.03%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.ci_high` | PASS |
| `hsx.band.n` | `\nBandDays` | band agreement, HSX stock ticker-days | 179,784 → **182,367** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.rows` | PASS |
| `hsx.band.disagree` |  | band disagreements | 4,324 → **14,769** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.disagree` | PASS |
| `hsx.band.disagree_same_width` |  | disagreements with the band width right | — → **2** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `3b3d765` :: `HSX stock.disagree_same_width` | PASS |
| `hsx.grid.history` | `\pctGridConform` | tick-grid conformity, library rule, all history | 99.999% → **99.9992%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `3b3d765` :: `HSX stocks.library_rate` | PASS |
| `hsx.grid.history.naive` | `\pctGridNaive` | tick-grid conformity, naive flat 0.1, all history | 84.51% → **85.38%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `3b3d765` :: `HSX stocks.naive_rate` | PASS |
| `hsx.grid.history.n` |  | closes, all history | 1,086,518 → **1,073,191** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `3b3d765` :: `HSX stocks.observations` | PASS |
| `hsx.grid.window` |  | tick-grid conformity, library rule, 2021–22 | (not measured) → **100.000%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `3b3d765` :: `HSX stocks.library_rate` | PASS |
| `hsx.grid.window.naive` |  | tick-grid conformity, naive, 2021–22 | (not measured) → **72.94%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `3b3d765` :: `HSX stocks.naive_rate` | PASS |
| `hsx.grid.window.n` |  | closes, 2021–22 | — → **186,271** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `3b3d765` :: `HSX stocks.observations` | PASS |

### T8: rule versions, broker fields, maintenance effort, validator, properties, benchmark

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `PYTHONPATH=src python measurements/t8_counts.py`; `python measurements/maintenance_effort.py --markdown`; `PYTHONPATH=src:. python measurements/perf_benchmark.py`
- **Data slice:** none (engine source and git history)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `t8.rule_versions` | `\nRuleRows` | enforced rule versions (runtime rulebook rows) | 97 → **114** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 2 | PASS |
| `t8.rule_keys` |  | rule keys | — → **93** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 1 | PASS |
| `t8.rule_families` | `\nRuleTables` | rule families (tables) | **12** (unchanged) | `docs/reference/tables/t8_counts.md` @ `905f737` :: regex /\*\*Total \((\d+) families\)\*\*/ | PASS |
| `t8.rule_high` |  | rule versions graded HIGH | — → **87** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 4 | PASS |
| `t8.rule_not_high` | `\nEnforcedBelowHigh` | rule versions graded MEDIUM, LOW or UNVERIFIED | a handful → **27** | `docs/reference/tables/t8_counts.md` @ `905f737` :: computed from `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 5; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 6; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 7 | PASS |
| `t8.rule_unknown` |  | rows that record an absence (UNKNOWN) | **11** (unchanged) | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 10 | PASS |
| `t8.broker_fields` |  | broker fields | **244** (unchanged) | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 1 | PASS |
| `t8.broker_published` |  | broker fields published by the firm | — → **110** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 2 | PASS |
| `t8.broker_supplied` | `\nBrokerSupplied` | broker fields supplied by us (as shipped) | — → **0** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 3 | PASS |
| `t8.broker_inferred` |  | broker fields inferred | — → **21** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 4 | PASS |
| `t8.broker_unpublished` |  | broker fields recorded as not published | — → **113** | `docs/reference/tables/t8_counts.md` @ `905f737` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 5 | PASS |
| `t8.encoded_total` |  | rules + broker fields encoded in the engine | 341 → **358** | `docs/reference/tables/t8_counts.md` @ `905f737` :: computed from `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 2; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 1 | PASS |
| `t8.maint.im.data` | `\nMaintDataLines` | IM 13% → 17%: rule-data lines | — → **15** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| VSD initial margin 13% -> 17%/ cell 2 | PASS |
| `t8.maint.im.engine` | `\nMaintCodeLines` | IM 13% → 17%: change-specific engine lines | — → **0** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| VSD initial margin 13% -> 17%/ cell 4 | PASS |
| `t8.maint.im.dup` |  | IM 13% → 17%: undated duplicate scalars | — → **3** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| VSD initial margin 13% -> 17%/ cell 3 | PASS |
| `t8.maint.lot.data` |  | HOSE lot 10 → 100: rule-data lines | — → **13** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| HOSE round lot 10 -> 100/ cell 2 | PASS |
| `t8.maint.lot.engine` |  | HOSE lot 10 → 100: engine lines | — → **4** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| HOSE round lot 10 -> 100/ cell 4 | PASS |
| `t8.maint.krx.data` |  | KRX cutover: rule-data lines | — → **79** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| KRX trading-system cutover/ cell 2 | PASS |
| `t8.maint.krx.engine` |  | KRX cutover: engine lines | — → **20** | `docs/reference/tables/t8_maintenance_effort.md` @ `905f737` :: row /^\| KRX trading-system cutover/ cell 4 | PASS |
| `t8.validator.edges` |  | uncovered rule edges, all resolving to UNKNOWN | — → **12** | — | PENDING: Prose only (`docs/rivf26/NOTES-FOR-OWNER.md` §3.4, `LIMITATIONS.md` #8); pinned in `tests/market/session/test_rule_tables.py::OPEN_EDGES` but no committed result file. |
| `t8.properties` | `\nProperties` | Hypothesis properties | — → **14** | — | PENDING: Prose only (`NOTES-FOR-OWNER.md` §3.5). No committed result file; count from `tests/properties/` at freeze. |
| `t8.property_examples` | `\nPropertyExamples` | Hypothesis examples (plus 26 boundary cases) | — → **3,850** | — | PENDING: Prose only (`NOTES-FOR-OWNER.md` §3.5). No committed result file. |
| `t8.bench.at_per_sec` | `\nAtPerSec` | `Rulebook.at(ts)` resolutions per second (warm) | — → **TBD** | — | PENDING: T8.3 benchmark pending (CPU benchmark not yet run on a quiet machine; no committed result). |
| `t8.bench.orders_per_sec` | `\nOrdersPerSec` | orders per second through `ExchangeSession` | — → **TBD** | — | PENDING: T8.3 benchmark pending. Commit `af55e29` reports daily fill evaluation ~15,800 orders/s in its message only (not a result file). |
| `t8.bench.e1_wall` | `\EoneWall` | E1 wall time and peak RSS | — → **TBD** | — | PENDING: T8.3 benchmark pending. |

### Test-suite counts (F4)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest tests`; `pytest scenarios`; `pytest strategies` (each on its own)
- **Data slice:** shipped fixtures

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `tests.unit.passed` | `\nUnitTests` | unit tests passed | 1,646 → **2,169** | — | PENDING: To refresh at freeze: an engine fix in flight turns the 2 xfails into passes, and this checker's own test file adds tests. Recorded value from the coordinating session at `af55e29`; `pytest --collect-only` at `7fbe16b` gives 2,624 = 2,169 + 2 + 453. |
| `tests.unit.xfailed` |  | unit tests xfailed (strict) | — → **2** | — | PENDING: To refresh at freeze: an engine fix in flight turns the 2 xfails into passes, and this checker's own test file adds tests. Recorded value from the coordinating session at `af55e29`; `pytest --collect-only` at `7fbe16b` gives 2,624 = 2,169 + 2 + 453. |
| `tests.unit.skipped` |  | unit tests skipped (corpus-gated) | — → **453** | — | PENDING: To refresh at freeze: an engine fix in flight turns the 2 xfails into passes, and this checker's own test file adds tests. Recorded value from the coordinating session at `af55e29`; `pytest --collect-only` at `7fbe16b` gives 2,624 = 2,169 + 2 + 453. |
| `tests.scenarios` | `\nScenarioTests` | scenario tests passed (0 skipped) | 38 → **39** | — | PENDING: To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d. |
| `tests.strategies.passed` | `\nStrategyTests` | strategy tests passed | 11 → **18** | — | PENDING: To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d. |
| `tests.strategies.skipped` |  | strategy tests skipped (E1, F2 need corpus slices) | — → **2** | — | PENDING: To refresh at freeze. Recorded in `docs/rivf26/T0-audit.md` §4d. |

### Scenario and strategy findings quoted in the text

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest strategies/test_s2_*.py scenarios`
- **Data slice:** shipped fixtures

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `s2.loss` |  | S2 leveraged long: loss | — → **−77% (100M → 23.3M)** | — | PENDING: No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` §4b, §4d) and the test only pins it qualitatively. Needs a result file (or an exact pin) before freeze. |
| `s2.margin_calls` |  | S2 margin calls | — → **10** | — | PENDING: No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` §4b, §4d) and the test only pins it qualitatively. Needs a result file (or an exact pin) before freeze. |
| `s2.forced_tranches` | `\nStopSales` | S2 forced-sale tranches | three sales → **7** | — | PENDING: No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` §4b) and the test only pins it qualitatively. Needs a result file (or an exact pin) before freeze. |
| `s2.queue_ahead` |  | S2 2022-11-07: floor queue ahead at 10:00 vs volume after | — → **8,657,000 vs 775,000** | — | PENDING: No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` §4b (lock-queue table)) and the test only pins it qualitatively. Needs a result file (or an exact pin) before freeze. |
| `j18.deposit_step` |  | J18: deposit change at the 13% → 17% IM step | — → **+30.8%** | — | PENDING: No committed result file: the value is in prose (`docs/rivf26/T0-audit.md` §4d) and the test only pins it qualitatively. Needs a result file (or an exact pin) before freeze. |

### Table II, ProtoSmartBeta (null anchor)

- **Repo:** `ProtoSmartBeta` (branch `rivf26`, HEAD `02bc8ca` when generated)
- **Command:** `.venv/bin/python -m proto_smart_beta.experiments.null_anchor`
- **Data slice:** `data/market/<w>/`, `data/signal/<w>/` (DATA-MANIFESTs, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `sb.w2022.fills_naive` |  | w2022: naive fills | — → **457** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `naive.fills` | PASS |
| `sb.w2022.fills_faithful` |  | w2022: faithful fills | 2,257 (old OOS run) → **457** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `faithful.fills` | PASS |
| `sb.w2022.fn` | `\sbFillRange` | w2022: f/n fills | — → **100.0%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `comparison.fill_ratio_f_over_n` | PASS |
| `sb.w2022.hpr_naive` | `\sbHPRRange` | w2022: HPR naive | −3.17% → **−26.21%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `naive.hpr` | PASS |
| `sb.w2022.hpr_faithful` | `\sbHPRRange` | w2022: HPR faithful | −8.39% → **−27.08%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `faithful.hpr` | PASS |
| `sb.w2022.band_lock_no_fills` |  | w2022: band-lock no-fills (of 10 candidates) | **0** (unchanged) | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `tier1.band_lock_no_fills` | PASS |
| `sb.w2023.fills_naive` |  | w2023: naive fills | — → **727** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `naive.fills` | PASS |
| `sb.w2023.fills_faithful` |  | w2023: faithful fills | 2,257 (old OOS run) → **724** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `faithful.fills` | PASS |
| `sb.w2023.fn` | `\sbFillRange` | w2023: f/n fills | — → **99.6%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `comparison.fill_ratio_f_over_n` | PASS |
| `sb.w2023.hpr_naive` | `\sbHPRRange` | w2023: HPR naive | −3.17% → **+19.66%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `naive.hpr` | PASS |
| `sb.w2023.hpr_faithful` | `\sbHPRRange` | w2023: HPR faithful | −8.39% → **+17.68%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `faithful.hpr` | PASS |
| `sb.w2023.band_lock_no_fills` |  | w2023: band-lock no-fills (of 10 candidates) | **0** (unchanged) | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `tier1.band_lock_no_fills` | PASS |

### Table II, ProtoGrid

- **Repo:** `ProtoGrid` (branch `rivf26`, HEAD `199a61f` when generated)
- **Command:** `.venv/bin/pg-anchor`
- **Data slice:** `data/{band,tick}/<w>/` (DATA-MANIFEST in `data/manifest/<w>/`, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `grid.w2022_10.fills_naive` |  | w2022_10: naive fills | 1,457 → **136** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `naive.fills` | PASS |
| `grid.w2022_10.fills_faithful` |  | w2022_10: faithful fills | 151 → **62** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `faithful.fills` | PASS |
| `grid.w2022_10.fn` | `\gridFillRange` | w2022_10: f/n fills | ≈10% → **45.6%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `gap.fill_ratio_f_over_n` | PASS |
| `grid.w2022_10.hpr_naive` | `\gridHPRRange` | w2022_10: HPR naive | −19.0% → **−2.40%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `naive.hpr` | PASS |
| `grid.w2022_10.hpr_faithful` | `\gridHPRRange` | w2022_10: HPR faithful | −34.2% → **−2.65%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `faithful.hpr` | PASS |
| `grid.w2022_10.band_limit` |  | w2022_10: BAND_LIMIT refusals | — → **828** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `tier1.band_limit_refusals` | PASS |
| `grid.w2022_10.tick_grid` |  | w2022_10: TICK_GRID refusals | 2,409 → **0** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `tier1.tick_grid_refusals` | PASS |
| `grid.w2022_10.unsettled` |  | w2022_10: UNSETTLED_HOLDING refusals (T+2) | — → **58** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `tier1.unsettled_holding_refusals` | PASS |
| `grid.w2022_10.t2_locked` |  | w2022_10: T+2-locked re-buys (INSUFFICIENT_CASH) | 248 → **28** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: `tier1.t2_locked_rebuys` | PASS |
| `grid.w2021_11.fills_naive` |  | w2021_11: naive fills | 1,457 → **124** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `naive.fills` | PASS |
| `grid.w2021_11.fills_faithful` |  | w2021_11: faithful fills | 151 → **57** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `faithful.fills` | PASS |
| `grid.w2021_11.fn` | `\gridFillRange` | w2021_11: f/n fills | ≈10% → **46.0%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `gap.fill_ratio_f_over_n` | PASS |
| `grid.w2021_11.hpr_naive` | `\gridHPRRange` | w2021_11: HPR naive | −19.0% → **+1.47%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `naive.hpr` | PASS |
| `grid.w2021_11.hpr_faithful` | `\gridHPRRange` | w2021_11: HPR faithful | −34.2% → **+1.18%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `faithful.hpr` | PASS |
| `grid.w2021_11.band_limit` |  | w2021_11: BAND_LIMIT refusals | — → **784** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `tier1.band_limit_refusals` | PASS |
| `grid.w2021_11.tick_grid` |  | w2021_11: TICK_GRID refusals | 2,409 → **0** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `tier1.tick_grid_refusals` | PASS |
| `grid.w2021_11.unsettled` |  | w2021_11: UNSETTLED_HOLDING refusals (T+2) | — → **68** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `tier1.unsettled_holding_refusals` | PASS |
| `grid.w2021_11.t2_locked` |  | w2021_11: T+2-locked re-buys (INSUFFICIENT_CASH) | 248 → **3** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `199a61f` :: `tier1.t2_locked_rebuys` | PASS |
| `grid.min_fn` | `\gridFill` | Grid f/n, minimum over windows (abstract) | ≈10% → **45.6%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `199a61f` :: computed from `result/grid_anchor/w2022_10.json` `gap.fill_ratio_f_over_n`; `result/grid_anchor/w2021_11.json` `gap.fill_ratio_f_over_n` | PASS |

### Table II, ProtoPair

- **Repo:** `ProtoPair` (branch `rivf26`, HEAD `adee6db` when generated)
- **Command:** `.venv/bin/pp-anchor`; `.venv/bin/pp-credibility`
- **Data slice:** `data/market/<w>/` (DATA-MANIFEST, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `pair.w1.fills_naive` |  | w1: naive fills | 2,298 → **1,209** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `naive.fills` | PASS |
| `pair.w1.fills_faithful` |  | w1: faithful fills | 1,236 → **651** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `faithful.fills` | PASS |
| `pair.w1.fn` | `\pairFillRange` | w1: f/n fills | **53.8%** (unchanged) | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `gap.fills_f_over_n` | PASS |
| `pair.w1.hpr_naive` | `\pairHPRn` | w1: HPR naive | +3.5% → **+1.03%** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `gap.hpr_naive_pct` | PASS |
| `pair.w1.hpr_faithful` | `\pairHPRf` | w1: HPR faithful | −3.2% → **−2.15%** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `gap.hpr_faithful_pct` | PASS |
| `pair.w1.exits_blocked` | `\pairStuck` | w1: exits blocked by T+2 | 16 → **8** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `tier1.settlement_asymmetry.exits_blocked_by_t2` | PASS |
| `pair.w1.exits_wanted` |  | w1: exits wanted | 22 → **10** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `tier1.settlement_asymmetry.exits_wanted` | PASS |
| `pair.w1.name_days` | `\pairNameDays` | w1: name-days held open | 758 → **420** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `tier1.settlement_asymmetry.name_days_held_open` | PASS |
| `pair.w1.forgone` | `\pairSkipped` | w1: opposite-side trades forgone | 17 → **9** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `tier1.opposite_side.forgone` | PASS |
| `pair.w1.signalled` |  | w1: opposite-side trades signalled | 17 → **9** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `tier1.opposite_side.mirror_trades_signalled` | PASS |
| `pair.w1.soft_undecided_events` | `\pctPairUndecSoft` | w1: fill-time undecided events, `soft` | 2.2% → **0** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `variants.headline.fill_time_indeterminate_events` | PASS |
| `pair.w1.hard_fills` |  | w1: `hard` variant fills | 0 → **583** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `variants.hard.fills` | PASS |
| `pair.w1.hard_undecided_events` | `\pctPairUndecHard` | w1: fill-time undecided events, `hard` | 96.8% → **71** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `variants.hard.fill_time_indeterminate_events` | PASS: An event count; the old value was a rate. The result has no denominator for a `hard` rate. |
| `pair.w2.fills_naive` |  | w2: naive fills | 2,298 → **775** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `naive.fills` | PASS |
| `pair.w2.fills_faithful` |  | w2: faithful fills | 1,236 → **403** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `faithful.fills` | PASS |
| `pair.w2.fn` | `\pairFillRange` | w2: f/n fills | 53.8% → **52.0%** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `gap.fills_f_over_n` | PASS |
| `pair.w2.hpr_naive` | `\pairHPRRange` | w2: HPR naive | +3.5% → **+0.28%** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `gap.hpr_naive_pct` | PASS |
| `pair.w2.hpr_faithful` | `\pairHPRRange` | w2: HPR faithful | −3.2% → **−0.31%** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `gap.hpr_faithful_pct` | PASS |
| `pair.w2.exits_blocked` | `\pairStuck` | w2: exits blocked by T+2 | 16 → **4** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `tier1.settlement_asymmetry.exits_blocked_by_t2` | PASS |
| `pair.w2.exits_wanted` |  | w2: exits wanted | 22 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `tier1.settlement_asymmetry.exits_wanted` | PASS |
| `pair.w2.name_days` | `\pairNameDays` | w2: name-days held open | 758 → **180** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `tier1.settlement_asymmetry.name_days_held_open` | PASS |
| `pair.w2.forgone` | `\pairSkipped` | w2: opposite-side trades forgone | 17 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `tier1.opposite_side.forgone` | PASS |
| `pair.w2.signalled` |  | w2: opposite-side trades signalled | 17 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `tier1.opposite_side.mirror_trades_signalled` | PASS |
| `pair.w2.soft_undecided_events` | `\pctPairUndecSoft` | w2: fill-time undecided events, `soft` | 2.2% → **0** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `variants.headline.fill_time_indeterminate_events` | PASS |
| `pair.w2.hard_fills` |  | w2: `hard` variant fills | 0 → **377** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `variants.hard.fills` | PASS |
| `pair.w2.hard_undecided_events` | `\pctPairUndecHard` | w2: fill-time undecided events, `hard` | 96.8% → **27** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `variants.hard.fill_time_indeterminate_events` | PASS: An event count; the old value was a rate. The result has no denominator for a `hard` rate. |
| `pair.w1.adf_p` |  | w1 basis ADF p-value | — → **0.0000434** | ProtoPair: `result/credibility/w1.json` @ `0c8b77b` :: `adf_pvalue` | PASS |
| `pair.w2.adf_p` |  | w2 basis ADF p-value (does not reject a unit root) | — → **0.537** | ProtoPair: `result/credibility/w2.json` @ `0c8b77b` :: `adf_pvalue` | PASS |

### Table II, ProtoMarketMaker: anchor (faithful arm flat each session)

- **Repo:** `ProtoMarketMaker` (branch `rivf26`, HEAD `2134be5` when generated)
- **Command:** `.venv/bin/python -m proto_market_maker.experiments.mm_anchor <window>`
- **Data slice:** `data/{band,l2,market}/<window>/` (`data/<window>-MANIFEST.md`, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `mm.krx2025.fills_naive` |  | krx2025, all 40 sessions: naive fills | 910 → **693** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `naive.fills` | PASS |
| `mm.krx2025.hpr_naive` |  | krx2025, 40 sessions: HPR naive | 56.75% → **+29.57%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `naive.hpr` | PASS |
| `mm.krx2025.fills_naive_pre` |  | krx2025, 20 pre-cutover sessions: naive fills | — → **228** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `naive_pre_cutover_only.fills` | PASS |
| `mm.krx2025.hpr_naive_pre` |  | krx2025, pre-cutover: HPR naive | — → **−5.22%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `naive_pre_cutover_only.hpr` | PASS |
| `mm.krx2025.fills_faithful` | `\mmFillsF` | krx2025: faithful fills, conservative | 402 → **116** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `faithful.fills` | PASS |
| `mm.krx2025.fills_opt` | `\mmFillsOpt` | krx2025: faithful fills, optimistic | — → **160** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `faithful_by_queue.optimistic.fills` | PASS |
| `mm.krx2025.hpr_faithful` |  | krx2025: HPR faithful, conservative | 31.62% → **−6.03%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `faithful.hpr` | PASS |
| `mm.krx2025.fn` | `\mmFillRange` | krx2025: f/n, all 40 sessions | 44% (402/910) → **16.7%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `fills_ratio_f_over_n` | PASS |
| `mm.krx2025.fn_pre` | `\mmFillRange` | krx2025: f/n, 20 pre-cutover sessions (like for like) | — → **50.9%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: computed from `result/mm_anchor/krx2025.json` `faithful.fills`; `result/mm_anchor/krx2025.json` `naive_pre_cutover_only.fills` | PASS |
| `mm.krx2025.queue_spread` | `\pctMMQueueSwing` | krx2025: queue spread (opt − cons) / opt | — → **27.5%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `tier1.queue_fill_spread.conservative_vs_optimistic_pct` | PASS |
| `mm.krx2025.undecided_pre` | `\pctMMUndecPre` | krx2025: conservative undecided orders, pre-cutover | 99.94% → **99.76%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `faithful.krx.pre.indeterminate_order_rate` | PASS: Old value counted fill-evaluation events; the new one counts orders. Post-cutover has no orders. |
| `mm.krx2025.refused_post` |  | krx2025: post-cutover sessions refused (of 20) | — → **20** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `b9f4b0b` :: `tier1.post_cutover_refused_sessions` | PASS |
| `mm.im2022.fills_naive` |  | im2022: naive fills | — → **129** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `naive.fills` | PASS |
| `mm.im2022.hpr_naive` |  | im2022: HPR naive | — → **−12.93%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `naive.hpr` | PASS |
| `mm.im2022.fills_faithful` |  | im2022: faithful fills, conservative | — → **70** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.fills` | PASS |
| `mm.im2022.fills_opt` |  | im2022: faithful fills, optimistic | — → **98** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful_by_queue.optimistic.fills` | PASS |
| `mm.im2022.hpr_faithful` |  | im2022: HPR faithful, conservative (flat each session) | — → **+2.19%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.hpr` | PASS |
| `mm.im2022.fn` | `\mmFillRange` | im2022: f/n | — → **54.3%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `fills_ratio_f_over_n` | PASS |
| `mm.im2022.queue_spread` |  | im2022: queue spread | — → **28.6%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `tier1.queue_fill_spread.conservative_vs_optimistic_pct` | PASS |
| `mm.im2022.undecided_pre` |  | im2022: conservative undecided orders, before 2022-12-15 | — → **99.87%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.im_step.pre.indeterminate_order_rate` | PASS |
| `mm.im2022.undecided_post` | `\pctMMUndecPost` | im2022: conservative undecided orders, from 2022-12-15 | — → **99.99%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.im_step.post.indeterminate_order_rate` | PASS |
| `mm.deposit` | `\mmDeposit` | MM deposit (đ) | — → **500,000,000** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.deposit_dong` | PASS |
| `mm.contracts_pre` | `\mmContractsPre` | dated-IM capacity on 2022-12-14 (13%) | 37 → **36** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.capacity.[date=2022-12-14].contracts` | PASS |
| `mm.contracts_post` | `\mmContractsPost` | dated-IM capacity on 2022-12-15 (17%) | **28** (unchanged) | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `b9f4b0b` :: `faithful.capacity.[date=2022-12-15].contracts` | PASS |

### ProtoMarketMaker attribution ladder (algorithm A fixed)

- **Repo:** `ProtoMarketMaker` (branch `rivf26`, HEAD `2134be5` when generated)
- **Command:** `.venv/bin/python -m proto_market_maker.experiments.mm_faithful_a <window> --queue <q>`, then `.venv/bin/python -m proto_market_maker.experiments.mm_ladder <window>`
- **Data slice:** as the MM anchor

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `ladder.im2022.n0.hpr` |  | im2022: N0 HPR | — → **−12.93%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N0 \|/ cell 5 | PASS |
| `ladder.im2022.n0.fills` |  | im2022: N0 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N0 \|/ cell 2 | PASS |
| `ladder.im2022.n1.hpr` |  | im2022: N1 HPR | — → **−15.90%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N1 \|/ cell 5 | PASS |
| `ladder.im2022.n1.fills` |  | im2022: N1 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N1 \|/ cell 2 | PASS |
| `ladder.im2022.n2.hpr` |  | im2022: N2 HPR | — → **−15.90%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N2 \|/ cell 5 | PASS |
| `ladder.im2022.n2.fills` |  | im2022: N2 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N2 \|/ cell 2 | PASS |
| `ladder.im2022.n3.hpr` |  | im2022: N3 HPR | — → **−16.42%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N3 \|/ cell 5 | PASS |
| `ladder.im2022.n3.fills` |  | im2022: N3 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| N3 \|/ cell 2 | PASS |
| `ladder.im2022.f-opt.hpr` |  | im2022: F-opt HPR | — → **−2.52%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| F\-opt \|/ cell 5 | PASS |
| `ladder.im2022.f-opt.fills` |  | im2022: F-opt fills | — → **198** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| F\-opt \|/ cell 2 | PASS |
| `ladder.im2022.f-con.hpr` |  | im2022: F-con HPR | — → **−11.47%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| F\-con \|/ cell 5 | PASS |
| `ladder.im2022.f-con.fills` |  | im2022: F-con fills | — → **116** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| F\-con \|/ cell 2 | PASS |
| `ladder.im2022.json_agrees` |  | im2022: ladder JSON HPRs equal the markdown (6 rungs) | — → **6** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `f0894d5` :: `result/mm_ladder/im2022.json` `rungs[].hpr` vs `result/mm_ladder/im2022.md` | PASS |
| `ladder.im2022.f-opt.fn` |  | im2022: F-opt fills / N0 fills | — → **153.5%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: computed from `result/mm_ladder/im2022.md` row /^\| F-opt \|/ cell 2; `result/mm_ladder/im2022.md` row /^\| N0 \|/ cell 2 | PASS: Above 100%: §6 criterion 1 (faithful fills < naive) fails for this arm. |
| `ladder.im2022.f-opt.source_sha` |  | im2022: F-opt faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `f0894d5` :: sha256 of the file at `faithful_sources.F-opt.path` vs `faithful_sources.F-opt.sha256` | PASS |
| `ladder.im2022.f-con.fn` |  | im2022: F-con fills / N0 fills | — → **89.9%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: computed from `result/mm_ladder/im2022.md` row /^\| F-con \|/ cell 2; `result/mm_ladder/im2022.md` row /^\| N0 \|/ cell 2 | PASS |
| `ladder.im2022.f-con.source_sha` |  | im2022: F-con faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `f0894d5` :: sha256 of the file at `faithful_sources.F-con.path` vs `faithful_sources.F-con.sha256` | PASS |
| `ladder.krx2025.n0.hpr` |  | krx2025: N0 HPR | — → **−5.22%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N0 \|/ cell 5 | PASS |
| `ladder.krx2025.n0.fills` |  | krx2025: N0 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N0 \|/ cell 2 | PASS |
| `ladder.krx2025.n1.hpr` |  | krx2025: N1 HPR | — → **−14.09%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N1 \|/ cell 5 | PASS |
| `ladder.krx2025.n1.fills` |  | krx2025: N1 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N1 \|/ cell 2 | PASS |
| `ladder.krx2025.n2.hpr` |  | krx2025: N2 HPR | — → **−14.09%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N2 \|/ cell 5 | PASS |
| `ladder.krx2025.n2.fills` |  | krx2025: N2 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N2 \|/ cell 2 | PASS |
| `ladder.krx2025.n3.hpr` |  | krx2025: N3 HPR | — → **−15.02%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N3 \|/ cell 5 | PASS |
| `ladder.krx2025.n3.fills` |  | krx2025: N3 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| N3 \|/ cell 2 | PASS |
| `ladder.krx2025.f-opt.hpr` |  | krx2025: F-opt HPR | — → **−7.58%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| F\-opt \|/ cell 5 | PASS |
| `ladder.krx2025.f-opt.fills` |  | krx2025: F-opt fills | — → **261** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| F\-opt \|/ cell 2 | PASS |
| `ladder.krx2025.f-con.hpr` |  | krx2025: F-con HPR | — → **−25.55%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| F\-con \|/ cell 5 | PASS |
| `ladder.krx2025.f-con.fills` |  | krx2025: F-con fills | — → **153** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| F\-con \|/ cell 2 | PASS |
| `ladder.krx2025.json_agrees` |  | krx2025: ladder JSON HPRs equal the markdown (6 rungs) | — → **6** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `f0894d5` :: `result/mm_ladder/krx2025.json` `rungs[].hpr` vs `result/mm_ladder/krx2025.md` | PASS |
| `ladder.krx2025.f-opt.fn` |  | krx2025: F-opt fills / N0 fills | — → **114.5%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: computed from `result/mm_ladder/krx2025.md` row /^\| F-opt \|/ cell 2; `result/mm_ladder/krx2025.md` row /^\| N0 \|/ cell 2 | PASS: Above 100%: §6 criterion 1 (faithful fills < naive) fails for this arm. |
| `ladder.krx2025.f-opt.source_sha` |  | krx2025: F-opt faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `f0894d5` :: sha256 of the file at `faithful_sources.F-opt.path` vs `faithful_sources.F-opt.sha256` | PASS |
| `ladder.krx2025.f-con.fn` |  | krx2025: F-con fills / N0 fills | — → **67.1%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: computed from `result/mm_ladder/krx2025.md` row /^\| F-con \|/ cell 2; `result/mm_ladder/krx2025.md` row /^\| N0 \|/ cell 2 | PASS |
| `ladder.krx2025.f-con.source_sha` |  | krx2025: F-con faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `f0894d5` :: sha256 of the file at `faithful_sources.F-con.path` vs `faithful_sources.F-con.sha256` | PASS |
| `ladder.im2022.f-con.undecided` |  | im2022: F-con undecided orders | — → **99.88%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `f0894d5` :: row /^\| F-con \|/ cell 7 | PASS |
| `ladder.krx2025.f-con.undecided` |  | krx2025: F-con undecided orders | — → **99.63%** | ProtoMarketMaker: `result/mm_ladder/krx2025.md` @ `f0894d5` :: row /^\| F-con \|/ cell 7 | PASS |
| `ladder.markout.naive` |  | 5-min markout per fill, naive (pts) | — → **−2.24** | — | PENDING: Pending (full-window run in progress). Current value is from the first 6 im2022 sessions (`NOTES-FOR-OWNER.md` §4.2); no committed result file. |
| `ladder.markout.faithful` |  | 5-min markout per fill, faithful (pts) | — → **−0.78** | — | PENDING: Pending (full-window run in progress). First 6 im2022 sessions only; no committed result file. |
| `ladder.markout.ghost` |  | 1-min markouts (no ghost fills) | — → **TBD** | — | PENDING: Pending (full-window run in progress). |

### Data-slice integrity (sha256 of every committed slice file vs its manifest)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `ee16521` when generated)
- **Command:** this checker
- **Data slice:** each manifest named in the row

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `slice.sim.scenarios.fixtures.daily` |  | `scenarios/fixtures/daily/DATA-MANIFEST.md`: files matching sha256 | — → **9** | `scenarios/fixtures/daily/DATA-MANIFEST.md` @ `5314bb6` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.scenarios.fixtures.book` |  | `scenarios/fixtures/book/DATA-MANIFEST.md`: files matching sha256 | — → **12** | `scenarios/fixtures/book/DATA-MANIFEST.md` @ `5314bb6` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.parquet` |  | `strategies/fixtures/parquet/DATA-MANIFEST.md`: files matching sha256 | — → **9** | `strategies/fixtures/parquet/DATA-MANIFEST.md` @ `5314bb6` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.s2_lock.daily` |  | `strategies/fixtures/s2_lock/daily/DATA-MANIFEST.md`: files matching sha256 | — → **4** | `strategies/fixtures/s2_lock/daily/DATA-MANIFEST.md` @ `1a98db6` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.s2_lock.book` |  | `strategies/fixtures/s2_lock/book/DATA-MANIFEST.md`: files matching sha256 | — → **4** | `strategies/fixtures/s2_lock/book/DATA-MANIFEST.md` @ `1a98db6` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.tests.market.session.fixtures.book_walk` |  | `tests/market/session/fixtures/book_walk/DATA-MANIFEST.md`: files matching sha256 | — → **8** | `tests/market/session/fixtures/book_walk/DATA-MANIFEST.md` @ `f0434dc` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.market.w2022.manifest` |  | ProtoSmartBeta `data/market/w2022/DATA-MANIFEST.md`: files matching sha256 | — → **9** | ProtoSmartBeta: `data/market/w2022/DATA-MANIFEST.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.market.w2023.manifest` |  | ProtoSmartBeta `data/market/w2023/DATA-MANIFEST.md`: files matching sha256 | — → **9** | ProtoSmartBeta: `data/market/w2023/DATA-MANIFEST.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.signal.w2022.manifest` |  | ProtoSmartBeta `data/signal/w2022/DATA-MANIFEST.md`: files matching sha256 | — → **1** | ProtoSmartBeta: `data/signal/w2022/DATA-MANIFEST.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS: The manifest lists an empty (0-row) ticker master that was not copied into the repo. |
| `slice.smartbeta.signal.w2023.manifest` |  | ProtoSmartBeta `data/signal/w2023/DATA-MANIFEST.md`: files matching sha256 | — → **1** | ProtoSmartBeta: `data/signal/w2023/DATA-MANIFEST.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS: The manifest lists an empty (0-row) ticker master that was not copied into the repo. |
| `slice.smartbeta.signal.w2022.manifest-financial` |  | ProtoSmartBeta `data/signal/w2022/DATA-MANIFEST-financial.md`: files matching sha256 | — → **1** | ProtoSmartBeta: `data/signal/w2022/DATA-MANIFEST-financial.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.signal.w2023.manifest-financial` |  | ProtoSmartBeta `data/signal/w2023/DATA-MANIFEST-financial.md`: files matching sha256 | — → **1** | ProtoSmartBeta: `data/signal/w2023/DATA-MANIFEST-financial.md` @ `b82c6f2` :: files whose sha256 matches the manifest | PASS |
| `slice.pair.market.w1.manifest` |  | ProtoPair `data/market/w1/DATA-MANIFEST.md`: files matching sha256 | — → **11** | ProtoPair: `data/market/w1/DATA-MANIFEST.md` @ `0c8b77b` :: files whose sha256 matches the manifest | PASS |
| `slice.pair.market.w2.manifest` |  | ProtoPair `data/market/w2/DATA-MANIFEST.md`: files matching sha256 | — → **11** | ProtoPair: `data/market/w2/DATA-MANIFEST.md` @ `0c8b77b` :: files whose sha256 matches the manifest | PASS |
| `slice.grid.manifest.w2021_11.manifest` |  | ProtoGrid `data/manifest/w2021_11/DATA-MANIFEST.md`: files matching sha256 | — → **8** | ProtoGrid: `data/manifest/w2021_11/DATA-MANIFEST.md` @ `199a61f` :: files whose sha256 matches the manifest | PASS |
| `slice.grid.manifest.w2022_10.manifest` |  | ProtoGrid `data/manifest/w2022_10/DATA-MANIFEST.md`: files matching sha256 | — → **8** | ProtoGrid: `data/manifest/w2022_10/DATA-MANIFEST.md` @ `199a61f` :: files whose sha256 matches the manifest | PASS |
| `slice.marketmaker.im2022.manifest` |  | ProtoMarketMaker `data/im2022-MANIFEST.md`: files matching sha256 | — → **12** | ProtoMarketMaker: `data/im2022-MANIFEST.md` @ `f0894d5` :: files whose sha256 matches the manifest | PASS |
| `slice.marketmaker.krx2025.manifest` |  | ProtoMarketMaker `data/krx2025-MANIFEST.md`: files matching sha256 | — → **12** | ProtoMarketMaker: `data/krx2025-MANIFEST.md` @ `f0894d5` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.result.w2022` |  | SB `result/null_anchor/w2022.json` recorded slice sha256 match the committed files | — → **11** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `02bc8ca` :: `provenance.slices` sha256 vs the committed files | PASS |
| `slice.smartbeta.result.w2023` |  | SB `result/null_anchor/w2023.json` recorded slice sha256 match the committed files | — → **11** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `02bc8ca` :: `provenance.slices` sha256 vs the committed files | PASS |
| `slice.pair.result.w1` |  | Pair `result/pair_anchor/w1.json` recorded slice sha256 match the committed files | — → **11** | ProtoPair: `result/pair_anchor/w1.json` @ `adee6db` :: `slice` sha256 vs the committed files | PASS |
| `slice.pair.result.w2` |  | Pair `result/pair_anchor/w2.json` recorded slice sha256 match the committed files | — → **11** | ProtoPair: `result/pair_anchor/w2.json` @ `adee6db` :: `slice` sha256 vs the committed files | PASS |

<!-- END GENERATED -->
