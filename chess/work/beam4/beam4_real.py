#!/usr/bin/env python3
"""beam4_real: workbench beam4 adapted to the OFFICIAL oracle contract.

What was kept from beam4.py (workbench, good prototype):
  * candidate union: Stockfish MultiPV + ALL checking moves + captures +
    promotions, ordered by a cheap move-order score with attack bonus.
  * diversity: keep distinct first-move basins so the beam does not
    collapse onto one line.
  * "a found mate is a candidate, not yet an official verified line"
    (validation happens later, live env + official scorer only).

What was FIXED / ADDED (workbench gaps, verified against oracle.mjs):
  * Oracle: RealOracle (real_oracle.py) with the official contract
    {"game": N, "our_moves": [...]} -> full response dict. The
    workbench adapter sent {"id","history"} and expected {"move"}.
  * Board state comes from response["fen"] (authoritative), and a win
    is ONLY outcome=="win" + reason=="checkmate" in that response.
    mock_oracle.py is NEVER used here.
  * Scoring: SF eval is a tiebreak, not the driver (G6 lesson: pure
    SF-material scoring prunes king-hunt mates). Score = SF eval
    + check bonus (+60) + 40 per check already in the line
    + king-attack term (attackers on the enemy king's neighbourhood,
    Q/R on an open file/rank toward the enemy king).
  * Candidates also include Q/R-attack moves (beam3 lesson).
  * Mate-rescore from depth>=1: SF @500k on top-5 states; if SF shows
    a mate, play its PV through the oracle immediately.
  * Checkpoint/resume per game (checkpoint.json + log.jsonl), like
    beam3b, so a VM restart does not lose the search.
  * First-move bans per game (book's first our-move, so the final
    lines are genuinely different from the starting book).
  * Stockfish 17 (work/stockfish/stockfish-bin), nodes-based limits,
    Threads=1. Stockfish is a guide only; the house oracle is
    authoritative.

Target: mate as short as possible per game. New user target is
total <=100 plies (spare >=1100), i.e. ~16-17 plies/game: white mate
by our 5th move (17 plies), black mate by our 4th (16 plies). The beam
returns the FIRST mate found at the shallowest depth; if none is found
by MAX_OUR_MOVES it reports the best frontier lines instead. No result
is claimed verified until the live env + official scorer agree 6/6.

Usage (ONE oracle process at a time; do NOT run while beam3b runs):
  python3 beam4_real.py --game 2 --width 64 --max-our-moves 9
"""
import argparse
import json
import os
import sys
import time

import chess
import chess.engine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from real_oracle import RealOracle  # noqa: E402

BASE = os.path.expanduser(os.environ.get("CHESS_BASE", "~/workspace/tiny-chess-01"))
WORK_ROOT = os.path.join(BASE, "work/beam4")
SF = os.path.join(BASE, "work/stockfish/stockfish-bin")

# game: colour, opening (8 plies), banned first OUR moves (book's first).
SPECS = {
    1: {"colour": chess.WHITE, "opening": ["d2d4", "d7d5", "c2c4", "c7c6", "b1c3", "g8f6", "e2e3", "e7e6"], "bans": {"d1c2"}},
    2: {"colour": chess.BLACK, "opening": ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6"], "bans": {"b8c6"}},
    3: {"colour": chess.WHITE, "opening": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "c2c3", "g8f6"], "bans": {"d1e2"}},
    4: {"colour": chess.BLACK, "opening": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "g8f6", "e1g1", "f6e4"], "bans": {"e4d6"}},
    5: {"colour": chess.WHITE, "opening": ["d2d4", "d7d5", "c2c4", "c7c6", "g1f3", "g8f6", "b1c3", "d5c4"], "bans": {"e2e4", "g2g3", "e2e3", "a2a4", "c1f4"}},
    6: {"colour": chess.BLACK, "opening": ["e2e4", "e7e5", "g1f3", "d7d6", "d2d4", "g8f6", "b1c3", "b8d7"], "bans": {"h7h5", "g7g6"}},
}

SCREEN_NODES = 100_000   # SF MultiPV screening
RESCORE_NODES = 50_000   # SF eval of child position after house reply
DEEP_NODES = 500_000     # SF PV for mate verification
CANDS_PER_STATE = 10
CHECK_BONUS = 60
CHECK_LINE_BONUS = 40
KING_ATTACK_W = 10


