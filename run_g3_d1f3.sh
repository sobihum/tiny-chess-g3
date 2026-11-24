#!/bin/bash
# G3 — basin menteri ke f3 (d1f3, menyerang f7). Prefix 1 langkah, cari mate
# 17 plies (5 our-moves). Jalankan di mesin ke-4, paralel dengan run_g3.sh.
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
mkdir -p g3
python3 beam4_real.py --game 3 --width 128 --max-our-moves 5 \
  --prefix d1f3 --time-budget-min 480 --fresh 2>&1 | tee g3/beam4_g3_d1f3.out
echo "--- TAIL ---"
tail -n 20 g3/beam4_g3_d1f3.out
