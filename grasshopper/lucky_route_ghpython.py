"""lucky_route.gh 의 GhPython 컴포넌트 소스 (단독 실행도 가능).

역할:
  street_segments.geojson (품질 점수가 붙은 거리 세그먼트)
  + daily_reading.json (오늘의 품질 가중치)
  → 최단 경로(fastest)와 행운 경로(lucky)를 계산해
    outputs/fastest_route.geojson, outputs/lucky_route.geojson,
    outputs/design_space.csv 로 저장.

비용 함수:
  luck(seg)   = Σ_q  quality_weights[q] × seg.properties[q]      (0~1)
  fastest cost = length_m
  lucky cost   = length_m × (LUCK_BIAS − luck)   # 운이 좋은 길일수록 저렴

GhPython 입력:  segments_path(str), reading_path(str),
               origin(str "lon,lat"), destination(str "lon,lat"),
               out_dir(str), run(bool)
GhPython 출력:  fastest_pts, lucky_pts (폴리라인 좌표), summary(str)

단독 실행:
  python grasshopper/lucky_route_ghpython.py \
      --segments data/processed/street_segments.geojson \
      --reading engine/daily_reading.json \
      --origin " -73.9990,40.7280" --dest " -73.9930,40.7340"
"""

import csv
import heapq
import json
import os

QUALITIES = ["green", "water", "sunlight", "open_sky",
             "quiet", "vibrant", "rest", "culture"]
LUCK_BIAS = 1.6  # 비용이 항상 양수가 되도록 하는 오프셋 (luck 최대 1.0)


def _key(coord):
    return (round(coord[0], 6), round(coord[1], 6))


def load_segments(path):
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    segments = []
    for feat in gj["features"]:
        if feat["geometry"]["type"] != "LineString":
            continue
        coords = feat["geometry"]["coordinates"]
        props = feat["properties"]
        segments.append({
            "id": props.get("segment_id", len(segments)),
            "coords": coords,
            "length": float(props.get("length_m", 1.0)),
            "qualities": {q: float(props.get(q, 0.0)) for q in QUALITIES},
        })
    return segments


def luck_score(seg, weights):
    return sum(weights.get(q, 0.0) * seg["qualities"][q] for q in QUALITIES)


def build_graph(segments, cost_fn):
    """무방향 그래프: node → [(neighbor, cost, seg_index)]"""
    graph = {}
    for i, seg in enumerate(segments):
        a, b = _key(seg["coords"][0]), _key(seg["coords"][-1])
        cost = cost_fn(seg)
        graph.setdefault(a, []).append((b, cost, i))
        graph.setdefault(b, []).append((a, cost, i))
    return graph


def nearest_node(graph, coord):
    lon, lat = coord
    return min(graph, key=lambda n: (n[0] - lon) ** 2 + (n[1] - lat) ** 2)


def dijkstra(graph, start, goal):
    """start→goal 최소 비용 경로. (노드 리스트, 세그먼트 인덱스 리스트) 반환."""
    dist = {start: 0.0}
    prev = {}
    pq = [(0.0, start)]
    visited = set()
    while pq:
        d, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        if node == goal:
            break
        for nb, cost, seg_i in graph.get(node, []):
            nd = d + cost
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = (node, seg_i)
                heapq.heappush(pq, (nd, nb))
    if goal not in prev and goal != start:
        return [], []
    nodes, segs = [goal], []
    cur = goal
    while cur != start:
        cur, seg_i = prev[cur]
        nodes.append(cur)
        segs.append(seg_i)
    nodes.reverse()
    segs.reverse()
    return nodes, segs


def route_feature_collection(segments, seg_indices, weights, route_type):
    feats = []
    for order, i in enumerate(seg_indices):
        seg = segments[i]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": seg["coords"]},
            "properties": {
                "segment_id": seg["id"], "order": order,
                "length_m": seg["length"],
                "luck_score": round(luck_score(seg, weights), 4),
                "route_type": route_type,
                **{q: seg["qualities"][q] for q in QUALITIES},
            },
        })
    total_len = sum(segments[i]["length"] for i in seg_indices)
    total_luck = (sum(luck_score(segments[i], weights) *
                      segments[i]["length"] for i in seg_indices) /
                  total_len) if total_len else 0.0
    return {
        "type": "FeatureCollection",
        "properties": {"route_type": route_type,
                       "total_length_m": round(total_len, 1),
                       "mean_luck": round(total_luck, 4)},
        "features": feats,
    }


