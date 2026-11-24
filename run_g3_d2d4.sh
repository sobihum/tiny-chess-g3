#!/bin/bash
# G3 — basin dobrak pion d4 (d2d4). Prefix 1 langkah, cari mate 17 plies
# (5 our-moves). Jalankan di mesin ke-5, paralel dengan run_g3.sh.
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
mkdir -p g3
python3 beam4_real.py --game 3 --width 128 --max-our-moves 5 \
  --prefix d2d4 --time-budget-min 480 --fresh 2>&1 | tee g3/beam4_g3_d2d4.out
echo "--- TAIL ---"
tail -n 20 g3/beam4_g3_d2d4.out
