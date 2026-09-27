"""
v51_r1_transfer_north: v37 + W-Tree R1 (factory TRANSFER_NORTH to fresh support).

Adds ONE rule to v37 (no other changes):

R1 trigger (W-Tree L02+L08, offline precision 0.97 / 0.70, n=3834):
  factory_move_cd <= 1 AND counts[MINER] == 0 AND
  north neighbour holds a friendly non-factory unit with energy in [280, 600] AND
  no wall blocks NORTH out of factory.

R1 action: factory issues TRANSFER_NORTH (donates energy to that support unit).
Insertion: between mine_build_action and BUILD_SCOUT branches in the factory
elif chain (so transfer takes priority over scout-build but not over miner-build).
"""
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
SCOUT_DELAY_STEP = 24

# Precompute mirror wall lookup: E<->W swap, N and S unchanged
MIRROR_WALL = [0] * 16
for _v in range(16):
    _m = (_v & 1) | (_v & 4)
    if _v & 2: _m |= 8
    if _v & 8: _m |= 2
    MIRROR_WALL[_v] = _m

_memory = {}


def agent(obs, config):
    """Main entry point â€” wrapped for exception safety."""
    global _memory
    try:
        return _agent_inner(obs, config)
    except Exception:
        return {uid: "IDLE" for uid in obs.robots if obs.robots[uid][4] == obs.player}


