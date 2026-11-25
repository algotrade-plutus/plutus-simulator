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

**Status when generated:** 339 entries: 339 PASS, 0 FAIL, 0 PENDING. The test counts and the numbers that once
existed only in prose (S2, J18, the property-test and validator counts) are now read from
`docs/reference/tables/camera_ready_pins.json`, written by `measurements/camera_ready_pins.py --tests` (rerun it at
freeze if a test is added).

## Conventions

- **Tolerance.** A stated value passes if the source rounds to it: half a unit in the last stated digit
  (31.43% passes for 0.31426; −76.4% for −0.764458). Counts must match exactly.
- **Queue swing (F5)** is always relative to the optimistic arm: (optimistic − conservative) / optimistic.
- **Commit** in each row is the last commit that touched the source file, in that file's repo, when this map
  was generated. All repos are on branch `rivf26` (local commits only).
- **Macro** is the `paper/numbers.tex` macro the value fills (handoff §9). A blank macro means the number is
  quoted in the text or a table without its own macro, or is a check that backs one.
- MM provenance: the four faithful-A runs, the ladders, the markouts and both anchors were rerun on
  plutus-simulator `8d46c56` (ProtoMarketMaker `4474777`); each result JSON records that commit at start and end.

## MM rerun 2026-11-25 (plutus-simulator `8d46c56`, ProtoMarketMaker `4474777`)

- **What moved: krx2025 after the cutover, only.** `4867d46` sources the post-KRX margin rule (QĐ 26's two layers:
  broker IM intraday, VSDC CCP requirement after the close; `T0-audit.md` §4j). The engine's margin model is no
  longer unresolved after 2025-05-05, so MM's guard accepts it and krx2025 trades all 40 sessions instead of
  refusing the 20 post-cutover ones. The krx2025 slice gained the VN30 index close (40 rows) that the CCP layer
  reads; its manifest and the MM byte count changed accordingly (krx2025 16,352,393 B).
- **Anchor, krx2025 (40 sessions):** faithful 116 → **366** fills (optimistic 160 → **444**), HPR −6.03% →
  **−0.73%**, f/n 16.7% → **52.8%**, queue spread 27.5% → **17.6%**, refused post-cutover sessions 20 → **0**.
  The like-for-like pre-cutover f/n stays **50.9%** (116 / 228).
- **Ladder, krx2025:** the markdown's first table is now the whole window; the JSON adds `views.pre_cutover`
  (unchanged: N0 −5.22%, N3 −15.02%, F-opt −7.58%, F-con −25.55%) and `views.post_cutover` (N0 +36.70%,
  N3 −35.01%, F-opt −4.81%, F-con −23.39%). F-con over the window: 31 margin calls, 3 forced liquidations executed;
  CCP layer: 0 indeterminate nights and 0 calendar-spread UNKNOWN in both queues.
- **Markouts:** full-window results replace the withdrawn 6-session figures (−2.24 / −0.78; withdrawn for a
  roll-day marking bug, owner notes `d0623bd`). The 1-min F-opt markout is kept only as the record for the
  withdrawn "no ghost fills" claim.
- **Unchanged:** im2022 (anchor and ladder) and every krx2025 pre-cutover number. `ba0d9f4` (band-edge orders on
  book sessions) and `6e6c104` (soft market-order evidence label) change no MM number.

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
| MM anchor (faithful flat each session, conservative) | krx2025, 40 sessions | 52.8% (366 / 693) | +29.57% → −0.73% | pass / pass |
| MM anchor | krx2025, 20 pre-cutover sessions | 50.9% (116 / 228) | −5.22% → (anchor HPR is whole-window only) | pass / — |
| MM anchor | im2022 | 54.3% (70 / 129) | −12.93% → +2.19% | pass / **fail** |
| MM ladder (A fixed), F-con vs N0 | im2022 | 89.9% (116 / 129) | −12.93% → −11.47% | pass / **fail** |
| MM ladder, F-opt vs N0 | im2022 | 153.5% (198 / 129) | −12.93% → −2.52% | **fail** / **fail** |
| MM ladder, F-con vs N0 | krx2025, 40 sessions | 51.7% (358 / 693) | +29.57% → −42.96% | pass / pass |
| MM ladder, F-opt vs N0 | krx2025, 40 sessions | 83.0% (575 / 693) | +29.57% → −12.02% | pass / pass |
| MM ladder, F-con vs N0 | krx2025 pre-cutover | 67.1% (153 / 228) | −5.22% → −25.55% | pass / pass |
| MM ladder, F-opt vs N0 | krx2025 pre-cutover | 114.5% (261 / 228) | −5.22% → −7.58% | **fail** / pass |
| MM ladder, F-con vs N0 | krx2025 post-cutover | 44.1% (205 / 465) | +36.70% → −23.39% | pass / pass |
| MM ladder, F-opt vs N0 | krx2025 post-cutover | 67.5% (314 / 465) | +36.70% → −4.81% | pass / pass |

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
| ProtoMarketMaker `data/{band,l2,market}/<w>/` | MM anchor and ladder | ProtoMarketMaker | `data/<w>-MANIFEST.md` (checked) | 25,078,745 (im2022 8,726,352; krx2025 16,352,393): over the size flag, owner sign-off |

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

1. **F2 figure data was stale. Fixed.** `figures/f2_indeterminate_rate.json` held the old 66-day population
   (bar 35.8%, tick optimistic 85.6%, tick conservative 99.7%), while `docs/rivf26/T0-audit.md` §4h said F2 was
   regenerated (`b8c1488` changed only the PNG). It is now re-rendered from
   `docs/reference/tables/t2/indeterminate_after_change2.json` by `measurements/indeterminate_rate.py --from-json`
   (90 days, 32.6% / 10.1% / 60.2%): the JSON is byte-identical to the T2 file, and the re-rendered PNG is
   byte-identical to the committed one, so the PNG was already right. §4h is corrected; `f2.figure.*` checks it.
2. **Unit-test count.** `docs/rivf26/T0-audit.md` §4h: "2,162 passed, 2 xfailed, 453 skipped"; the
   coordinating session's later count was 2,169 + 2 xfailed (`pytest --collect-only tests` at `473166f`: 2,624 =
   2,169 + 2 + 453). §4i, after the band-edge fix: **2,180 passed, 0 xfailed, 453 skipped** (now the recorded
   value). That predates `tests/test_check_numbers.py` (7 tests), so the count is still to refresh at freeze.
3. **ProtoPair README engine commit. Fixed** (ProtoPair `77aa71f`). The README headed its results "plutus-simulator
   `17b58a6`"; both `result/pair_anchor/w*.json` record `566fda4`, which the README now states.
4. **MM contract capacity at the IM step: 36 → 28, from the run** (`result/mm_anchor/im2022.json`
   `faithful.capacity`, 2022-12-14 → 2022-12-15). The plutus-simulator docs written for the camera-ready already
   say 36 → 28 (`NOTES-FOR-OWNER.md` §2, this map, `experiments_registry.md`, ProtoMarketMaker `README.md`).
   Only the submission text and handoff §5 T5 still say "37 → 28"; the paper takes 36 → 28.
5. **MM return for im2022 depends on which faithful arm.** `NOTES-FOR-OWNER.md` §2 and the MM README anchor
   table: faithful +2.19% vs naive −12.93% (flat each session, `result/mm_anchor/im2022.json`). The ladder
   (`result/mm_ladder/im2022.md`, algorithm A with overnight carry): F-con −11.47%, F-opt −2.52%. Both are
   committed results of different designs, not a contradiction; the owner picks Table II's arm.
6. **MM undecided pre/post at the KRX cutover. Settled by the rerun.** krx2025 now has post-cutover orders, so
   the cutover comparison exists on one measure: conservative undecided **orders** 99.76% pre → **99.21%** post
   (`result/mm_anchor/krx2025.json` `faithful.krx.{pre,post}.indeterminate_order_rate`; macros `\pctMMUndecPre`,
   `\pctMMUndecPost`). The submission's "rising from 99.94% to 99.92%" counted fill-evaluation **events** and in
   fact fell; the new pair also falls. The paper should say "orders" and "falls slightly". (The im2022 IM step,
   99.87% → 99.99%, stays registered without a macro.)
7. **Maintenance effort for the IM step. Fixed.** `T0-audit.md` §4g said "data-only (one tuple line)";
   `docs/reference/tables/t8_maintenance_effort.md` gives 15 rule-data lines in 2 units (the tuple line plus the
   14-line cited rulebook row), 0 engine lines, 3 undated copies. §4g and `NOTES-FOR-OWNER.md` §3.6 now say so;
   `\nMaintDataLines` = 15, `\nMaintCodeLines` = 0.
8. **Slice sizes. Fixed.** `data_provenance.md` said MM was 29 MB and `NOTES-FOR-OWNER.md` §2 said 15.1 MB and
   8.2 MB; the smaller fixtures were also off (40 KB, 88 KB, 224 KB, ...). Both docs now give exact committed
   bytes: MM 25,078,745 B (krx2025 16,352,393; im2022 8,726,352), and every other row of the provenance table.
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
- **F2 rerun after the band-edge fix `ba0d9f4` (2026-11-25, engine `51344fb`).** The 48 `{book, low}` evaluations
  per tick arm are gone: tick optimistic 10.1% → **7.1%**, tick conservative 60.2% → **58.7%**, bar unchanged at
  32.6%. Result: `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json`; the figure is re-rendered from it.
  The reversal (tick below bar) is stronger.
- `strategies/fixtures/extract/` has no sha256 manifest, so the S9 queue numbers have no slice hash.
- Numbers that once existed only in prose (S2, J18, validator edges, property counts) and the test counts are
  pinned in `docs/reference/tables/camera_ready_pins.json` (`measurements/camera_ready_pins.py`).

