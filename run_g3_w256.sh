#!/bin/bash
# G3 — versi LEBAR (w256) dari run_g3.sh. Sama: ban f3h4, cari mate 17 plies
# (5 our-moves) dari semua langkah pertama lain. Jalankan di mesin ke-2,
# paralel dengan run_g3.sh (w128). Yang menemukan mate duluan yang menang.
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
mkdir -p g3
python3 beam4_real.py --game 3 --width 256 --max-our-moves 5 \
  --bans f3h4 --time-budget-min 480 --fresh 2>&1 | tee g3/beam4_g3_alt_w256.out
echo "--- TAIL ---"
tail -n 20 g3/beam4_g3_alt_w256.out
