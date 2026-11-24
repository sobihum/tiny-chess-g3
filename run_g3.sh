#!/bin/bash
# G3 — CARI MATE 17 PLIES (5 our-moves), dari basin ALTERNATIF.
# G3 sekarang 19 plies (6 our-moves): f3h4 h4f5 d1f3 f5g7 f3f7 g7f5.
# Basin standar (f3h4) SUDAH tertutup total: beam w256 + hunt 192 state frontier,
# semuanya tanpa mate (terverifikasi oracle). Jadi JANGAN ulangi basin itu.
# Run ini memban langkah pertama garis lama (f3h4) dan mencari mate 17 plies
# dari SEMUA langkah pertama lainnya. Ini jalur yang BELUM pernah dicoba.
# Target: mate 17 plies (5 our-moves) -> total 141, spare 1059.
# Progress: chess/work/beam4/g3/beam4.out (tail it). Checkpoint: .../g3/checkpoint.json
# (resume: jalankan lagi TANPA --fresh bila sesi mati).
set -e
source "$(dirname "$0")/env.sh"
cd "$CHESS_BASE/work/beam4"
mkdir -p g3
python3 beam4_real.py --game 3 --width 128 --max-our-moves 5 \
  --bans f3h4 --time-budget-min 480 --fresh 2>&1 | tee g3/beam4_g3_alt.out
echo "--- TAIL ---"
tail -n 20 g3/beam4_g3_alt.out