## The map

<!-- BEGIN GENERATED: measurements/check_numbers.py --write-doc -->

### E1: fill-policy divergence over the 2022 HSX population

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `PYTHONPATH=src:. python -m measurements.e1_regenerate run --data-dir <rivf26-data>/t2-e1`, then `python measurements/e1_publish.py --data-root <rivf26-data>/t2-e1 --out docs/reference/tables/t2/e1_published`
- **Data slice:** `rivf26/data/t2-e1/` (391 HSX tickers, 2022; not shipped, statistics only; sha256 in the map's slice table)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `e1.decisions` | `\nDecisions` | decisions (5 intents × ticker-days) | 477,537 → **484,949** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b1390b` :: `questions` | PASS |
| `e1.agreed` |  | decisions on which all three policies agree | — → **332,549** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b1390b` :: `agreed` | PASS |
| `e1.tickers` | `\nEoneTickers` | tickers (HSX stocks, ≥200 sessions in 2022) | 385 → **391** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b1390b` :: `tickers` | PASS |
| `e1.ticker_days` |  | ticker-days | 95,815 → **97,269** | `docs/reference/tables/t2/e1_published/totals.json` @ `5b1390b` :: `ticker_days` | PASS |
| `e1.agree` | `\pctPolicyAgree` | policies agree | 68.4% → **68.57%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `agreement.p` | PASS |
| `e1.disagree` | `\pctPolicyDisagree` | policies disagree | 31.6% → **31.43%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `disagreement.p` | PASS |
| `e1.disagree.wilson_lo` |  | disagree, Wilson 95% low | 31.50 → **31.30%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `disagreement.wilson95.0` | PASS |
| `e1.disagree.wilson_hi` |  | disagree, Wilson 95% high | 31.76 → **31.56%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `disagreement.wilson95.1` | PASS |
| `e1.disagree.boot_lo` |  | disagree, ticker-cluster bootstrap 95% low | — → **30.97%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `disagreement.cluster_boot95.0` | PASS |
| `e1.disagree.boot_hi` |  | disagree, ticker-cluster bootstrap 95% high | — → **31.84%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `disagreement.cluster_boot95.1` | PASS |
| `e1.published.n_sum_month` |  | published by-month table sums to the decisions | — → **484,949** | `docs/reference/tables/t2/e1_published/by_month_intent.csv` @ `5b1390b` :: sum of column `n` | PASS |
| `e1.published.agreed_sum_month` |  | published by-month table sums to the agreed | — → **332,549** | `docs/reference/tables/t2/e1_published/by_month_intent.csv` @ `5b1390b` :: sum of column `agreed` | PASS |
| `e1.published.n_sum_ticker` |  | published by-ticker table sums to the decisions | — → **484,949** | `docs/reference/tables/t2/e1_published/by_ticker_intent.csv` @ `5b1390b` :: sum of column `n` | PASS |
| `e1.published.agreed_sum_ticker` |  | published by-ticker table sums to the agreed | — → **332,549** | `docs/reference/tables/t2/e1_published/by_ticker_intent.csv` @ `5b1390b` :: sum of column `agreed` | PASS |
| `e1.figure.decisions` |  | figure data (`figures/e1_fill_divergence.json`) carries the same N | 477,537 → **484,949** | `figures/e1_fill_divergence.json` @ `b8c1488` :: `questions` | PASS |
| `e1.figure.agree` |  | figure data agreement rate | 68.4% → **68.57%** | `figures/e1_fill_divergence.json` @ `b8c1488` :: `agreement_rate` | PASS |
| `e1.disagree.market_buy` |  | policies disagree: market order | 95.5% → **95.44%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.market_buy.disagreement.p` | PASS |
| `e1.disagree.limit_buy_at_close` |  | policies disagree: limit buy at close | 23.1% → **23.13%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_close.disagreement.p` | PASS |
| `e1.disagree.limit_sell_at_close` |  | policies disagree: limit sell at close | 23.3% → **23.52%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_close.disagreement.p` | PASS |
| `e1.disagree.limit_buy_at_floor` |  | policies disagree: limit buy at floor | 9.9% → **9.15%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_floor.disagreement.p` | PASS |
| `e1.disagree.limit_sell_at_ceil` |  | policies disagree: limit sell at ceiling | 6.0% → **5.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_ceil.disagreement.p` | PASS |
| `e1.fill.market_buy.soft` |  | fill rate, market_buy, `soft` | 89.21% → **89.14%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.market_buy.fill.soft.p` | PASS |
| `e1.fill.market_buy.hard` |  | fill rate, market_buy, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.market_buy.fill.hard.p` | PASS |
| `e1.fill.market_buy.probabilistic` |  | fill rate, market_buy, `probabilistic` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.market_buy.fill.probabilistic.p` | PASS |
| `e1.fill.limit_buy_at_close.soft` |  | fill rate, limit_buy_at_close, `soft` | 89.20% → **89.13%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_close.fill.soft.p` | PASS |
| `e1.fill.limit_buy_at_close.hard` |  | fill rate, limit_buy_at_close, `hard` | 72.32% → **72.30%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_close.fill.hard.p` | PASS |
| `e1.fill.limit_buy_at_close.probabilistic` |  | fill rate, limit_buy_at_close, `probabilistic` | 80.73% → **80.68%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_close.fill.probabilistic.p` | PASS |
| `e1.fill.limit_sell_at_close.soft` |  | fill rate, limit_sell_at_close, `soft` | 89.21% → **89.14%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_close.fill.soft.p` | PASS |
| `e1.fill.limit_sell_at_close.hard` |  | fill rate, limit_sell_at_close, `hard` | 72.81% → **72.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_close.fill.hard.p` | PASS |
| `e1.fill.limit_sell_at_close.probabilistic` |  | fill rate, limit_sell_at_close, `probabilistic` | 81.11% → **80.92%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_close.fill.probabilistic.p` | PASS |
| `e1.fill.limit_buy_at_floor.soft` |  | fill rate, limit_buy_at_floor, `soft` | 9.47% → **8.74%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_floor.fill.soft.p` | PASS |
| `e1.fill.limit_buy_at_floor.hard` |  | fill rate, limit_buy_at_floor, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_floor.fill.hard.p` | PASS |
| `e1.fill.limit_buy_at_floor.probabilistic` |  | fill rate, limit_buy_at_floor, `probabilistic` | 4.74% → **4.39%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_buy_at_floor.fill.probabilistic.p` | PASS |
| `e1.fill.limit_sell_at_ceil.soft` |  | fill rate, limit_sell_at_ceil, `soft` | 5.64% → **5.21%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_ceil.fill.soft.p` | PASS |
| `e1.fill.limit_sell_at_ceil.hard` |  | fill rate, limit_sell_at_ceil, `hard` | 0% → **0.00%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_ceil.fill.hard.p` | PASS |
| `e1.fill.limit_sell_at_ceil.probabilistic` |  | fill rate, limit_sell_at_ceil, `probabilistic` | 2.76% → **2.55%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_intent.limit_sell_at_ceil.fill.probabilistic.p` | PASS |
| `e1.undecided.hard` |  | undecided share, `hard` | 33.4% → **33.26%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_policy.hard.indeterminate.p` | PASS |
| `e1.undecided.soft` |  | undecided share, `soft` | 2.7% → **2.75%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_policy.soft.indeterminate.p` | PASS |
| `e1.undecided.probabilistic` |  | undecided share, `probabilistic` | 21.0% → **20.97%** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `by_policy.probabilistic.indeterminate.p` | PASS |
| `e1.shares.soft` | `\sharesSoft` | filled shares, `soft` | 245.8M → **247,376,400** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `executed_quantity.soft` | PASS |
| `e1.shares.hard` | `\sharesHard` | filled shares, `hard` | 128.5M → **129,818,200** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `executed_quantity.hard` | PASS |
| `e1.shares.probabilistic` |  | filled shares, `probabilistic` | 148M → **149,450,400** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `executed_quantity.probabilistic` | PASS |
| `e1.shares.ratio` | `\xSharesSoftHard` | filled shares, soft / hard | 1.91× → **1.91** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `soft_over_hard_quantity.ratio` | PASS |
| `e1.shares.ratio.boot_lo` |  | soft / hard ratio, bootstrap 95% low | — → **1.89** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `soft_over_hard_quantity.cluster_boot95.0` | PASS |
| `e1.shares.ratio.boot_hi` |  | soft / hard ratio, bootstrap 95% high | — → **1.92** | `docs/reference/tables/t2/e1_aggregates.json` @ `c7be283` :: `soft_over_hard_quantity.cluster_boot95.1` | PASS |

### F2: the indeterminate rate, bar vs tick

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `PYTHONPATH=src:. python measurements/indeterminate_rate.py` on the T2 group D slices (see `docs/reference/tables/t2/indeterminate.md`); the figure and its JSON are re-rendered with `measurements/indeterminate_rate.py --from-json docs/reference/tables/t2/indeterminate_after_band_edge_fix.json`
- **Data slice:** `rivf26/data/t2-indeterminate/{daily,book}` (FPT, HPG, HTV, 2022-10-20..11-30; not shipped)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `f2.days` |  | instrument-days (FPT, HPG, HTV) | 66 → **90** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `instrument_days` | PASS |
| `f2.bar` |  | undecided, `hard` at the daily bar | 35.8% → **32.6%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=BAR / hard].rate` | PASS |
| `f2.bar.ci_lo` |  | bar, Wilson 95% low | 32.3 → **29.7%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=BAR / hard].ci_low` | PASS |
| `f2.bar.ci_hi` |  | bar, Wilson 95% high | 39.4 → **35.7%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=BAR / hard].ci_high` | PASS |
| `f2.bar.n` |  | bar, fill evaluations | 698 → **950** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=BAR / hard].evaluations` | PASS |
| `f2.tick_opt` |  | undecided, `book_walk` tick, optimistic queue | 85.6% → **7.1%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (optimistic)].rate` | PASS |
| `f2.tick_opt.ci_lo` |  | tick optimistic, Wilson 95% low | 83.5 → **5.9%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (optimistic)].ci_low` | PASS |
| `f2.tick_opt.ci_hi` |  | tick optimistic, Wilson 95% high | 87.4 → **8.5%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (optimistic)].ci_high` | PASS |
| `f2.tick_opt.n` |  | tick optimistic, fill evaluations | 1,212 → **1,443** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (optimistic)].evaluations` | PASS |
| `f2.tick_con` |  | undecided, `book_walk` tick, conservative queue | 99.7% → **58.7%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.tick_con.n` |  | tick conservative, fill evaluations | 1,545 → **1,611** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=TICK / book-walk (conservative)].evaluations` | PASS |
| `f2.tick_opt.before_band_fix` |  | tick optimistic before the band-edge fix (`ba0d9f4`) | — → **10.1%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `ee42cb7` :: `arms.[label=TICK / book-walk (optimistic)].rate` | PASS |
| `f2.tick_con.before_band_fix` |  | tick conservative before the band-edge fix (`ba0d9f4`) | — → **60.2%** | `docs/reference/tables/t2/indeterminate_after_change2.json` @ `ee42cb7` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.tick_con.before_change2` |  | tick conservative before change 2 (`254aa1d`) | 99.7% → **78.2%** | `docs/reference/tables/t2/indeterminate_before_change2.json` @ `ee42cb7` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.bar.resolution_limit` |  | bar: share whose cause is the resolution limit | 35.8% → **32.6%** | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: `arms.[label=BAR / hard].resolution_limit_share` | PASS |
| `f2.figure.days` |  | figure data (`figures/f2_indeterminate_rate.json`) carries the same days | 66 → **90** | `figures/f2_indeterminate_rate.json` @ `6a33977` :: `instrument_days` | PASS |
| `f2.figure.bar` |  | figure data: bar | 35.8% → **32.6%** | `figures/f2_indeterminate_rate.json` @ `6a33977` :: `arms.[label=BAR / hard].rate` | PASS |
| `f2.figure.tick_opt` |  | figure data: tick optimistic | 85.6% → **7.1%** | `figures/f2_indeterminate_rate.json` @ `6a33977` :: `arms.[label=TICK / book-walk (optimistic)].rate` | PASS |
| `f2.figure.tick_con` |  | figure data: tick conservative | 99.7% → **58.7%** | `figures/f2_indeterminate_rate.json` @ `6a33977` :: `arms.[label=TICK / book-walk (conservative)].rate` | PASS |
| `f2.tick.resolution_limit` |  | tick (both queues): resolution-limit share | **0** (unchanged) | `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` @ `6a33977` :: computed from `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` `arms.[label=TICK / book-walk (optimistic)].resolution_limit_share`; `docs/reference/tables/t2/indeterminate_after_band_edge_fix.json` `arms.[label=TICK / book-walk (conservative)].resolution_limit_share` | PASS |

