# G3 — SERANG DI BAWAH 19 PLIES (target 17)

## Posisi sekarang (jujur)

- G3 sekarang **19 plies** (6 our-moves, Putih, italian-game):
  `f3h4 h4f5 d1f3 f5g7 f3f7 g7f5`
- Total book **143 plies / spare 1057**, rank #12 live. Satu potongan 2 plies
  di G3 (19 -> 17) = total **141, spare 1059** = rank ~#11.
- Deadline entry: **Rabu 25 Nov 00:00 WIB** (24 Nov 17:00 UTC).
  Freeze pencarian baru: **22:00 WIB** hari ini — setelah itu hanya lipat + submit.

## Yang SUDAH tertutup — jangan ulangi

Basin standar G3 (langkah pertama f3h4) **sudah tertutup total** oleh oracle:
beam w128/w256 + hunt exhaustif 192 state frontier w256, semuanya tanpa mate.
Mengulang basin f3h4 = buang waktu. Aturan skip: begitu satu pencarian habis
tanpa mate, langsung lanjut ke berikutnya.

## Yang BELUM dicoba — ini serangannya

Metode yang menembus G1 (25->23) dan G5 (25->23): **basin alternatif + ban**.
G1 ketemu karena langkah tenang e3e4 yang TIDAK masuk kandidat Stockfish —
beam buta terhadap mate seperti itu. G3 bisa menyembunyikan mate yang sama
di basin alternatif. Itu yang dicari 5 run di bawah ini.

Semua run cari **mate 17 plies (5 our-moves)**. Kalau ada mate 15 plies
(4 our-moves), run ini juga akan menemukannya.

## Pembagian mesin (paralel, 5 mesin)

| Mesin | Script | Isi |
|---|---|---|
| 1 (utama) | `run_g3.sh` | Ban f3h4, cari mate 17 dari SEMUA langkah pertama lain, w128 |
| 2 | `run_g3_w256.sh` | Sama seperti mesin 1, tapi w256 (lebih lebar) |
| 3 | `run_g3_f3g5.sh` | Basin kuda ke g5 (menyerang f7), w128 |
| 4 | `run_g3_d1f3.sh` | Basin menteri ke f3 (menyerang f7), w128 |
| 5 | `run_g3_d2d4.sh` | Basin dobrak pion d4, w128 |

Satu mesin juga cukup — jalankan `run_g3.sh` dulu (itu yang paling luas).

## Cara jalan (Linux)

```bash
# 1. Extract paket ini, masuk ke foldernya
# 2. Setup sekali (offline, semua sudah ikut di vendor/):
bash setup.sh
# 3. Jalankan run G3 (pilih sesuai mesin):
bash run_g3.sh        # mesin 1
bash run_g3_w256.sh   # mesin 2
bash run_g3_f3g5.sh   # mesin 3
bash run_g3_d1f3.sh   # mesin 4
bash run_g3_d2d4.sh   # mesin 5
```

Progress: `chess/work/beam4/g3/beam4.out` (atau file `beam4_g3_*.out`
masing-masing run). Checkpoint: `chess/work/beam4/g3/checkpoint.json` —
kalau sesi mati, jalankan lagi TANPA `--fresh` untuk resume.

## Kalau ketemu MATE — verifikasi dulu, jangan langsung percaya

1. Di log akan muncul `MATE FOUND` atau `MATE via SF PV` + garisnya.
2. Verifikasi garis itu dengan oracle (wajib — skor Stockfish >=100000
   BUKAN bukti, itu sering halusinasi):
   ```bash
   cd chess/work/beam4
   python3 verify_line_real.py --game 3 --line '["f3g5", ...]'
   ```
   Harus keluar `outcome: win`, `reason: checkmate`, `total_plies: 17`
   (atau 15). Kalau tidak, itu BUKAN mate.
3. Kirim garisnya balik ke saya (chat) — saya yang lipat ke book,
   validasi live 3x, push, dan submit. **Jangan submit dari mesin lain** —
   submit hanya dari akun tresiass96, satu jalur, supaya tidak kena
   duplicate_snapshot / diskualifikasi.

## Penilaian jujur (tanpa basa-basi)

G3 adalah game yang paling keras kepala: basin standarnya sudah diburu
habis-habisan tanpa hasil. Peluang satu run ini menemukan mate 17 memang
kecil. Tapi G1 membuktikan beam bisa buta terhadap satu langkah tenang,
dan 5 run di atas adalah jalur yang BELUM pernah dicoba untuk G3.
Dengan 5 mesin paralel + deadline 13 jam, ini tembakan terbaik yang tersisa.
Berjuang sampai titik darah penghabisan — tapi hanya oracle yang menentukan
menang atau tidak.
