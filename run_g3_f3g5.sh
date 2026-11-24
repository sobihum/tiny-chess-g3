#!/bin/bash
# G3 — basin kuda ke g5 (f3g5, menyerang f7). Prefix 1 langkah, cari mate
# 17 plies (5 our-moves). Jalankan di mesin ke-3, paralel dengan run_g3.sh.
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
mkdir -p g3
python3 beam4_real.py --game 3 --width 128 --max-our-moves 5 \
  --prefix f3g5 --time-budget-min 480 --fresh 2>&1 | tee g3/beam4_g3_f3g5.out
echo "--- TAIL ---"
tail -n 20 g3/beam4_g3_f3g5.out