def write_design_space(path, segments, weights, fastest_set, lucky_set):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment_id", "length_m", *QUALITIES,
                    "luck_score", "in_fastest", "in_lucky"])
        for i, seg in enumerate(segments):
            w.writerow([
                seg["id"], round(seg["length"], 1),
                *[seg["qualities"][q] for q in QUALITIES],
                round(luck_score(seg, weights), 4),
                int(i in fastest_set), int(i in lucky_set),
            ])


def solve(segments_path, reading_path, origin, destination, out_dir):
    segments = load_segments(segments_path)
    with open(reading_path, encoding="utf-8") as f:
        weights = json.load(f)["quality_weights"]

    g_fast = build_graph(segments, lambda s: s["length"])
    g_lucky = build_graph(
        segments, lambda s: s["length"] * (LUCK_BIAS - luck_score(s, weights)))

    start = nearest_node(g_fast, origin)
    goal = nearest_node(g_fast, destination)

    f_nodes, f_segs = dijkstra(g_fast, start, goal)
    l_nodes, l_segs = dijkstra(g_lucky, start, goal)

    fast_fc = route_feature_collection(segments, f_segs, weights, "fastest")
    lucky_fc = route_feature_collection(segments, l_segs, weights, "lucky")

    os.makedirs(out_dir, exist_ok=True)
    for name, fc in [("fastest_route.geojson", fast_fc),
                     ("lucky_route.geojson", lucky_fc)]:
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=1)
    write_design_space(os.path.join(out_dir, "design_space.csv"),
                       segments, weights, set(f_segs), set(l_segs))

    summary = ("fastest: {:.0f} m / luck {:.3f}   |   "
               "lucky: {:.0f} m / luck {:.3f}").format(
        fast_fc["properties"]["total_length_m"], fast_fc["properties"]["mean_luck"],
        lucky_fc["properties"]["total_length_m"], lucky_fc["properties"]["mean_luck"])
    return f_nodes, l_nodes, summary


# ── GhPython 컴포넌트 모드 ─────────────────────────────────────────────
try:
    import Rhino.Geometry as rg  # noqa: F401  (Rhino 안에서만 존재)
    _IN_RHINO = True
except ImportError:
    _IN_RHINO = False

if _IN_RHINO:
    if run:  # noqa: F821  — GhPython 입력
        _o = [float(v) for v in origin.split(",")]        # noqa: F821
        _d = [float(v) for v in destination.split(",")]   # noqa: F821
        _fn, _ln, summary = solve(segments_path, reading_path,  # noqa: F821
                                  _o, _d, out_dir)              # noqa: F821
        fastest_pts = [rg.Point3d(x, y, 0) for x, y in _fn]
        lucky_pts = [rg.Point3d(x, y, 0) for x, y in _ln]

# ── 단독 실행 모드 ────────────────────────────────────────────────────
elif __name__ == "__main__":
    import argparse
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(description="행운 경로 계산 (Rhino 없이 실행)")
    p.add_argument("--segments",
                   default=os.path.join(ROOT, "data/processed/street_segments.geojson"))
    p.add_argument("--reading",
                   default=os.path.join(ROOT, "engine/daily_reading.json"))
    p.add_argument("--origin", required=True, help='"lon,lat"')
    p.add_argument("--dest", required=True, help='"lon,lat"')
    p.add_argument("--outdir", default=os.path.join(ROOT, "outputs"))
    a = p.parse_args()
    _, _, summary = solve(
        a.segments, a.reading,
        [float(v) for v in a.origin.split(",")],
        [float(v) for v in a.dest.split(",")], a.outdir)
    print(summary)