def king_neighbours(ksq):
    out = set()
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f = chess.square_file(ksq) + df
            r = chess.square_rank(ksq) + dr
            if 0 <= f < 8 and 0 <= r < 8:
                out.add(chess.square(f, r))
    return out


def king_attack_term(board, us, them):
    """Mate-proximity: our pieces attacking squares adjacent to the
    enemy king (+10 per distinct attacker) + our Q/R on an open
    file/rank toward the enemy king (+10 each)."""
    eking = board.king(them)
    if eking is None:
        return 0
    neigh = king_neighbours(eking)
    attackers = set()
    for sq in neigh:
        for a in board.attackers(us, sq):
            attackers.add(a)
    term = KING_ATTACK_W * len(attackers)
    kf, kr = chess.square_file(eking), chess.square_rank(eking)
    for sq in board.pieces(chess.QUEEN, us) | board.pieces(chess.ROOK, us):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if f == kf:
            between = [chess.square(f, rr) for rr in range(min(r, kr) + 1, max(r, kr))]
            if all(board.piece_at(s) is None for s in between):
                term += KING_ATTACK_W
        elif r == kr:
            between = [chess.square(ff, r) for ff in range(min(f, kf) + 1, max(f, kf))]
            if all(board.piece_at(s) is None for s in between):
                term += KING_ATTACK_W
    return term


def count_checks(full_moves, us):
    """Number of OUR moves in full_moves that gave check (replayed
    with python-chess; full_moves starts with the 8 opening plies)."""
    b = chess.Board()
    n = 0
    for m in full_moves:
        mv = chess.Move.from_uci(m)
        if b.turn == us and b.gives_check(mv):
            n += 1
        b.push(mv)
    return n


def qr_attack_moves(board, us, them):
    """Q/R moves that capture, give check, or land attacking the enemy
    king's neighbourhood (king square + 8 neighbours)."""
    eking = board.king(them)
    if eking is None:
        return []
    neigh = king_neighbours(eking)
    out = []
    for mv in board.legal_moves:
        if board.piece_type_at(mv.from_square) not in (chess.QUEEN, chess.ROOK):
            continue
        if board.is_capture(mv) or board.gives_check(mv):
            out.append(mv.uci())
            continue
        b2 = board.copy()
        b2.push(mv)
        for sq in neigh:
            if b2.is_attacked_by(us, sq):
                out.append(mv.uci())
                break
    return out


def move_order_score(board, move):
    """Cheap ordering only (from beam4.py); never proof of a tactic."""
    score = 0
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if victim is None and board.is_en_passant(move):
            victim = board.piece_at(move.to_square - 8 if board.turn == chess.WHITE
                                    else move.to_square + 8)
        attacker = board.piece_at(move.from_square)
        values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                  chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}
        score += 10_000 + values.get(victim.piece_type if victim else None, 0)
        score -= values.get(attacker.piece_type if attacker else None, 0) // 10
    if move.promotion:
        score += 8_000 + {chess.KNIGHT: 320, chess.BISHOP: 330,
                          chess.ROOK: 500, chess.QUEEN: 900}.get(move.promotion, 0)
    board.push(move)
    if board.is_check():
        score += 6_000
    for sq, piece in board.piece_map().items():
        if piece.color == board.turn and board.is_attacked_by(not board.turn, sq):
            score += 500 + {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                            chess.ROOK: 500, chess.QUEEN: 900,
                            chess.KING: 20000}.get(piece.piece_type, 0) // 4
    board.pop()
    return score


# ---------- stockfish (one process, Threads=1) ----------
_engine = None
_stats = {"oracle_queries": 0, "cache_hits": 0, "sf_calls": 0, "mates_found": []}


def sf_multipv(board, nodes, multipv, us):
    _stats["sf_calls"] += 1
    infos = _engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv)
    if isinstance(infos, dict):
        infos = [infos]
    res = []
    for inf in infos:
        pv = inf.get("pv") or []
        if not pv or pv[0] not in board.legal_moves:
            continue
        sc = inf["score"].pov(us)
        res.append((pv[0].uci(), sc.score(mate_score=100000)))
    return res


