# Tiny Chess G3 — status 24 Nov 2026 11:28 WIB

Book: 143 plies, spare 1057, rank #12.
G3 (19): f3h4 h4f5 d1f3 f5g7 f3f7 g7f5 — target mate 17 -> total 141, spare 1059.
Deadline entry: 25 Nov 00:00 WIB, freeze pencarian baru: 22:00 WIB 24 Nov.

5 mesin sedang jalan paralel (w128 ban f3h4, w256 ban f3h4, prefix f3g5, prefix f3g5,d1f3, prefix d2d4).
Catatan penting: prefix d1f3 saja ILEGAL — kuda sudah di f3 di opening, oracle balikin illegal_move.
Perbaikan yang dipakai: prefix f3g5,d1f3 (terverifikasi legal, 12 plies).
verify_line_real.py tidak ada di paket — verifikasi pakai RealOracle langsung.
