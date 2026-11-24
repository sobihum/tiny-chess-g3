#!/bin/bash
# G1 rebeam on Kaggle: fix the shared prefix of the three known 25-ply G1 variants
# (d1c2 c1d2 c4d5) and search for a mate in 8 our-moves = 23 total plies.
# A mate here cuts the book total 145 -> 143 (spare 1055 -> 1057).
# Progress: work/beam4/g1/beam4.out (tail it). Checkpoint: work/beam4/g1/checkpoint.json
# (resume by re-running this script WITHOUT --fresh if the session dies).
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
python3 beam4_real.py --game 1 --width 128 --max-our-moves 8 \
  --prefix d1c2,c1d2,c4d5 --time-budget-min 480 --fresh 2>&1 | tee g1/beam4_kaggle.out
echo "--- TAIL ---"
tail -n 20 g1/beam4_kaggle.out