def sf_eval(board, us, nodes=RESCORE_NODES):
    r = sf_multipv(board, nodes, 1, us)
    return r[0][1] if r else 0


def candidates(board, us, them, is_depth0, bans, extra_bans=None):
    """Ordered candidate our-moves (uci) for this our-turn position.
    extra_bans: moves excluded at this depth (ban-after-prefix)."""
    legal = {m.uci() for m in board.legal_moves}
    extra_bans = extra_bans or set()
    if is_depth0:
        return [m for m in sorted(legal, key=lambda u: move_order_score(
            board, chess.Move.from_uci(u)), reverse=True) if m not in bans]
    sf = sf_multipv(board, SCREEN_NODES, 12, us)
    sf_moves = [m for m, _ in sf]
    sf_score = {m: s for m, s in sf}
    checks = [m.uci() for m in board.legal_moves if board.gives_check(m)]
    qr = qr_attack_moves(board, us, them)
    ordered, seen = [], set()

    def add(m):
        if m not in seen and m in legal and m not in extra_bans:
            seen.add(m)
            ordered.append(m)

    for m in sf_moves[:5]:
        add(m)
    for m in checks:
        add(m)
        if len(ordered) >= CANDS_PER_STATE:
            break
    for m in qr:
        add(m)
        if len(ordered) >= CANDS_PER_STATE:
            break
    for m in sf_moves[5:]:
        add(m)
        if len(ordered) >= CANDS_PER_STATE:
            break
    if len(ordered) < CANDS_PER_STATE:
        caps = sorted((m for m in board.legal_moves if board.is_capture(m)),
                      key=lambda m: move_order_score(board, m), reverse=True)
        for m in caps:
            add(m.uci())
            if len(ordered) >= CANDS_PER_STATE:
                break
    return ordered, sf_score


def verify_mate_pv(state, oracle, us, max_our_moves):
    """If SF (deep) says mate from state's FEN, play the SF PV's our
    moves through the oracle and return the mating line or None."""
    board = chess.Board(state["fen"])
    infos = _engine.analyse(board, chess.engine.Limit(nodes=DEEP_NODES), multipv=1)
    _stats["sf_calls"] += 1
    if not infos:
        return None
    sc = infos[0]["score"].pov(us).score(mate_score=100000)
    if sc < 90000:
        return None
    pv = [m.uci() for m in (infos[0].get("pv") or [])]
    our_pv = pv[0::2]  # PV alternates us, house, us, ... (we are to move)
    moves = list(state["our_moves"]) + our_pv
    if len(moves) > max_our_moves:
        moves = moves[:max_our_moves]
    out = oracle(moves)
    if oracle.is_mate(out):
        return moves, out
    return None