### F3: fill-policy axis (S1) and queue axis (S9)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest strategies/test_f3_cross_policy.py strategies/test_s9_queue_sensitivity.py` (writes `figures/f3_cross_policy_divergence.json`)
- **Data slice:** `strategies/fixtures/parquet/` (DATA-MANIFEST, checked below) and `strategies/fixtures/extract/` (no sha256 manifest; `PROVENANCE.md` only)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `f3.s1.soft.return` |  | S1 return under `soft` | −75.5% → **−76.4%** | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.soft.return_pct` | PASS |
| `f3.s1.soft.fills` |  | S1 fills under `soft` | **5** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.soft.fills` | PASS |
| `f3.s1.soft.forced` |  | S1 forced liquidations under `soft` | 2 → **3** | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.soft.forced` | PASS |
| `f3.s1.soft.undecided` |  | S1 undecided under `soft` | **0%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.soft.indeterminate_rate` | PASS |
| `f3.s1.hard.return` |  | S1 return under `hard` | **0.0%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.hard.return_pct` | PASS |
| `f3.s1.hard.undecided` |  | S1 undecided under `hard` | **50%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.hard.indeterminate_rate` | PASS |
| `f3.s1.probabilistic.undecided` |  | S1 undecided under `probabilistic` | **50%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `fill_axis.probabilistic.indeterminate_rate` | PASS |
| `f3.queue.optimistic` | `\sharesQueueOpt` | S9 maker shares, optimistic queue | **152,600** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `queue_axis.optimistic.maker_shares` | PASS |
| `f3.queue.conservative` | `\sharesQueueCons` | S9 maker shares, conservative queue | **123,700** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `queue_axis.conservative.maker_shares` | PASS |
| `f3.queue.probabilistic` |  | S9 maker shares, probabilistic queue | **137,600** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `queue_axis.probabilistic.maker_shares` | PASS |
| `f3.queue.swing` | `\pctQueueSwing` | queue swing (optimistic − conservative) / optimistic (F5) | **18.9%** (unchanged) | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: computed from `figures/f3_cross_policy_divergence.json` `queue_axis.optimistic.maker_shares`; `figures/f3_cross_policy_divergence.json` `queue_axis.conservative.maker_shares` | PASS |
| `f3.queue.conservative.undecided` |  | S9 conservative queue undecided | 16.7% → **0%** | `figures/f3_cross_policy_divergence.json` @ `da3d15f` :: `queue_axis.conservative.indeterminate_rate` | PASS |