def _agent_inner(obs, config):
    global _memory
    actions = {}
    width = config.width
    south = obs.southBound
    north = obs.northBound
    player = obs.player
    turn = getattr(obs, "step", 0)

    # ========== PERSISTENT WALL MEMORY ==========
    # Walls persist across turns. We also infer mirrored walls (E/W symmetry).
    if turn == 0:
        _memory = {}
    if "walls" not in _memory:
        _memory["walls"] = {}
    walls_mem = _memory["walls"]

    for i, w in enumerate(obs.walls):
        if w == -1:
            continue
        r = south + i // width
        c = i % width
        walls_mem[(c, r)] = w
        # Mirror: col' = (width - 1) - col, swap E<->W bits
        mc = (width - 1) - c
        mw = MIRROR_WALL[w]
        if (mc, r) not in walls_mem:
            walls_mem[(mc, r)] = mw

    # Purge old cells to save memory
    if len(walls_mem) > 2000:
        cutoff = south - 5
        walls_mem = {k: v for k, v in walls_mem.items() if k[1] >= cutoff}
        _memory["walls"] = walls_mem

    # ========== HELPER FUNCTIONS ==========
    def get_wall(c, r):
        """Get wall bits. Unknown cells = 0 (optimistic: assume passable)."""
        return walls_mem.get((c, r), 0)

    def can_move(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + dc, r + dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return not (get_wall(c, r) & WALL_BITS[d])

    def can_jump(c, r, d):
        """Can factory jump in direction d? Lands 2 cells away over wall."""
        dc, dr = OFFSETS[d]
        nc, nr = c + 2 * dc, r + 2 * dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return get_wall(nc, nr) != 15  # don't land in fully walled cell

    def action_dest(c, r, act):
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            return c + 2 * dc, r + 2 * dr
        if act in OFFSETS:
            dc, dr = OFFSETS[act]
            return c + dc, r + dr
        return c, r

    # ========== ROBOT CLASSIFICATION ==========
    my_robots = {uid: d for uid, d in obs.robots.items() if d[4] == player}
    enemy_robots = {uid: d for uid, d in obs.robots.items() if d[4] != player}
    enemy_factories = [d for d in enemy_robots.values() if d[0] == FACTORY]
    my_positions = {(d[1], d[2]): uid for uid, d in my_robots.items()}
    reserved = set()
    counts = {rt: sum(1 for d in my_robots.values() if d[0] == rt) for rt in range(4)}

    # Crystal locations (for worker pathing)
    crystals = {}
    for k, v in obs.crystals.items():
        parts = k.split(",")
        crystals[(int(parts[0]), int(parts[1]))] = v

    mining_nodes = set()
    for k in getattr(obs, "miningNodes", {}):
        parts = k.split(",")
        mining_nodes.add((int(parts[0]), int(parts[1])))

    own_mines = {}
    for k, v in getattr(obs, "mines", {}).items():
        parts = k.split(",")
        pos = (int(parts[0]), int(parts[1]))
        if len(v) >= 3 and v[2] == player:
            own_mines[pos] = v

    # ========== BFS: STANDARD (no jumps) ==========
    def bfs_first_step(start, goals, depth=20, avoid_occupied=True):
        """BFS returning first action to reach any goal cell."""
        if not goals:
            return None
        goal_set = set(goals)
        if start in goal_set:
            return "IDLE"
        q = deque([(start, None, 0)])
        seen = {start}
        while q:
            (c, r), first_d, dist = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue
            for d in DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                if (nc, nr) in seen:
                    continue
                if avoid_occupied and (nc, nr) in reserved:
                    continue
                if avoid_occupied and (nc, nr) in my_positions and (nc, nr) != start:
                    continue
                seen.add((nc, nr))
                q.append(((nc, nr), first_d or d, dist + 1))
        return None

    # ========== BFS: JUMP-PREFERRED (factory only) ==========
    def bfs_jump(start, goals, jump_cd, depth=20, north_only_jump=False):
        """
        BFS with jump state tracking.
        KEY INSIGHT: Explores jumps BEFORE walks when cooldown is ready,
        because a jump covers 2 cells in 1 turn (vs walking = 1 cell/turn).

        north_only_jump=True restricts jump expansion to JUMP_NORTH so the
        20-turn cooldown is preserved for emergencies. Used in late game
        when scroll pressure makes lateral jumps catastrophic.
        """
        if not goals:
            return None
        goal_set = set(goals)
        q = deque([(start, None, 0, min(jump_cd, 20))])
        seen = {(start[0], start[1], jump_cd <= 0)}
        jump_dirs = ("NORTH",) if north_only_jump else DIRS
        while q:
            (c, r), first_d, dist, jcd = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue

            # JUMP moves explored first when cooldown ready
            if jcd <= 0:
                for d in jump_dirs:
                    if not can_jump(c, r, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = c + 2 * dc, r + 2 * dr
                    key = (nc, nr, False)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append(((nc, nr), first_d or f"JUMP_{d}", dist + 1, 20))

            # Normal walking moves
            for d in DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                njcd = max(0, jcd - 1)
                key = (nc, nr, njcd <= 0)
                if key in seen:
                    continue
                seen.add(key)
                q.append(((nc, nr), first_d or d, dist + 1, njcd))

        return None

    # ========== ACTION RECORDING ==========
    def record(uid, act, col, row):
        """Record action and reserve destination cell."""
        actions[uid] = act
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            reserved.add((col + 2 * dc, row + 2 * dr))
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            reserved.add((col + dc, row + dr))
        elif act.startswith("BUILD_"):
            parts = act.split("_")
            d = parts[2] if len(parts) >= 3 and parts[2] in OFFSETS else "NORTH"
            dc, dr = OFFSETS[d]
            reserved.add((col + dc, row + dr))
        else:
            reserved.add((col, row))

    # ========== FIND FACTORY ==========
    factory_uid = None
    factory_col, factory_row = 0, 0
    for uid, d in my_robots.items():
        if d[0] == FACTORY:
            factory_uid = uid
            factory_col, factory_row = d[1], d[2]
            break

    if not factory_uid:
        return actions  # factory dead, GG

    factory_energy = my_robots[factory_uid][3]
    factory_gap = factory_row - south  # rows above death

    fdata = my_robots[factory_uid]
    f_move_cd = fdata[5] if len(fdata) > 5 else 0
    f_jump_cd = fdata[6] if len(fdata) > 6 else 0
    f_build_cd = fdata[7] if len(fdata) > 7 else 0

    own_support_energy = sum(d[3] for d in my_robots.values() if d[0] != FACTORY)
    own_support_count = sum(1 for d in my_robots.values() if d[0] != FACTORY)
    visible_enemy_support_energy = sum(d[3] for d in enemy_robots.values() if d[0] != FACTORY)
    visible_enemy_support_count = sum(1 for d in enemy_robots.values() if d[0] != FACTORY)
    collision_tiebreak_bad = (
        factory_gap > 3
        and visible_enemy_support_count > 0
        and (
            own_support_energy + 15 < visible_enemy_support_energy
            or (
                own_support_energy <= visible_enemy_support_energy + 15
                and own_support_count < visible_enemy_support_count
            )
        )
    )

    enemy_factory_threats = set()
    enemy_factory_jump_threats = set()
    if collision_tiebreak_bad:
        for enemy in enemy_factories:
            ec, er = enemy[1], enemy[2]
            emove_cd = enemy[5] if len(enemy) > 5 else 0
            ejump_cd = enemy[6] if len(enemy) > 6 else 0
            enemy_factory_threats.add((ec, er))
            if emove_cd <= 1:
                for d in DIRS:
                    if can_move(ec, er, d):
                        enemy_factory_threats.add(action_dest(ec, er, d))
            if ejump_cd <= 0:
                for d in DIRS:
                    if can_jump(ec, er, d):
                        enemy_factory_threats.add(action_dest(ec, er, f"JUMP_{d}"))
    if factory_gap > 3:
        for enemy in enemy_factories:
            ec, er = enemy[1], enemy[2]
            if abs(ec - factory_col) + abs(er - factory_row) > 4:
                continue
            emove_cd = enemy[5] if len(enemy) > 5 else 0
            enemy_factory_jump_threats.add((ec, er))
            if emove_cd <= 1:
                for d in DIRS:
                    if can_move(ec, er, d):
                        enemy_factory_jump_threats.add(action_dest(ec, er, d))

    def safe_factory_action(act):
        dest = action_dest(factory_col, factory_row, act)
        if enemy_factory_threats and dest in enemy_factory_threats:
            return False
        if act.startswith("JUMP_") and dest in enemy_factory_jump_threats:
            return False
        return True

    # ========== FACTORY PLANNING (MOST IMPORTANT!) ==========
    # Emergency: â‰¤ 2 rows from south bound = imminent death
    if factory_gap <= 2 and south > 0:
        if f_jump_cd <= 0 and can_jump(factory_col, factory_row, "NORTH") and safe_factory_action("JUMP_NORTH"):
            nc, nr = factory_col, factory_row + 2
            if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                record(factory_uid, "JUMP_NORTH", factory_col, factory_row)
        elif f_jump_cd <= 0:
            for d in ("EAST", "WEST"):
                act = f"JUMP_{d}"
                if can_jump(factory_col, factory_row, d) and safe_factory_action(act):
                    dc, dr = OFFSETS[d]
                    nc, nr = factory_col + 2 * dc, factory_row + 2 * dr
                    if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                        record(factory_uid, act, factory_col, factory_row)
                        break

    if factory_uid not in actions:
        # Mine economy: if a visible adjacent mining node is open, convert one
        # factory turn and 300 energy into a mine the factory can harvest.
        spawn = (factory_col, factory_row + 1)
        mine_build_action = None
        if f_build_cd <= 1 and factory_energy >= 650 and factory_gap > 6 and counts[MINER] < 1:
            for d in ("NORTH",):
                dc, dr = OFFSETS[d]
                mpos = (factory_col + dc, factory_row + dr)
                if mpos not in mining_nodes or mpos in my_positions:
                    continue
                if not can_move(factory_col, factory_row, d):
                    continue
                mine_build_action = f"BUILD_MINER_{d}"
                break

        spawn_ok = (
            f_build_cd <= 1
            and spawn not in my_positions
            and factory_row + 1 <= north
            and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        )

        # R1 (W-Tree L02 / L08): TRANSFER_NORTH to a fresh adj-north support unit.
        # Fires only when no miner exists yet, factory is move-ready, and the
        # north neighbour holds a friendly worker/scout/miner whose energy is
        # in the "near-full but with headroom" band the tree learned from
        # top-15 replays. The wall check mirrors the BUILD branches so we
        # never burn a turn on a transfer that the engine would no-op.
        transfer_north_action = None
        if (
            f_move_cd <= 1
            and counts[MINER] == 0
            and factory_row + 1 <= north
            and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        ):
            target_uid = my_positions.get((factory_col, factory_row + 1))
            if target_uid is not None and target_uid != factory_uid:
                target_energy = my_robots[target_uid][3]
                if 280 <= target_energy <= 600:
                    transfer_north_action = "TRANSFER_NORTH"

        if mine_build_action:
            record(factory_uid, mine_build_action, factory_col, factory_row)
            counts[MINER] += 1
        elif transfer_north_action:
            record(factory_uid, transfer_north_action, factory_col, factory_row)
        elif (
            turn >= SCOUT_DELAY_STEP
            and spawn_ok
            and counts[SCOUT] < 1
            and factory_energy >= 50
            and factory_gap > 4
        ):
            record(factory_uid, "BUILD_SCOUT", factory_col, factory_row)
            counts[SCOUT] += 1
        elif f_move_cd > 1:
            record(factory_uid, "IDLE", factory_col, factory_row)
        else:
            if (factory_col, factory_row) in own_mines and factory_gap > 10:
                record(factory_uid, "IDLE", factory_col, factory_row)
            if factory_uid in actions:
                pass
            else:
                for d in ("NORTH",):
                    dc, dr = OFFSETS[d]
                    mpos = (factory_col + dc, factory_row + dr)
                    if mpos in own_mines and can_move(factory_col, factory_row, d) and safe_factory_action(d):
                        record(factory_uid, d, factory_col, factory_row)
                        break
            if factory_uid in actions:
                pass
            else:
                # Main pathfinding: BFS toward row + 20 using jump-preferred search.
                # If gap is small, restrict jump expansion to JUMP_NORTH so
                # we keep the 20-turn cooldown ready for a NORTH escape; the
                # explicit fallbacks below still allow lateral jumps when
                # walking is impossible.
                target_row = min(north, factory_row + 20)
                factory_goals = [(tc, target_row) for tc in range(width)]
                step = bfs_jump(
                    (factory_col, factory_row),
                    factory_goals,
                    f_jump_cd,
                    depth=20,
                    north_only_jump=factory_gap <= 8,
                )
                if step and not safe_factory_action(step):
                    step = None

                # Fallback 1: closer target with standard BFS
                if not step:
                    closer_goals = [(tc, min(north, factory_row + 5)) for tc in range(width)]
                    step = bfs_first_step((factory_col, factory_row), closer_goals, depth=10, avoid_occupied=False)
                    if step and not safe_factory_action(step):
                        step = None

                # Fallback 2: try any northward direction
                if not step:
                    for d in ("NORTH", "EAST", "WEST"):
                        if can_move(factory_col, factory_row, d) and safe_factory_action(d):
                            step = d
                            break

                # Fallback 3: walk SOUTH to escape dead-end (counterintuitive but life-saving)
                if not step and factory_gap <= 3:
                    if can_move(factory_col, factory_row, "SOUTH") and safe_factory_action("SOUTH"):
                        step = "SOUTH"

                # Fallback 4: desperation jump any direction
                if not step and f_jump_cd <= 0 and factory_gap <= 3:
                    for d in ("EAST", "WEST", "SOUTH"):
                        act = f"JUMP_{d}"
                        if can_jump(factory_col, factory_row, d) and safe_factory_action(act):
                            step = act
                            break

                if step and step != "IDLE":
                    record(factory_uid, step, factory_col, factory_row)
                else:
                    # Absolute last resort: build worker to break wall ahead
                    if spawn_ok and counts[WORKER] < 1 and factory_energy >= 200 and factory_gap <= 4:
                        record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
                        counts[WORKER] += 1
                    else:
                        record(factory_uid, "IDLE", factory_col, factory_row)

    # ========== SCOUT PLANNING ==========
    scouts = [(uid, d) for uid, d in my_robots.items() if d[0] == SCOUT]
    for uid, data in scouts:
        col, row = data[1], data[2]
        move_cd = data[5] if len(data) > 5 else 0
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        # Scout runs ahead of factory for vision
        scout_goals = [(tc, min(north, factory_row + 8)) for tc in range(width)]
        step = bfs_first_step((col, row), scout_goals, depth=12)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== MINER PLANNING ==========
    miners = [(uid, d) for uid, d in my_robots.items() if d[0] == MINER]
    for uid, data in miners:
        col, row = data[1], data[2]
        energy = data[3]
        if (col, row) in mining_nodes and energy >= 100:
            record(uid, "TRANSFORM", col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== WORKER PLANNING (only spawned as last resort) ==========
    workers = [(uid, d) for uid, d in my_robots.items() if d[0] == WORKER]
    for uid, data in workers:
        col, row = data[1], data[2]
        energy = data[3]
        move_cd = data[5] if len(data) > 5 else 0
        if (get_wall(col, row) & WALL_BITS["NORTH"]) and energy >= 100:
            record(uid, "REMOVE_NORTH", col, row)
            continue
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        worker_gap = row - south
        if worker_gap <= 4:
            target_goals = [(factory_col, min(north, factory_row + 5))]
        else:
            nearby_crystals = [
                c for c in crystals if abs(c[0] - col) + abs(c[1] - row) <= 8
            ]
            if nearby_crystals:
                target_goals = sorted(nearby_crystals, key=lambda t: abs(t[0] - col) + abs(t[1] - row))[:3]
            else:
                target_goals = [(factory_col, min(north, factory_row + 5))]
        step = bfs_first_step((col, row), target_goals, depth=10)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== DEFAULT ==========
    for uid in my_robots:
        if uid not in actions:
            actions[uid] = "IDLE"

    return actions
