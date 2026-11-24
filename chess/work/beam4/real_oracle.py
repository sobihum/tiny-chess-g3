#!/usr/bin/env python3
"""Real oracle adapter for tiny-chess-01.

Implements the OFFICIAL oracle contract (work/oracle/oracle.mjs, playGame),
verified against the source and the shared cache. The workbench adapter
(oracle_adapter.py) is WRONG for this oracle: it sends {"id", "history"}
and expects {"move"}; the real oracle answers that with error unknown_game.

Official contract:
  request  (one JSON object per line on stdin):
      {"game": 1..6, "our_moves": ["uci", ...]}   # our moves ONLY, from
      # the position after the fixed 8-ply opening (+ house first move
      # when we are black). our_moves=[] probes the root position.
  response (one JSON object per line on stdout):
      {"game", "opponent", "colour", "opening", "full_moves",
       "house_moves", "our_moves", "fen", "legal_moves",
       "status": "your_move" | "over", "result", "reason",
       "outcome": "win" | "draw" | "loss" | null,
       "total_plies", "error"?}

  A win is ONLY outcome=="win" and reason=="checkmate" in a response.
  The board for further search comes from response["fen"] (authoritative),
  never from replaying a raw history.

Cache: same JSONL format as the rest of the project
(cache/oracle.jsonl, key "G|move1 move2 ...", entries
{"key", "request", "output"}), append-only, shared with beam3/beam3b.
"""
import json
import os
import subprocess

BASE = os.path.expanduser(os.environ.get("CHESS_BASE", "~/workspace/tiny-chess-01"))
ORACLE = os.path.join(BASE, "work/oracle/oracle.mjs")
CACHE_PATH = os.path.join(BASE, "cache/oracle.jsonl")


def cache_key(game, moves):
    return f"{game}|{' '.join(moves)}"


def load_cache(path=CACHE_PATH):
    """Load the shared JSONL cache into {key: output}."""
    cache = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    cache[e["key"]] = e["output"]
                except Exception:
                    continue
    return cache


class RealOracle:
    """One long-lived official oracle process + shared JSONL cache.

    Only ONE RealOracle (i.e. one oracle process) may exist at a time:
    the G5 beam3b worker owns the oracle until it finishes. Do not
    construct this while beam3b.py is still running.
    """

    def __init__(self, game, cache_path=CACHE_PATH):
        self.game = game
        self.cache_path = cache_path
        self.cache = load_cache(cache_path)
        self.hits = 0
        self.queries = 0
        self.cache_f = open(cache_path, "a")
        self.proc = subprocess.Popen(
            ["node", ORACLE], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, bufsize=1)

    def __call__(self, moves):
        """Return the official oracle response dict for our_moves (list)."""
        moves = list(moves)
        key = cache_key(self.game, moves)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        req = {"game": self.game, "our_moves": moves}
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("oracle process died")
        out = json.loads(line)
        self.queries += 1
        self.cache[key] = out
        self.cache_f.write(
            json.dumps({"key": key, "request": req, "output": out}) + "\n")
        self.cache_f.flush()
        return out

    def is_mate(self, out):
        return out.get("outcome") == "win" and out.get("reason") == "checkmate"

    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.cache_f.close()
        except Exception:
            pass