### Derivatives margin: regime split, the IM step, margin-call incidence

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `PYTHONPATH=src:. python measurements/t2_futures_margin.py <rivf26-data>/t2-futures-margin`
- **Data slice:** `rivf26/data/t2-futures-margin/` (VN30F front month, 2021-06-01..2022-12-30; sha256 in `docs/reference/tables/t2/futures_margin.md`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `margin.entries` |  | entries in the VN30F front-month book | **381** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: regex /N = ([\d,]+) entries/ | PASS |
| `margin.pre` | `\marginPre` | mean requirement, pre-KRX IM+VM | 17,692,385đ → **17,692,385** | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| mean margin requirement \| pre-KRX/ cell 3 | PASS |
| `margin.post` | `\marginPost` | mean requirement, post-KRX scenario grid | 22,995,748đ → **22,995,748** | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| mean margin requirement \| post-KRX/ cell 3 | PASS |
| `margin.regime_split` | `\pctMarginSwing` | regime split, post-KRX grid vs pre-KRX IM+VM | **+30.0%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: computed from `docs/reference/tables/t2/futures_margin.md` row /^\| mean margin requirement \| pre-KRX/ cell 3; `docs/reference/tables/t2/futures_margin.md` row /^\| mean margin requirement \| post-KRX/ cell 3 | PASS |
| `margin.regime_split.table` |  | regime split as stated in the F1 table | **+30.0%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| \(1\) \*\*Regime split/ cell 3 | PASS |
| `margin.im_step` |  | the 13% → 17% IM step alone (F1) | (shown as +30.0%) → **+30.8%** | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| \(2\) \*\*13% → 17% IM step/ cell 3 | PASS |
| `margin.im_step.formula` |  | IM step = 17/13 − 1 (book-independent) | — → **+30.8%** | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: computed from `docs/reference/tables/t2/futures_margin.md` regex /(17,584,984)đ → 22,995,748đ/; `docs/reference/tables/t2/futures_margin.md` regex /17,584,984đ → (22,995,748)đ/ | PASS |
| `margin.call.h5` | `\pctCallFive` | margin-call incidence, hold 5 | **6.30%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| margin-call incidence \| 5 \|/ cell 3 | PASS |
| `margin.forced.h5` |  | forced-close incidence, hold 5 | **1.84%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| forced-close incidence \| 5 \|/ cell 3 | PASS |
| `margin.call.h10` |  | margin-call incidence, hold 10 | **11.55%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| margin-call incidence \| 10 \|/ cell 3 | PASS |
| `margin.forced.h10` |  | forced-close incidence, hold 10 | **8.66%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| forced-close incidence \| 10 \|/ cell 3 | PASS |
| `margin.call.h20` | `\pctCallTwenty` | margin-call incidence, hold 20 | **13.12%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| margin-call incidence \| 20 \|/ cell 3 | PASS |
| `margin.forced.h20` |  | forced-close incidence, hold 20 | **9.71%** (unchanged) | `docs/reference/tables/t2/futures_margin.md` @ `73f9f64` :: row /^\| forced-close incidence \| 20 \|/ cell 3 | PASS |

### Equity admission, band agreement, tick-grid conformity

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `measurements/equity_admission.py`, `band_conformance.py`, `grid_conformity.py` (exact invocations in `docs/reference/tables/t2/hsx_daily.md`)
- **Data slice:** `rivf26/data/t2-hsx-daily/` and `t2-hsx-daily-grid-history/` (sha256 in `docs/reference/tables/t2/hsx_daily.md`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `hsx.admission.lag0` |  | blocked entry, lag 0 (look-ahead) | 12.90% → **13.16%** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `77f5b3b` :: `stocks_lag0.rate` | PASS |
| `hsx.admission.lag0.n` |  | lag 0 attempts | 197,337 → **205,755** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `77f5b3b` :: `stocks_lag0.attempts` | PASS |
| `hsx.admission.lag1` |  | blocked entry, lag 1 (honest) | 5.84% → **6.03%** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `77f5b3b` :: `stocks_lag1.rate` | PASS |
| `hsx.admission.lag1.n` |  | lag 1 attempts | 197,521 → **205,958** | `docs/reference/tables/t2/hsx_daily/equity_admission.json` @ `77f5b3b` :: `stocks_lag1.attempts` | PASS |
| `hsx.band.agree` | `\pctBandAgree` | band agreement, HSX stock | 97.59% → **91.90%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.agreement_rate` | PASS |
| `hsx.band.ci_lo` | `\ciBandAgree` | band agreement, Wilson 95% low | 97.52 → **91.78%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.ci_low` | PASS |
| `hsx.band.ci_hi` | `\ciBandAgree` | band agreement, Wilson 95% high | 97.66 → **92.03%** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.ci_high` | PASS |
| `hsx.band.n` | `\nBandDays` | band agreement, HSX stock ticker-days | 179,784 → **182,367** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.rows` | PASS |
| `hsx.band.disagree` |  | band disagreements | 4,324 → **14,769** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.disagree` | PASS |
| `hsx.band.disagree_same_width` |  | disagreements with the band width right | — → **2** | `docs/reference/tables/t2/hsx_daily/band_conformance.json` @ `77f5b3b` :: `HSX stock.disagree_same_width` | PASS |
| `hsx.grid.history` | `\pctGridConform` | tick-grid conformity, library rule, all history | 99.999% → **99.9992%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `77f5b3b` :: `HSX stocks.library_rate` | PASS |
| `hsx.grid.history.naive` | `\pctGridNaive` | tick-grid conformity, naive flat 0.1, all history | 84.51% → **85.38%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `77f5b3b` :: `HSX stocks.naive_rate` | PASS |
| `hsx.grid.history.n` |  | closes, all history | 1,086,518 → **1,073,191** | `docs/reference/tables/t2/hsx_daily/grid_conformity_history.json` @ `77f5b3b` :: `HSX stocks.observations` | PASS |
| `hsx.grid.window` |  | tick-grid conformity, library rule, 2021–22 | (not measured) → **100.000%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `77f5b3b` :: `HSX stocks.library_rate` | PASS |
| `hsx.grid.window.naive` |  | tick-grid conformity, naive, 2021–22 | (not measured) → **72.94%** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `77f5b3b` :: `HSX stocks.naive_rate` | PASS |
| `hsx.grid.window.n` |  | closes, 2021–22 | — → **186,271** | `docs/reference/tables/t2/hsx_daily/grid_conformity_window.json` @ `77f5b3b` :: `HSX stocks.observations` | PASS |

### T8: rule versions, broker fields, maintenance effort, validator, properties, benchmark

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `PYTHONPATH=src python measurements/t8_counts.py`; `python measurements/maintenance_effort.py --markdown`; `PYTHONPATH=src:. python measurements/perf_benchmark_repeat.py --runs 10` (median of 10 runs)
- **Data slice:** none (engine source and git history)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `t8.rule_versions` | `\nRuleRows` | enforced rule versions (runtime rulebook rows) | 97 → **114** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 2 | PASS |
| `t8.rule_keys` |  | rule keys | — → **93** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 1 | PASS |
| `t8.rule_families` | `\nRuleTables` | rule families (tables) | **12** (unchanged) | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: regex /\*\*Total \((\d+) families\)\*\*/ | PASS |
| `t8.rule_high` |  | rule versions graded HIGH | — → **87** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 4 | PASS |
| `t8.rule_not_high` | `\nEnforcedBelowHigh` | rule versions graded MEDIUM, LOW or UNVERIFIED | a handful → **27** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: computed from `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 5; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 6; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 7 | PASS |
| `t8.rule_unknown` |  | rows that record an absence (UNKNOWN) | **11** (unchanged) | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total \(12 families\)\*\*/ cell 10 | PASS |
| `t8.broker_fields` |  | broker fields | **244** (unchanged) | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 1 | PASS |
| `t8.broker_published` |  | broker fields published by the firm | — → **110** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 2 | PASS |
| `t8.broker_supplied` | `\nBrokerSupplied` | broker fields supplied by us (as shipped) | — → **0** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 3 | PASS |
| `t8.broker_inferred` |  | broker fields inferred | — → **21** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 4 | PASS |
| `t8.broker_unpublished` |  | broker fields recorded as not published | — → **113** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 5 | PASS |
| `t8.encoded_total` |  | rules + broker fields encoded in the engine | 341 → **358** | `docs/reference/tables/t8_counts.md` @ `c2bb172` :: computed from `docs/reference/tables/t8_counts.md` row /^\| \*\*Total \(12 families\)\*\*/ cell 2; `docs/reference/tables/t8_counts.md` row /^\| \*\*Total\*\* \| \*\*244\*\*/ cell 1 | PASS |
| `t8.maint.im.data` | `\nMaintDataLines` | IM 13% → 17%: rule-data lines | — → **15** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| VSD initial margin 13% -> 17%/ cell 2 | PASS |
| `t8.maint.im.engine` | `\nMaintCodeLines` | IM 13% → 17%: change-specific engine lines | — → **0** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| VSD initial margin 13% -> 17%/ cell 4 | PASS |
| `t8.maint.im.dup` |  | IM 13% → 17%: undated duplicate scalars | — → **3** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| VSD initial margin 13% -> 17%/ cell 3 | PASS |
| `t8.maint.lot.data` |  | HOSE lot 10 → 100: rule-data lines | — → **13** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| HOSE round lot 10 -> 100/ cell 2 | PASS |
| `t8.maint.lot.engine` |  | HOSE lot 10 → 100: engine lines | — → **4** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| HOSE round lot 10 -> 100/ cell 4 | PASS |
| `t8.maint.krx.data` |  | KRX cutover: rule-data lines | — → **79** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| KRX trading-system cutover/ cell 2 | PASS |
| `t8.maint.krx.engine` |  | KRX cutover: engine lines | — → **20** | `docs/reference/tables/t8_maintenance_effort.md` @ `c2bb172` :: row /^\| KRX trading-system cutover/ cell 4 | PASS |
| `t8.validator.edges` |  | uncovered rule edges, all resolving to UNKNOWN | — → **12** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `rules.open_edges` | PASS: `len(OPEN_EDGES)` in `tests/market/session/test_rule_tables.py`, which pins the set. |
| `t8.properties` | `\nProperties` | Hypothesis properties | — → **14** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `properties.properties` | PASS |
| `t8.property_examples` | `\nPropertyExamples` | Hypothesis examples (sum of `max_examples`) | — → **3,850** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `properties.max_examples_total` | PASS |
| `t8.property_boundary` |  | explicit `@example` boundary cases on those properties | — → **26** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `properties.boundary_examples` | PASS |
| `t8.bench.at_per_sec` | `\nAtPerSec` | `Rulebook.at(ts)` resolutions per second (warm), median of 10 runs | — → **3,911,183** | `docs/reference/tables/t8_perf_benchmark.json` @ `c2bb172` :: `rulebook.at_per_second` | PASS |
| `t8.bench.orders_per_sec` | `\nOrdersPerSec` | daily fill evaluations per second through `ExchangeSession`, median of 10 runs | — → **13,086** | `docs/reference/tables/t8_perf_benchmark.json` @ `c2bb172` :: `daily.fill_evaluations_per_second` | PASS |
| `t8.bench.e1_wall` | `\EoneWall` | E1 wall time, full 2022 population (s), median of 10 runs | — → **7.18** | `docs/reference/tables/t8_perf_benchmark.json` @ `c2bb172` :: `e1.wall_s` | PASS |
| `t8.bench.e1_rss` |  | E1 peak RSS (MB), median of 10 runs | — → **285.6** | `docs/reference/tables/t8_perf_benchmark.json` @ `c2bb172` :: `e1.peak_rss_mb` | PASS |
| `t8.bench.commit` |  | benchmark ran on plutus-simulator | — → **b06d36c** | `docs/reference/tables/t8_perf_benchmark.json` @ `c2bb172` :: `machine.plutus_simulator_commit` | PASS |

### Test-suite counts (F4)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest tests`; `pytest scenarios`; `pytest strategies` (each on its own)
- **Data slice:** shipped fixtures

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `tests.unit.passed` | `\nUnitTests` | unit tests passed | 1,646 → **2,206** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.unit.passed` | PASS: Each suite run on its own shipped fixtures by `measurements/camera_ready_pins.py --tests`. Rerun it at freeze if any test is added. |
| `tests.unit.failed` |  | unit tests failed | — → **0** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.unit.failed` | PASS |
| `tests.unit.xfailed` |  | unit tests xfailed (strict) | — → **0** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.unit.xfailed` | PASS |
| `tests.unit.skipped` |  | unit tests skipped (corpus-gated) | — → **453** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.unit.skipped` | PASS |
| `tests.scenarios` | `\nScenarioTests` | scenario tests passed (0 skipped) | 38 → **39** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.scenarios.passed` | PASS |
| `tests.strategies.passed` | `\nStrategyTests` | strategy tests passed | 11 → **18** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.strategies.passed` | PASS |
| `tests.strategies.skipped` |  | strategy tests skipped (E1, F2 need corpus slices) | — → **2** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `tests.strategies.skipped` | PASS |

### Scenario and strategy findings quoted in the text

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** `env -u PLUTUS_DATA_ROOT pytest strategies/test_s2_*.py scenarios`
- **Data slice:** shipped fixtures

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `s2.loss` |  | S2 leveraged long: loss (100M start) | — → **−77%** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2.return_pct` | PASS |
| `s2.end_equity` |  | S2 end equity (M đ) | — → **23.3** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2.end_equity` | PASS |
| `s2.margin_calls` |  | S2 margin calls | — → **10** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2.margin_calls` | PASS |
| `s2.forced_tranches` | `\nStopSales` | S2 forced-sale tranches | three sales → **7** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2.forced_sale_orders` | PASS |
| `s2.queue_ahead` |  | S2 2022-11-07: floor queue ahead at 10:00 | — → **8,657,000** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2_queue.queue_ahead` | PASS |
| `s2.volume_after` |  | S2 2022-11-07: volume traded at the floor after 10:00 | — → **775,000** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2_queue.volume_after` | PASS |
| `s2.queue_verdict` |  | S2 2022-11-07: lock-queue verdict | — → **blocked** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `s2_queue.verdict` | PASS |
| `j18.deposit_step` |  | J18: deposit change at the 13% → 17% IM step | — → **+30.8%** | `docs/reference/tables/camera_ready_pins.json` @ `4a8bcff` :: `j18.deposit_step_pct` | PASS |

### Table II, ProtoSmartBeta (null anchor)

- **Repo:** `ProtoSmartBeta` (branch `rivf26`, HEAD `bdc741e` when generated)
- **Command:** `.venv/bin/python -m proto_smart_beta.experiments.null_anchor`
- **Data slice:** `data/market/<w>/`, `data/signal/<w>/` (DATA-MANIFESTs, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `sb.w2022.fills_naive` |  | w2022: naive fills | — → **457** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `naive.fills` | PASS |
| `sb.w2022.fills_faithful` |  | w2022: faithful fills | 2,257 (old OOS run) → **457** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `faithful.fills` | PASS |
| `sb.w2022.fn` | `\sbFillRange` | w2022: f/n fills | — → **100.0%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `comparison.fill_ratio_f_over_n` | PASS |
| `sb.w2022.hpr_naive` | `\sbHPRRange` | w2022: HPR naive | −3.17% → **−26.21%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `naive.hpr` | PASS |
| `sb.w2022.hpr_faithful` | `\sbHPRRange` | w2022: HPR faithful | −8.39% → **−27.08%** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `faithful.hpr` | PASS |
| `sb.w2022.band_lock_no_fills` |  | w2022: band-lock no-fills (of 10 candidates) | **0** (unchanged) | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `tier1.band_lock_no_fills` | PASS |
| `sb.w2023.fills_naive` |  | w2023: naive fills | — → **727** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `naive.fills` | PASS |
| `sb.w2023.fills_faithful` |  | w2023: faithful fills | 2,257 (old OOS run) → **724** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `faithful.fills` | PASS |
| `sb.w2023.fn` | `\sbFillRange` | w2023: f/n fills | — → **99.6%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `comparison.fill_ratio_f_over_n` | PASS |
| `sb.w2023.hpr_naive` | `\sbHPRRange` | w2023: HPR naive | −3.17% → **+19.66%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `naive.hpr` | PASS |
| `sb.w2023.hpr_faithful` | `\sbHPRRange` | w2023: HPR faithful | −8.39% → **+17.68%** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `faithful.hpr` | PASS |
| `sb.w2023.band_lock_no_fills` |  | w2023: band-lock no-fills (of 10 candidates) | **0** (unchanged) | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `tier1.band_lock_no_fills` | PASS |

### Table II, ProtoGrid

- **Repo:** `ProtoGrid` (branch `rivf26`, HEAD `becb3a2` when generated)
- **Command:** `.venv/bin/pg-anchor`
- **Data slice:** `data/{band,tick}/<w>/` (DATA-MANIFEST in `data/manifest/<w>/`, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `grid.w2022_10.fills_naive` |  | w2022_10: naive fills | 1,457 → **136** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `naive.fills` | PASS |
| `grid.w2022_10.fills_faithful` |  | w2022_10: faithful fills | 151 → **62** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `faithful.fills` | PASS |
| `grid.w2022_10.fn` | `\gridFillRange` | w2022_10: f/n fills | ≈10% → **45.6%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `gap.fill_ratio_f_over_n` | PASS |
| `grid.w2022_10.hpr_naive` | `\gridHPRRange` | w2022_10: HPR naive | −19.0% → **−2.40%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `naive.hpr` | PASS |
| `grid.w2022_10.hpr_faithful` | `\gridHPRRange` | w2022_10: HPR faithful | −34.2% → **−2.65%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `faithful.hpr` | PASS |
| `grid.w2022_10.band_limit` |  | w2022_10: BAND_LIMIT refusals | — → **828** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `tier1.band_limit_refusals` | PASS |
| `grid.w2022_10.tick_grid` |  | w2022_10: TICK_GRID refusals | 2,409 → **0** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `tier1.tick_grid_refusals` | PASS |
| `grid.w2022_10.unsettled` |  | w2022_10: UNSETTLED_HOLDING refusals (T+2) | — → **58** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `tier1.unsettled_holding_refusals` | PASS |
| `grid.w2022_10.t2_locked` |  | w2022_10: T+2-locked re-buys (INSUFFICIENT_CASH) | 248 → **28** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: `tier1.t2_locked_rebuys` | PASS |
| `grid.w2021_11.fills_naive` |  | w2021_11: naive fills | 1,457 → **124** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `naive.fills` | PASS |
| `grid.w2021_11.fills_faithful` |  | w2021_11: faithful fills | 151 → **57** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `faithful.fills` | PASS |
| `grid.w2021_11.fn` | `\gridFillRange` | w2021_11: f/n fills | ≈10% → **46.0%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `gap.fill_ratio_f_over_n` | PASS |
| `grid.w2021_11.hpr_naive` | `\gridHPRRange` | w2021_11: HPR naive | −19.0% → **+1.47%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `naive.hpr` | PASS |
| `grid.w2021_11.hpr_faithful` | `\gridHPRRange` | w2021_11: HPR faithful | −34.2% → **+1.18%** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `faithful.hpr` | PASS |
| `grid.w2021_11.band_limit` |  | w2021_11: BAND_LIMIT refusals | — → **784** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `tier1.band_limit_refusals` | PASS |
| `grid.w2021_11.tick_grid` |  | w2021_11: TICK_GRID refusals | 2,409 → **0** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `tier1.tick_grid_refusals` | PASS |
| `grid.w2021_11.unsettled` |  | w2021_11: UNSETTLED_HOLDING refusals (T+2) | — → **68** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `tier1.unsettled_holding_refusals` | PASS |
| `grid.w2021_11.t2_locked` |  | w2021_11: T+2-locked re-buys (INSUFFICIENT_CASH) | 248 → **3** | ProtoGrid: `result/grid_anchor/w2021_11.json` @ `becb3a2` :: `tier1.t2_locked_rebuys` | PASS |
| `grid.min_fn` | `\gridFill` | Grid f/n, minimum over windows (abstract) | ≈10% → **45.6%** | ProtoGrid: `result/grid_anchor/w2022_10.json` @ `becb3a2` :: computed from `result/grid_anchor/w2022_10.json` `gap.fill_ratio_f_over_n`; `result/grid_anchor/w2021_11.json` `gap.fill_ratio_f_over_n` | PASS |

### Table II, ProtoPair

- **Repo:** `ProtoPair` (branch `rivf26`, HEAD `505ca0e` when generated)
- **Command:** `.venv/bin/pp-anchor`; `.venv/bin/pp-credibility`
- **Data slice:** `data/market/<w>/` (DATA-MANIFEST, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `pair.w1.fills_naive` |  | w1: naive fills | 2,298 → **1,209** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `naive.fills` | PASS |
| `pair.w1.fills_faithful` |  | w1: faithful fills | 1,236 → **651** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `faithful.fills` | PASS |
| `pair.w1.fn` | `\pairFillRange` | w1: f/n fills | **53.8%** (unchanged) | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `gap.fills_f_over_n` | PASS |
| `pair.w1.hpr_naive` | `\pairHPRn` | w1: HPR naive | +3.5% → **+1.03%** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `gap.hpr_naive_pct` | PASS |
| `pair.w1.hpr_faithful` | `\pairHPRf` | w1: HPR faithful | −3.2% → **−2.15%** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `gap.hpr_faithful_pct` | PASS |
| `pair.w1.exits_blocked` | `\pairStuck` | w1: exits blocked by T+2 | 16 → **8** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `tier1.settlement_asymmetry.exits_blocked_by_t2` | PASS |
| `pair.w1.exits_wanted` |  | w1: exits wanted | 22 → **10** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `tier1.settlement_asymmetry.exits_wanted` | PASS |
| `pair.w1.name_days` | `\pairNameDays` | w1: name-days held open | 758 → **420** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `tier1.settlement_asymmetry.name_days_held_open` | PASS |
| `pair.w1.forgone` | `\pairSkipped` | w1: opposite-side trades forgone | 17 → **9** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `tier1.opposite_side.forgone` | PASS |
| `pair.w1.signalled` |  | w1: opposite-side trades signalled | 17 → **9** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `tier1.opposite_side.mirror_trades_signalled` | PASS |
| `pair.w1.soft_undecided_events` | `\pctPairUndecSoft` | w1: fill-time undecided events, `soft` | 2.2% → **0** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `variants.headline.fill_time_indeterminate_events` | PASS |
| `pair.w1.hard_fills` |  | w1: `hard` variant fills | 0 → **583** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `variants.hard.fills` | PASS |
| `pair.w1.hard_undecided_events` | `\pctPairUndecHard` | w1: fill-time undecided events, `hard` | 96.8% → **71** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `variants.hard.fill_time_indeterminate_events` | PASS: An event count; the old value was a rate. The result has no denominator for a `hard` rate. |
| `pair.w2.fills_naive` |  | w2: naive fills | 2,298 → **775** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `naive.fills` | PASS |
| `pair.w2.fills_faithful` |  | w2: faithful fills | 1,236 → **403** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `faithful.fills` | PASS |
| `pair.w2.fn` | `\pairFillRange` | w2: f/n fills | 53.8% → **52.0%** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `gap.fills_f_over_n` | PASS |
| `pair.w2.hpr_naive` | `\pairHPRRange` | w2: HPR naive | +3.5% → **+0.28%** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `gap.hpr_naive_pct` | PASS |
| `pair.w2.hpr_faithful` | `\pairHPRRange` | w2: HPR faithful | −3.2% → **−0.31%** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `gap.hpr_faithful_pct` | PASS |
| `pair.w2.exits_blocked` | `\pairStuck` | w2: exits blocked by T+2 | 16 → **4** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `tier1.settlement_asymmetry.exits_blocked_by_t2` | PASS |
| `pair.w2.exits_wanted` |  | w2: exits wanted | 22 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `tier1.settlement_asymmetry.exits_wanted` | PASS |
| `pair.w2.name_days` | `\pairNameDays` | w2: name-days held open | 758 → **180** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `tier1.settlement_asymmetry.name_days_held_open` | PASS |
| `pair.w2.forgone` | `\pairSkipped` | w2: opposite-side trades forgone | 17 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `tier1.opposite_side.forgone` | PASS |
| `pair.w2.signalled` |  | w2: opposite-side trades signalled | 17 → **6** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `tier1.opposite_side.mirror_trades_signalled` | PASS |
| `pair.w2.soft_undecided_events` | `\pctPairUndecSoft` | w2: fill-time undecided events, `soft` | 2.2% → **0** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `variants.headline.fill_time_indeterminate_events` | PASS |
| `pair.w2.hard_fills` |  | w2: `hard` variant fills | 0 → **377** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `variants.hard.fills` | PASS |
| `pair.w2.hard_undecided_events` | `\pctPairUndecHard` | w2: fill-time undecided events, `hard` | 96.8% → **27** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `variants.hard.fill_time_indeterminate_events` | PASS: An event count; the old value was a rate. The result has no denominator for a `hard` rate. |
| `pair.w1.adf_p` |  | w1 basis ADF p-value | — → **0.0000434** | ProtoPair: `result/credibility/w1.json` @ `0c8b77b` :: `adf_pvalue` | PASS |
| `pair.w2.adf_p` |  | w2 basis ADF p-value (does not reject a unit root) | — → **0.537** | ProtoPair: `result/credibility/w2.json` @ `0c8b77b` :: `adf_pvalue` | PASS |

### Table II, ProtoMarketMaker: anchor (faithful arm flat each session)

- **Repo:** `ProtoMarketMaker` (branch `rivf26`, HEAD `3919718` when generated)
- **Command:** `.venv/bin/python -m proto_market_maker.experiments.mm_anchor <window>`
- **Data slice:** `data/{band,l2,market}/<window>/` (`data/<window>-MANIFEST.md`, checked under `slice.*`)

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `mm.krx2025.fills_naive` |  | krx2025, all 40 sessions: naive fills | 910 → **693** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `naive.fills` | PASS |
| `mm.krx2025.hpr_naive` |  | krx2025, 40 sessions: HPR naive | 56.75% → **+29.57%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `naive.hpr` | PASS |
| `mm.krx2025.fills_naive_pre` |  | krx2025, 20 pre-cutover sessions: naive fills | — → **228** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `naive_pre_cutover_only.fills` | PASS |
| `mm.krx2025.hpr_naive_pre` |  | krx2025, pre-cutover: HPR naive | — → **−5.22%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `naive_pre_cutover_only.hpr` | PASS |
| `mm.krx2025.fills_faithful` | `\mmFillsF` | krx2025, 40 sessions: faithful fills, conservative | 402 (submission); 116 (before the rerun) → **366** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.fills` | PASS |
| `mm.krx2025.fills_opt` | `\mmFillsOpt` | krx2025, 40 sessions: faithful fills, optimistic | 160 (before the rerun) → **444** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful_by_queue.optimistic.fills` | PASS |
| `mm.krx2025.hpr_faithful` |  | krx2025, 40 sessions: HPR faithful, conservative | 31.62% (submission); −6.03% (before the rerun) → **−0.73%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.hpr` | PASS |
| `mm.krx2025.fn` | `\mmFillRange` | krx2025: f/n, all 40 sessions | 44% (submission); 16.7% (before the rerun) → **52.8%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `fills_ratio_f_over_n` | PASS |
| `mm.krx2025.fills_faithful_pre` |  | krx2025, 20 pre-cutover sessions: faithful fills, conservative | **116** (unchanged) | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.krx.pre.fills` | PASS |
| `mm.krx2025.fills_faithful_post` |  | krx2025, 20 post-cutover sessions: faithful fills, conservative | 0 (refused, before the rerun) → **250** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.krx.post.fills` | PASS |
| `mm.krx2025.fn_pre` | `\mmFillRange` | krx2025: f/n, 20 pre-cutover sessions (like for like) | **50.9%** (unchanged) | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: computed from `result/mm_anchor/krx2025.json` `faithful.krx.pre.fills`; `result/mm_anchor/krx2025.json` `naive_pre_cutover_only.fills` | PASS |
| `mm.krx2025.queue_spread` | `\pctMMQueueSwing` | krx2025: queue spread (opt − cons) / opt | 27.5% (before the rerun) → **17.6%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `tier1.queue_fill_spread.conservative_vs_optimistic_pct` | PASS |
| `mm.krx2025.undecided_pre` | `\pctMMUndecPre` | krx2025: conservative undecided orders, pre-cutover | 99.94% (submission, events) → **99.76%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.krx.pre.indeterminate_order_rate` | PASS: Counts orders; the submission's 99.94% / 99.92% counted fill-evaluation events. |
| `mm.krx2025.undecided_post` | `\pctMMUndecPost` | krx2025: conservative undecided orders, post-cutover | 99.92% (submission, events); none (refused, before the rerun) → **99.21%** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `faithful.krx.post.indeterminate_order_rate` | PASS |
| `mm.krx2025.refused_post` |  | krx2025: post-cutover sessions refused (of 20) | 20 (before the rerun) → **0** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `tier1.post_cutover_refused_sessions` | PASS |
| `mm.krx2025.engine_commit` |  | krx2025 anchor ran on plutus-simulator | 31e3405 → **8d46c56** | ProtoMarketMaker: `result/mm_anchor/krx2025.json` @ `c92e2b7` :: `plutus_simulator_commit` (first 7 characters) | PASS |
| `mm.im2022.fills_naive` |  | im2022: naive fills | — → **129** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `naive.fills` | PASS |
| `mm.im2022.hpr_naive` |  | im2022: HPR naive | — → **−12.93%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `naive.hpr` | PASS |
| `mm.im2022.fills_faithful` |  | im2022: faithful fills, conservative | — → **70** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.fills` | PASS |
| `mm.im2022.fills_opt` |  | im2022: faithful fills, optimistic | — → **98** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful_by_queue.optimistic.fills` | PASS |
| `mm.im2022.hpr_faithful` |  | im2022: HPR faithful, conservative (flat each session) | — → **+2.19%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.hpr` | PASS |
| `mm.im2022.fn` | `\mmFillRange` | im2022: f/n | — → **54.3%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `fills_ratio_f_over_n` | PASS |
| `mm.im2022.queue_spread` |  | im2022: queue spread | — → **28.6%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `tier1.queue_fill_spread.conservative_vs_optimistic_pct` | PASS |
| `mm.im2022.undecided_pre` |  | im2022: conservative undecided orders, before 2022-12-15 | — → **99.87%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.im_step.pre.indeterminate_order_rate` | PASS |
| `mm.im2022.undecided_post` |  | im2022: conservative undecided orders, from 2022-12-15 | — → **99.99%** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.im_step.post.indeterminate_order_rate` | PASS |
| `mm.deposit` | `\mmDeposit` | MM deposit (đ) | — → **500,000,000** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.deposit_dong` | PASS |
| `mm.contracts_pre` | `\mmContractsPre` | dated-IM capacity on 2022-12-14 (13%) | 37 → **36** | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.capacity.[date=2022-12-14].contracts` | PASS |
| `mm.contracts_post` | `\mmContractsPost` | dated-IM capacity on 2022-12-15 (17%) | **28** (unchanged) | ProtoMarketMaker: `result/mm_anchor/im2022.json` @ `c92e2b7` :: `faithful.capacity.[date=2022-12-15].contracts` | PASS |

### ProtoMarketMaker attribution ladder (algorithm A fixed)

- **Repo:** `ProtoMarketMaker` (branch `rivf26`, HEAD `3919718` when generated)
- **Command:** `.venv/bin/python -m proto_market_maker.experiments.mm_faithful_a <window> --queue <q>`, then `.venv/bin/python -m proto_market_maker.experiments.mm_ladder <window>`
- **Data slice:** as the MM anchor

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `ladder.im2022.n0.hpr` |  | im2022: N0 HPR | — → **−12.93%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N0 \|/ cell 5 | PASS |
| `ladder.im2022.n0.fills` |  | im2022: N0 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N0 \|/ cell 2 | PASS |
| `ladder.im2022.n1.hpr` |  | im2022: N1 HPR | — → **−15.90%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N1 \|/ cell 5 | PASS |
| `ladder.im2022.n1.fills` |  | im2022: N1 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N1 \|/ cell 2 | PASS |
| `ladder.im2022.n2.hpr` |  | im2022: N2 HPR | — → **−15.90%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N2 \|/ cell 5 | PASS |
| `ladder.im2022.n2.fills` |  | im2022: N2 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N2 \|/ cell 2 | PASS |
| `ladder.im2022.n3.hpr` |  | im2022: N3 HPR | — → **−16.42%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N3 \|/ cell 5 | PASS |
| `ladder.im2022.n3.fills` |  | im2022: N3 fills | — → **129** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| N3 \|/ cell 2 | PASS |
| `ladder.im2022.f-opt.hpr` |  | im2022: F-opt HPR | — → **−2.52%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| F\-opt \|/ cell 5 | PASS |
| `ladder.im2022.f-opt.fills` |  | im2022: F-opt fills | — → **198** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| F\-opt \|/ cell 2 | PASS |
| `ladder.im2022.f-con.hpr` |  | im2022: F-con HPR | — → **−11.47%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| F\-con \|/ cell 5 | PASS |
| `ladder.im2022.f-con.fills` |  | im2022: F-con fills | — → **116** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| F\-con \|/ cell 2 | PASS |
| `ladder.krx2025.n0.hpr` |  | krx2025, all 40 sessions: N0 HPR | — → **+29.57%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N0].hpr` | PASS |
| `ladder.krx2025.n0.fills` |  | krx2025, all 40 sessions: N0 fills | — → **693** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.n1.hpr` |  | krx2025, all 40 sessions: N1 HPR | — → **−41.99%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N1].hpr` | PASS |
| `ladder.krx2025.n1.fills` |  | krx2025, all 40 sessions: N1 fills | — → **693** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N1].fills` | PASS |
| `ladder.krx2025.n2.hpr` |  | krx2025, all 40 sessions: N2 HPR | — → **−41.99%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N2].hpr` | PASS |
| `ladder.krx2025.n2.fills` |  | krx2025, all 40 sessions: N2 fills | — → **693** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N2].fills` | PASS |
| `ladder.krx2025.n3.hpr` |  | krx2025, all 40 sessions: N3 HPR | — → **−44.77%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N3].hpr` | PASS |
| `ladder.krx2025.n3.fills` |  | krx2025, all 40 sessions: N3 fills | — → **693** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=N3].fills` | PASS |
| `ladder.krx2025.f-opt.hpr` |  | krx2025, all 40 sessions: F-opt HPR | — → **−12.02%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-opt].hpr` | PASS |
| `ladder.krx2025.f-opt.fills` |  | krx2025, all 40 sessions: F-opt fills | — → **575** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-opt].fills` | PASS |
| `ladder.krx2025.f-con.hpr` |  | krx2025, all 40 sessions: F-con HPR | — → **−42.96%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].hpr` | PASS |
| `ladder.krx2025.f-con.fills` |  | krx2025, all 40 sessions: F-con fills | — → **358** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].fills` | PASS |
| `ladder.krx2025.pre.n0.hpr` |  | krx2025, 20 pre-cutover sessions: N0 HPR | — → **−5.22%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N0].hpr` | PASS |
| `ladder.krx2025.pre.n0.fills` |  | krx2025, 20 pre-cutover sessions: N0 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.pre.n1.hpr` |  | krx2025, 20 pre-cutover sessions: N1 HPR | — → **−14.09%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N1].hpr` | PASS |
| `ladder.krx2025.pre.n1.fills` |  | krx2025, 20 pre-cutover sessions: N1 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N1].fills` | PASS |
| `ladder.krx2025.pre.n2.hpr` |  | krx2025, 20 pre-cutover sessions: N2 HPR | — → **−14.09%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N2].hpr` | PASS |
| `ladder.krx2025.pre.n2.fills` |  | krx2025, 20 pre-cutover sessions: N2 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N2].fills` | PASS |
| `ladder.krx2025.pre.n3.hpr` |  | krx2025, 20 pre-cutover sessions: N3 HPR | — → **−15.02%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N3].hpr` | PASS |
| `ladder.krx2025.pre.n3.fills` |  | krx2025, 20 pre-cutover sessions: N3 fills | — → **228** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=N3].fills` | PASS |
| `ladder.krx2025.pre.f-opt.hpr` |  | krx2025, 20 pre-cutover sessions: F-opt HPR | — → **−7.58%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=F-opt].hpr` | PASS |
| `ladder.krx2025.pre.f-opt.fills` |  | krx2025, 20 pre-cutover sessions: F-opt fills | — → **261** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=F-opt].fills` | PASS |
| `ladder.krx2025.pre.f-con.hpr` |  | krx2025, 20 pre-cutover sessions: F-con HPR | — → **−25.55%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=F-con].hpr` | PASS |
| `ladder.krx2025.pre.f-con.fills` |  | krx2025, 20 pre-cutover sessions: F-con fills | — → **153** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=F-con].fills` | PASS |
| `ladder.krx2025.post.n0.hpr` |  | krx2025, 20 post-cutover sessions: N0 HPR | — (refused before the rerun) → **+36.70%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N0].hpr` | PASS |
| `ladder.krx2025.post.n0.fills` |  | krx2025, 20 post-cutover sessions: N0 fills | — → **465** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.post.n1.hpr` |  | krx2025, 20 post-cutover sessions: N1 HPR | — (refused before the rerun) → **−32.47%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N1].hpr` | PASS |
| `ladder.krx2025.post.n1.fills` |  | krx2025, 20 post-cutover sessions: N1 fills | — → **465** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N1].fills` | PASS |
| `ladder.krx2025.post.n2.hpr` |  | krx2025, 20 post-cutover sessions: N2 HPR | — (refused before the rerun) → **−32.47%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N2].hpr` | PASS |
| `ladder.krx2025.post.n2.fills` |  | krx2025, 20 post-cutover sessions: N2 fills | — → **465** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N2].fills` | PASS |
| `ladder.krx2025.post.n3.hpr` |  | krx2025, 20 post-cutover sessions: N3 HPR | — (refused before the rerun) → **−35.01%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N3].hpr` | PASS |
| `ladder.krx2025.post.n3.fills` |  | krx2025, 20 post-cutover sessions: N3 fills | — → **465** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=N3].fills` | PASS |
| `ladder.krx2025.post.f-opt.hpr` |  | krx2025, 20 post-cutover sessions: F-opt HPR | — (refused before the rerun) → **−4.81%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=F-opt].hpr` | PASS |
| `ladder.krx2025.post.f-opt.fills` |  | krx2025, 20 post-cutover sessions: F-opt fills | — → **314** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=F-opt].fills` | PASS |
| `ladder.krx2025.post.f-con.hpr` |  | krx2025, 20 post-cutover sessions: F-con HPR | — (refused before the rerun) → **−23.39%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=F-con].hpr` | PASS |
| `ladder.krx2025.post.f-con.fills` |  | krx2025, 20 post-cutover sessions: F-con fills | — → **205** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.post_cutover.rungs.[rung=F-con].fills` | PASS |
| `ladder.im2022.f-opt.fn` |  | im2022: F-opt fills / N0 fills | — → **153.5%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: computed from `result/mm_ladder/im2022.md` row /^\| F-opt \|/ cell 2; `result/mm_ladder/im2022.md` row /^\| N0 \|/ cell 2 | PASS: Above 100%: §6 criterion 1 (faithful fills < naive) fails for this arm. |
| `ladder.im2022.f-con.fn` |  | im2022: F-con fills / N0 fills | — → **89.9%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: computed from `result/mm_ladder/im2022.md` row /^\| F-con \|/ cell 2; `result/mm_ladder/im2022.md` row /^\| N0 \|/ cell 2 | PASS |
| `ladder.krx2025.f-opt.fn` |  | krx2025, all 40 sessions: F-opt fills / N0 fills | — → **83.0%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `rungs.[rung=F-opt].fills`; `result/mm_ladder/krx2025.json` `rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.f-con.fn` |  | krx2025, all 40 sessions: F-con fills / N0 fills | — → **51.7%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `rungs.[rung=F-con].fills`; `result/mm_ladder/krx2025.json` `rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.pre.f-opt.fn` |  | krx2025, 20 pre-cutover sessions: F-opt fills / N0 fills | — → **114.5%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `views.pre_cutover.rungs.[rung=F-opt].fills`; `result/mm_ladder/krx2025.json` `views.pre_cutover.rungs.[rung=N0].fills` | PASS: Above 100%: §6 criterion 1 (faithful fills < naive) fails for this arm. |
| `ladder.krx2025.pre.f-con.fn` |  | krx2025, 20 pre-cutover sessions: F-con fills / N0 fills | — → **67.1%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `views.pre_cutover.rungs.[rung=F-con].fills`; `result/mm_ladder/krx2025.json` `views.pre_cutover.rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.post.f-opt.fn` |  | krx2025, 20 post-cutover sessions: F-opt fills / N0 fills | — → **67.5%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `views.post_cutover.rungs.[rung=F-opt].fills`; `result/mm_ladder/krx2025.json` `views.post_cutover.rungs.[rung=N0].fills` | PASS |
| `ladder.krx2025.post.f-con.fn` |  | krx2025, 20 post-cutover sessions: F-con fills / N0 fills | — → **44.1%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: computed from `result/mm_ladder/krx2025.json` `views.post_cutover.rungs.[rung=F-con].fills`; `result/mm_ladder/krx2025.json` `views.post_cutover.rungs.[rung=N0].fills` | PASS |
| `ladder.im2022.json_agrees` |  | im2022: ladder JSON HPRs equal the markdown's first table | — → **6** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `c92e2b7` :: `result/mm_ladder/im2022.json` `rungs[].hpr` vs `result/mm_ladder/im2022.md` | PASS |
| `ladder.im2022.f-opt.source_sha` |  | im2022: F-opt faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `c92e2b7` :: sha256 of the file at `faithful_sources.F-opt.path` vs `faithful_sources.F-opt.sha256` | PASS |
| `ladder.im2022.f-con.source_sha` |  | im2022: F-con faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/im2022.json` @ `c92e2b7` :: sha256 of the file at `faithful_sources.F-con.path` vs `faithful_sources.F-con.sha256` | PASS |
| `ladder.krx2025.json_agrees` |  | krx2025: ladder JSON HPRs equal the markdown's first table | — → **6** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `result/mm_ladder/krx2025.json` `rungs[].hpr` vs `result/mm_ladder/krx2025.md` | PASS |
| `ladder.krx2025.f-opt.source_sha` |  | krx2025: F-opt faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: sha256 of the file at `faithful_sources.F-opt.path` vs `faithful_sources.F-opt.sha256` | PASS |
| `ladder.krx2025.f-con.source_sha` |  | krx2025: F-con faithful-A result file matches the sha256 the ladder records | — → **1** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: sha256 of the file at `faithful_sources.F-con.path` vs `faithful_sources.F-con.sha256` | PASS |
| `ladder.im2022.f-con.undecided` |  | im2022: F-con undecided orders | — → **99.88%** | ProtoMarketMaker: `result/mm_ladder/im2022.md` @ `c92e2b7` :: row /^\| F-con \|/ cell 7 | PASS |
| `ladder.krx2025.f-con.undecided` |  | krx2025, all 40 sessions: F-con undecided orders | 99.63% (pre-cutover, before the rerun) → **99.54%** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].undecided_order_rate` | PASS |
| `ladder.krx2025.pre.f-con.undecided` |  | krx2025, pre-cutover: F-con undecided orders | **99.63%** (unchanged) | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `views.pre_cutover.rungs.[rung=F-con].undecided_order_rate` | PASS |
| `ladder.krx2025.f-con.margin_calls` |  | krx2025, all 40 sessions: F-con margin calls | — → **31** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].margin_calls` | PASS |
| `ladder.krx2025.f-con.forced_executed` |  | krx2025: F-con forced liquidations executed | — → **3** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].forced_liquidations_executed` | PASS |
| `ladder.krx2025.f-opt.ccp_nights` |  | krx2025: F-opt post-KRX CCP nights with a position | — → **20** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-opt].ccp_nights` | PASS |
| `ladder.krx2025.f-opt.ccp_indeterminate` |  | krx2025: F-opt CCP nights indeterminate | — → **0** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-opt].ccp_indeterminate_nights` | PASS |
| `ladder.krx2025.f-opt.ccp_calendar_unknown` |  | krx2025: F-opt calendar-spread charge UNKNOWN | — → **0** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-opt].ccp_calendar_spread_unknown` | PASS |
| `ladder.krx2025.f-con.ccp_nights` |  | krx2025: F-con post-KRX CCP nights with a position | — → **19** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].ccp_nights` | PASS |
| `ladder.krx2025.f-con.ccp_indeterminate` |  | krx2025: F-con CCP nights indeterminate | — → **0** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].ccp_indeterminate_nights` | PASS |
| `ladder.krx2025.f-con.ccp_calendar_unknown` |  | krx2025: F-con calendar-spread charge UNKNOWN | — → **0** | ProtoMarketMaker: `result/mm_ladder/krx2025.json` @ `c92e2b7` :: `rungs.[rung=F-con].ccp_calendar_spread_unknown` | PASS |
| `ladder.markout.im2022.n3.5m` |  | im2022, all 40 sessions: mean 5-min markout per fill, N3 (index pts; + good for the maker) | −2.24 naive / −0.78 faithful (first 6 im2022 sessions, prose) → **−0.71** | ProtoMarketMaker: `result/mm_markout/im2022_markout.json` @ `c92e2b7` :: `arms.N3.markout_mean_points.5m` | PASS |
| `ladder.markout.im2022.f-opt.5m` |  | im2022, all 40 sessions: mean 5-min markout per fill, F-opt (index pts; + good for the maker) | — → **+0.41** | ProtoMarketMaker: `result/mm_markout/im2022_markout.json` @ `c92e2b7` :: `arms.F-opt.markout_mean_points.5m` | PASS |
| `ladder.markout.im2022.f-con.5m` |  | im2022, all 40 sessions: mean 5-min markout per fill, F-con (index pts; + good for the maker) | — → **−0.57** | ProtoMarketMaker: `result/mm_markout/im2022_markout.json` @ `c92e2b7` :: `arms.F-con.markout_mean_points.5m` | PASS |
| `ladder.markout.krx2025.n3.5m` |  | krx2025, all 40 sessions: mean 5-min markout per fill, N3 (index pts; + good for the maker) | — → **−2.22** | ProtoMarketMaker: `result/mm_markout/krx2025_markout.json` @ `c92e2b7` :: `arms.N3.markout_mean_points.5m` | PASS |
| `ladder.markout.krx2025.f-opt.5m` |  | krx2025, all 40 sessions: mean 5-min markout per fill, F-opt (index pts; + good for the maker) | — → **−0.68** | ProtoMarketMaker: `result/mm_markout/krx2025_markout.json` @ `c92e2b7` :: `arms.F-opt.markout_mean_points.5m` | PASS |
| `ladder.markout.krx2025.f-con.5m` |  | krx2025, all 40 sessions: mean 5-min markout per fill, F-con (index pts; + good for the maker) | — → **−0.31** | ProtoMarketMaker: `result/mm_markout/krx2025_markout.json` @ `c92e2b7` :: `arms.F-con.markout_mean_points.5m` | PASS |
| `ladder.markout.im2022.f-opt.1m` |  | im2022: mean 1-min markout per fill, F-opt (record for the WITHDRAWN 'no ghost fills' claim) | — → **+0.21** | ProtoMarketMaker: `result/mm_markout/im2022_markout.json` @ `c92e2b7` :: `arms.F-opt.markout_mean_points.1m` | PASS: Withdrawn claim: kept as the record only; the paper does not state 'no ghost fills'. |
| `ladder.markout.krx2025.f-opt.1m` |  | krx2025: mean 1-min markout per fill, F-opt (record for the WITHDRAWN 'no ghost fills' claim) | — → **+0.06** | ProtoMarketMaker: `result/mm_markout/krx2025_markout.json` @ `c92e2b7` :: `arms.F-opt.markout_mean_points.1m` | PASS: Withdrawn claim: kept as the record only; the paper does not state 'no ghost fills'. |

