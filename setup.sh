#!/bin/bash
# OFFLINE setup for the tiny-chess-01 beam search on a Kaggle notebook (CPU).
# Everything needed is vendored in vendor/ — no internet required in the notebook.
# Run once, from the directory where this zip was extracted.
set -e
export CHESS_BASE="$(pwd)/chess"
echo "CHESS_BASE=$CHESS_BASE"

# 1. python-chess (vendored, pure Python, same 1.11.2 as local)
export PYTHONPATH="$(pwd)/vendor:$PYTHONPATH"
python3 -c "import chess; print('python-chess OK', chess.__version__)"

# 2. Node.js 20 (vendored tarball)
if ! command -v node >/dev/null 2>&1; then
  tar -xf vendor/node.tar.xz -C /tmp
  export PATH="/tmp/node-v20.18.1-linux-x64/bin:$PATH"
fi
node --version

# 3. Stockfish 16 (Ubuntu .deb, vendored) — SF17 was used locally, but SF16 is
# equivalent here: it only proposes candidates/scores, the oracle verifies mates.
SF_DIR="$CHESS_BASE/work/stockfish"
mkdir -p "$SF_DIR"
if [ ! -x "$SF_DIR/stockfish-bin" ]; then
  dpkg-deb -x vendor/stockfish_16-1build1_amd64.deb /tmp/sfdeb
  cp /tmp/sfdeb/usr/games/stockfish "$SF_DIR/stockfish-bin"
  chmod +x "$SF_DIR/stockfish-bin"
fi
printf 'uci\nquit\n' | "$SF_DIR/stockfish-bin" | head -2

# 4. dirs + env file for later cells/sessions
mkdir -p "$CHESS_BASE/cache" "$CHESS_BASE/work/beam4/g1"
cat > "$(pwd)/env.sh" <<EOF
export CHESS_BASE="$CHESS_BASE"
export PATH="/tmp/node-v20.18.1-linux-x64/bin:\$PATH"
export PYTHONPATH="$(pwd)/vendor:\$PYTHONPATH"
EOF
echo "SETUP DONE. Then run: bash run_g1.sh"
