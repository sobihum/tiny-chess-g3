# Tiny-chess-01 beam search on Kaggle (CPU notebook, OFFLINE)

## What this is
A self-contained copy of our beam-search code (same code that found the 145-ply book:
Mate Book + Trap-Beam, oracle = the house engine itself, Stockfish for candidates).
It runs **in parallel** with the local search — different game, no overlap.

## Why offline
Kaggle requires phone verification to turn on notebook internet, and this account
is not phone-verified. So everything is vendored in `vendor/` — no downloads at all:
- `vendor/node.tar.xz` — Node.js 20 (the oracle runs in Node)
- `vendor/stockfish_16-1build1_amd64.deb` — Stockfish 16 (Ubuntu package; SF17 was
  used locally, but SF16 is equivalent here since it only proposes candidates and
  scores — the oracle verifies every mate)
- `vendor/chess/` — python-chess 1.11.2, pure Python (same version as local)

## Contents
- `chess/work/beam4/beam4_real.py`, `real_oracle.py` — beam search (patched: base dir
  comes from env `CHESS_BASE`)
- `chess/work/oracle/oracle.mjs` — the house engine as a standalone oracle (verbatim)
- `setup.sh` — offline install from `vendor/` (no internet needed)
- `run_g1.sh` — the job: G1 rebeam, prefix `d1c2,c1d2,c4d5`, width 128, max 8 our-moves
  (= 23 total plies), budget 480 min

## How to run (in the Kaggle notebook)
1. Upload this zip to the notebook, unzip in the working directory.
2. `bash setup.sh` (extracts Node + Stockfish, verifies both).
3. `bash run_g1.sh` — runs the G1 rebeam. Watch `chess/work/beam4/g1/beam4_kaggle.out`.
4. If the session dies, re-run `bash run_g1.sh` **without** `--fresh` to resume from
   `chess/work/beam4/g1/checkpoint.json` (edit the script: remove `--fresh`).

## What counts as a result
- A line `*** MATE [...] total_plies=23 ***` in the log = a cut. Report the full move list.
- `NO MATE FOUND` = G1 closed at 25 in this basin; report the run time + oracle_q.
- Never trust a Stockfish mate score (100xxx) alone — only the oracle proves a mate.

## Notes
- The 153 MB oracle cache was NOT included (too big to upload); the cache rebuilds
  fresh on Kaggle. That makes the run slower but still correct.
- Kaggle CPU notebooks give ~4 cores / 16 GB; the beam itself is single-threaded,
  the win is running this in parallel with the local machine.
- Do NOT submit anything from Kaggle. Results come back here for oracle verification
  + live validation + submit.