### Data-slice integrity (sha256 of every committed slice file vs its manifest)

- **Repo:** `plutus-simulator` (branch `rivf26`, HEAD `b06d36c` when generated)
- **Command:** this checker
- **Data slice:** each manifest named in the row

| ID | Macro | Number | Old → New | Source file @ commit :: field | Check |
|---|---|---|---|---|---|
| `slice.sim.scenarios.fixtures.daily` |  | `scenarios/fixtures/daily/DATA-MANIFEST.md`: files matching sha256 | — → **9** | `scenarios/fixtures/daily/DATA-MANIFEST.md` @ `74fc71a` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.scenarios.fixtures.book` |  | `scenarios/fixtures/book/DATA-MANIFEST.md`: files matching sha256 | — → **12** | `scenarios/fixtures/book/DATA-MANIFEST.md` @ `74fc71a` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.parquet` |  | `strategies/fixtures/parquet/DATA-MANIFEST.md`: files matching sha256 | — → **9** | `strategies/fixtures/parquet/DATA-MANIFEST.md` @ `74fc71a` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.s2_lock.daily` |  | `strategies/fixtures/s2_lock/daily/DATA-MANIFEST.md`: files matching sha256 | — → **4** | `strategies/fixtures/s2_lock/daily/DATA-MANIFEST.md` @ `e8d819c` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.strategies.fixtures.s2_lock.book` |  | `strategies/fixtures/s2_lock/book/DATA-MANIFEST.md`: files matching sha256 | — → **4** | `strategies/fixtures/s2_lock/book/DATA-MANIFEST.md` @ `e8d819c` :: files whose sha256 matches the manifest | PASS |
| `slice.sim.tests.market.session.fixtures.book_walk` |  | `tests/market/session/fixtures/book_walk/DATA-MANIFEST.md`: files matching sha256 | — → **8** | `tests/market/session/fixtures/book_walk/DATA-MANIFEST.md` @ `6b4b9db` :: files whose sha256 matches the manifest | PASS |
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
| `slice.marketmaker.im2022.manifest` |  | ProtoMarketMaker `data/im2022-MANIFEST.md`: files matching sha256 | — → **12** | ProtoMarketMaker: `data/im2022-MANIFEST.md` @ `f507d2d` :: files whose sha256 matches the manifest | PASS |
| `slice.marketmaker.krx2025.manifest` |  | ProtoMarketMaker `data/krx2025-MANIFEST.md`: files matching sha256 | — → **12** | ProtoMarketMaker: `data/krx2025-MANIFEST.md` @ `b636a30` :: files whose sha256 matches the manifest | PASS |
| `slice.smartbeta.result.w2022` |  | SB `result/null_anchor/w2022.json` recorded slice sha256 match the committed files | — → **11** | ProtoSmartBeta: `result/null_anchor/w2022.json` @ `bdc741e` :: `provenance.slices` sha256 vs the committed files | PASS |
| `slice.smartbeta.result.w2023` |  | SB `result/null_anchor/w2023.json` recorded slice sha256 match the committed files | — → **11** | ProtoSmartBeta: `result/null_anchor/w2023.json` @ `bdc741e` :: `provenance.slices` sha256 vs the committed files | PASS |
| `slice.pair.result.w1` |  | Pair `result/pair_anchor/w1.json` recorded slice sha256 match the committed files | — → **11** | ProtoPair: `result/pair_anchor/w1.json` @ `505ca0e` :: `slice` sha256 vs the committed files | PASS |
| `slice.pair.result.w2` |  | Pair `result/pair_anchor/w2.json` recorded slice sha256 match the committed files | — → **11** | ProtoPair: `result/pair_anchor/w2.json` @ `505ca0e` :: `slice` sha256 vs the committed files | PASS |

<!-- END GENERATED -->