def main():
    global _engine
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", type=int, required=True, choices=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--max-our-moves", type=int, default=9)
    ap.add_argument("--time-budget-min", type=int, default=90)
    ap.add_argument("--bans", default=None,
                    help="comma-separated first-move bans (overrides default)")
    ap.add_argument("--ban-after-prefix", default=None,
                    help="comma-separated moves banned at the first depth after --prefix (level 1 after the basin)")
    ap.add_argument("--fresh", action="store_true", help="ignore checkpoint")
    ap.add_argument("--prefix", default=None,
                    help="comma-separated fixed opening our-moves, e.g. e4d6")
    args = ap.parse_args()

    game = args.game
    spec = SPECS[game]
    us = spec["colour"]
    them = chess.BLACK if us == chess.WHITE else chess.WHITE
    bans = set(args.bans.split(",")) if args.bans else set(spec["bans"])
    prefix_len = len([m for m in args.prefix.split(",") if m]) if args.prefix else 0
    ban_after = set(args.ban_after_prefix.split(",")) if args.ban_after_prefix else set()
    work = os.path.join(WORK_ROOT, f"g{game}")
    os.makedirs(work, exist_ok=True)
    out_path = os.path.join(work, "beam4.out")
    log_f = open(os.path.join(work, "log.jsonl"), "a")
    out_f = open(out_path, "a")
    t0 = time.time()

    def log(msg):
        line = f"[{time.time()-t0:7.1f}s] {msg}"
        print(line, flush=True)
        out_f.write(line + "\n")
        out_f.flush()

    log(f"beam4_real G{game} colour={'white' if us == chess.WHITE else 'black'} "
        f"width={args.width} max_our={args.max_our_moves} bans={sorted(bans)} "
        f"ban_after_prefix={sorted(ban_after)} prefix_len={prefix_len} "
        f"budget={args.time_budget_min}min")
    oracle = RealOracle(game)
    log(f"cache loaded: {len(oracle.cache)} entries "
        f"(shared cache/oracle.jsonl)")
    _engine = chess.engine.SimpleEngine.popen_uci(SF)
    _engine.configure({"Threads": 1, "Hash": 256})

    def save_checkpoint(frontier, depth):
        with open(os.path.join(work, "checkpoint.json"), "w") as f:
            json.dump({"depth": depth, "frontier": frontier,
                       "stats": {"oracle_queries": oracle.queries,
                                 "cache_hits": oracle.hits,
                                 "sf_calls": _stats["sf_calls"],
                                 "mates_found": _stats["mates_found"]},
                       "elapsed_s": round(time.time() - t0, 1)}, f, indent=1)

    start_depth = 0
    frontier = None
    ckpt_path = os.path.join(work, "checkpoint.json")
    if not args.fresh and os.path.exists(ckpt_path):
        try:
            ck = json.load(open(ckpt_path))
            if ck.get("frontier"):
                frontier = ck["frontier"]
                start_depth = ck["depth"] + 1
                log(f"RESUMING from checkpoint depth {ck['depth']}, "
                    f"frontier {len(frontier)}")
                fm_by_q = {}
                try:
                    with open(os.path.join(work, "log.jsonl")) as lf:
                        for line in lf:
                            try:
                                e = json.loads(line)
                                fm = (e.get("out") or {}).get("full_moves")
                                if fm:
                                    fm_by_q[tuple(e.get("q") or [])] = fm
                            except Exception:
                                pass
                except Exception as e:
                    log(f"could not read log.jsonl for n_checks: {e}")
                for st in frontier:
                    fm = fm_by_q.get(tuple(st["our_moves"]))
                    st["n_checks"] = count_checks(fm, us) if fm else 0
        except Exception as e:
            log(f"checkpoint unreadable ({e}); starting fresh")

    if frontier is None:
        if args.prefix:
            prefix = [m for m in args.prefix.split(",") if m]
            out = oracle(prefix)
            if not out.get("error") and out.get("fen"):
                frontier = [{"our_moves": prefix, "fen": out["fen"], "score": 0,
                             "total_plies_estimate": out.get("total_plies", 8 + len(prefix))}]
                start_depth = len(prefix)
                log(f"prefix {prefix}: fen={out['fen']} "
                    f"total_plies={out.get('total_plies')}")
                save_checkpoint(frontier, start_depth - 1)
        if frontier is None:
            root = oracle([])
            log(f"root: house_moves={root.get('house_moves')} "
                f"fen={root.get('fen')} total_plies={root.get('total_plies')}")
            frontier = [{"our_moves": [], "fen": root["fen"], "score": 0,
                         "total_plies_estimate": root["total_plies"]}]
            save_checkpoint(frontier, -1)

    beam_top = max(8, args.width * 3 // 4)
    best_mate = None
    depth = start_depth - 1
    for depth in range(start_depth, args.max_our_moves):
        if time.time() - t0 > args.time_budget_min * 60:
            log("TIME BUDGET reached; stopping")
            break
        is_depth0 = (depth == 0)
        children = []
        log(f"--- depth {depth} (our move #{depth+1}): "
            f"frontier {len(frontier)} states ---")
        for si, st in enumerate(frontier):
            board = chess.Board(st["fen"])
            if board.turn != us:
                log(f"  state {si}: not our turn, skipping (fen {st['fen']})")
                continue
            if is_depth0:
                cands = candidates(board, us, them, True, bans)
                sf_score = {}
            else:
                extra = ban_after if depth == prefix_len else set()
                cands, sf_score = candidates(board, us, them, False, bans, extra)
            log(f"  state {si} moves={st['our_moves']} cands={len(cands)} {cands}")
            if depth >= 1 and si < 5:
                vm = verify_mate_pv(st, oracle, us, args.max_our_moves)
                if vm:
                    moves, out = vm
                    log(f"  *** MATE via SF PV from state {si}: {moves} "
                        f"total_plies={out['total_plies']}")
                    best_mate = (moves, out)
                    break
            for mv in cands:
                moves = list(st["our_moves"]) + [mv]
                out = oracle(moves)
                log_f.write(json.dumps({"q": moves, "cached": False,
                                        "out": out}) + "\n")
                log_f.flush()
                if out.get("error"):
                    log(f"    {mv}: ERROR {out.get('error')}")
                    continue
                if oracle.is_mate(out):
                    log(f"    *** MATE {moves} total_plies="
                        f"{out['total_plies']} ***")
                    best_mate = (moves, out)
                    break
                if out.get("outcome") in ("draw", "loss") or \
                        out.get("status") == "over":
                    continue
                cb = chess.Board(out["fen"])
                ev = sf_eval(cb, us)
                parent_board = chess.Board(st["fen"])
                gave_check = parent_board.gives_check(chess.Move.from_uci(mv))
                bonus = CHECK_BONUS if gave_check else 0
                n_checks = st.get("n_checks", 0) + (1 if gave_check else 0)
                ka = king_attack_term(cb, us, them)
                score = ev + bonus + CHECK_LINE_BONUS * n_checks + ka
                children.append({
                    "our_moves": moves, "fen": out["fen"], "score": score,
                    "sf_eval": ev, "check_bonus": bonus,
                    "n_checks": n_checks, "king_attack": ka,
                    "sf_move_score": sf_score.get(mv),
                    "total_plies_estimate": out["total_plies"],
                    "house_reply": (out.get("house_moves") or [None])[-1],
                })
            if best_mate:
                break
            log(f"  state {si} done: children so far {len(children)}, "
                f"oracle_q={oracle.queries} cache_hits={oracle.hits}")
        if best_mate:
            break
        if not children:
            log("no children survive; beam dead")
            break
        children.sort(key=lambda c: c["score"], reverse=True)
        new_frontier = children[:beam_top]
        seen_first = {c["our_moves"][0] for c in new_frontier}
        seen_last = {c["our_moves"][-1] for c in new_frontier}
        for c in children[beam_top:]:
            if len(new_frontier) >= args.width:
                break
            if c["our_moves"][0] not in seen_first:
                new_frontier.append(c)
                seen_first.add(c["our_moves"][0])
                seen_last.add(c["our_moves"][-1])
        for c in children[beam_top:]:
            if len(new_frontier) >= args.width:
                break
            if c in new_frontier:
                continue
            if c["our_moves"][-1] not in seen_last:
                new_frontier.append(c)
                seen_last.add(c["our_moves"][-1])
        for c in children[beam_top:]:
            if len(new_frontier) >= args.width:
                break
            if c not in new_frontier:
                new_frontier.append(c)
        log(f"depth {depth}: {len(children)} children -> frontier "
            f"{len(new_frontier)}; top scores "
            f"{[c['score'] for c in new_frontier[:5]]}; "
            f"top lines {[c['our_moves'] for c in new_frontier[:3]]}")
        frontier = new_frontier
        save_checkpoint(frontier, depth)

    save_checkpoint(frontier or [], depth)
    result = {"game": game, "best_mate": None, "frontier": frontier,
              "stats": {"oracle_queries": oracle.queries,
                        "cache_hits": oracle.hits,
                        "sf_calls": _stats["sf_calls"]},
              "elapsed_s": round(time.time() - t0, 1)}
    if best_mate:
        moves, out = best_mate
        result["best_mate"] = {"our_moves": moves,
                               "full_moves": out.get("full_moves"),
                               "total_plies": out.get("total_plies"),
                               "reason": out.get("reason")}
        _stats["mates_found"] = [moves]
        log(f"BEST MATE: {moves} total_plies={out['total_plies']}")
    else:
        log("NO MATE FOUND in beam")
        log(f"best frontier lines: "
            f"{[(c['our_moves'], c['score']) for c in (frontier or [])[:5]]}")
    with open(os.path.join(work, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    _engine.quit()
    oracle.close()
    log(f"done in {time.time()-t0:.1f}s; oracle_q={oracle.queries} "
        f"cache_hits={oracle.hits} sf_calls={_stats['sf_calls']}")


if __name__ == "__main__":
    main()
