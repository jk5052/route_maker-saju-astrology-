"""Offline 60-day routing experiment; never writes production rules or outputs.

Run with the repository virtualenv to require the same calendar/ephemeris
backends as the saved reading. Experimental matrices and coefficients exist
only in this script and its analysis artifacts.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from compare_reading_routes import overlap, router
import combine_reading as engine

VARIANTS = {
    "baseline": {"label": "기존 결합", "top_k": None, "center": False, "alpha": 1.0},
    "sparse_2": {"label": "(a) 성질당 2개 속성", "top_k": 2, "center": False, "alpha": 1.0},
    "sparse_3": {"label": "(a) 성질당 3개 속성", "top_k": 3, "center": False, "alpha": 1.0},
    "centered": {"label": "(b) 평균 대비 편차", "top_k": None, "center": True, "alpha": 1.0},
    "alpha_1_5": {"label": "(c) luck 계수 1.5", "top_k": None, "center": False, "alpha": 1.5},
    "alpha_2_0": {"label": "(c) luck 계수 2.0", "top_k": None, "center": False, "alpha": 2.0},
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_matrix(path):
    with path.open(newline="", encoding="utf-8") as f:
        return {row["quality"]: {s: float(v) for s, v in row.items() if s != "quality"}
                for row in csv.DictReader(f)}


def sparse_matrix(matrix, k):
    """Keep top k, break ties by CSV column order, preserve each row's mass."""
    result = {}
    for quality, row in matrix.items():
        if not 1 <= k <= len(row):
            raise ValueError("top_k must be between 1 and the number of attributes")
        kept = sorted(row, key=lambda s: -row[s])[:k]
        scale = sum(row.values()) / sum(row[s] for s in kept)
        result[quality] = {s: v * scale if s in kept else 0.0 for s, v in row.items()}
    return result


def weights_from_matrix(quality, matrix):
    # Match production accumulation order and its final four-decimal rounding.
    out = dict.fromkeys(next(iter(matrix.values())), 0.0)
    for q, row in matrix.items():
        for s, value in row.items():
            out[s] += quality.get(q, 0.0) * value
    total = sum(out.values())
    if total <= 0:
        raise ValueError("Cannot normalize a zero street preference vector")
    return {s: round(v / total, 4) for s, v in out.items()}


def center_weights(weights):
    # Rounded weights need not sum to exactly one. Use their actual mean.
    mean = statistics.mean(weights.values())
    return {s: v - mean for s, v in weights.items()}


def vector_stats(vectors):
    return {s: {"min": min(v[s] for v in vectors),
                "max": max(v[s] for v in vectors),
                "mean": statistics.mean(v[s] for v in vectors),
                "std_population": statistics.pstdev(v[s] for v in vectors)}
            for s in vectors[0]}


def route(segments, start, goal, weights=None, alpha=1.0):
    luck = [router.luck_score(s, weights) for s in segments] if weights is not None else [0.0] * len(segments)
    factors = [router.LUCK_BIAS - alpha * v for v in luck] if weights is not None else [1.0] * len(segments)
    if any(not math.isfinite(f) or f <= 0 for f in factors):
        raise ValueError("Experiment would create nonpositive edge costs; no clipping or Dijkstra run allowed")
    factor_by_id = {s["id"]: f for s, f in zip(segments, factors)}
    graph = router.build_graph(segments, lambda s: s["length"] * factor_by_id[s["id"]])
    nodes, indices = router.dijkstra(graph, start, goal)
    if not indices:
        raise ValueError("Expected a nonempty connected route")
    ids = [segments[i]["id"] for i in indices]
    key = "r_" + hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()[:12]
    return {"route_id": key, "segment_ids": ids, "segment_indices": indices, "nodes": nodes,
            "length_m": sum(segments[i]["length"] for i in indices),
            "cost": sum(segments[i]["length"] * factors[i] for i in indices),
            "min_edge_cost_factor": min(factors), "max_edge_luck": max(luck),
            "negative_luck_segment_count": sum(v < 0 for v in luck)}


def summarize_routes(routes, fastest_length):
    counts = Counter(r["route_id"] for r in routes)
    detours = [r["length_m"] - fastest_length for r in routes]
    if min(detours) < -1e-7:
        raise AssertionError("Weighted route cannot be shorter than physical shortest path")
    return {"unique_route_count": len(counts), "route_day_counts": dict(counts.most_common()),
            "modal_route_days": max(counts.values()),
            "day_to_day_changes": sum(a["route_id"] != b["route_id"] for a, b in zip(routes, routes[1:])),
            "mean_length_m": statistics.mean(r["length_m"] for r in routes),
            "mean_detour_m": statistics.mean(detours), "max_detour_m": max(detours),
            "mean_detour_pct": 100 * statistics.mean(detours) / fastest_length,
            "min_edge_cost_factor": min(r["min_edge_cost_factor"] for r in routes),
            "negative_luck_segment_days": sum(r["negative_luck_segment_count"] for r in routes)}


def geojson_route(segments, result, weights, day):
    fc = router.route_feature_collection(segments, result["segment_indices"], weights, "combined")
    for i, feature in enumerate(fc["features"]):
        coords = feature["geometry"]["coordinates"]
        if router._key(coords[0]) != result["nodes"][i]:
            feature["geometry"]["coordinates"] = list(reversed(coords))
    fc["properties"].update({"date": day, "route_id": result["route_id"], "quality_weights": weights,
                              "snapped_origin": result["nodes"][0], "snapped_destination": result["nodes"][-1]})
    return fc


def markdown_report(summary, daily, matrices):
    p, base = summary["inputs"], summary["baseline"]
    lines = [f"# {p['start_date']}부터 {p['days']}일 경로 민감도 분석", "",
             f"기간: **{p['start_date']}–{p['end_date']}**, 양 끝 날짜 포함 {p['days']}일.",
             f"생년월일 `{p['birth']}`, 출생 시각 `{p['birth_time']}`. 출발 `{p['origin']}` → 도착 `{p['destination']}`.",
             f"현재 합성 거리 격자 **{p['segment_count']}개 구간**과 기존 규칙·행렬·비용 함수를 사용했다. "
             "실제 Williamsburg 보행망에서 얻은 결과는 아니다.", "",
             "## 실행 및 비교 기준", "",
             "- 저장된 프로필의 정밀 백엔드로 매일 원자료를 새로 계산했다. 폴백 실행은 허용하지 않았다.",
             f"- Python {p['python']}; lunar_python {p['versions']['lunar_python']}; astronomy-engine {p['versions']['astronomy-engine']}.",
             f"- {p['replay_date']} 재계산은 기존 저장 리딩 전체와 일치하는지 확인했다.",
             "- 서로 다른 경로는 순서 있는 `segment_id` 목록으로 구별한다. 길이가 같아도 구간이 다르면 별도 경로다.",
             "- 사주/점성술 분기일은 같은 날짜의 두 단독 경로가 서로 다른 날이다.",
             f"- 표준편차는 이 기간 전체 {p['days']}개 값을 대상으로 한 모집단 표준편차(`ddof=0`)다.",
             f"- 우회 거리 = 선택 경로 길이 − 동일 그래프·끝점의 거리 기준 최단 길이 **{summary['fastest']['length_m']:.1f}m**. "
             f"평균은 경로 종류별이 아니라 {p['days']}일별 동일 가중 평균이다.",
             "- 민감도 실험은 결합 벡터만 사용하며 각 방안을 독립 적용했다. 실제 엔진·행렬·계수 파일은 수정하지 않았다.", "",
             "## 기본 구조의 경로 변화", "",
             f"| 체계 | 서로 다른 경로 | 가장 잦은 경로 사용일 | 전일 대비 변경 횟수 / {p['days']-1} | 평균 우회(m) |",
             "|---|---:|---:|---:|---:|"]
    for name, label in [("saju", "사주만"), ("astrology", "점성술만"), ("combined", "결합")]:
        r = base[name]
        lines.append(f"| {label} | {r['unique_route_count']} | {r['modal_route_days']} / {p['days']} | {r['day_to_day_changes']} | {r['mean_detour_m']:.1f} |")
    lines += ["", f"**사주만/점성술만 경로가 갈라진 날: {base['saju_astrology_divergence_days']} / {p['days']}일 "
              f"({base['saju_astrology_divergence_days']/p['days']:.1%}).**", "",
              "날짜: " + ", ".join(base["saju_astrology_divergence_dates"]), "",
              "결합 경로별 사용일:", "", "| 경로 ID | 사용일 수 | 날짜 |", "|---|---:|---|"]
    for key, count in base["combined"]["route_day_counts"].items():
        days = [d["date"] for d in daily if d["baseline"]["combined"]["route_id"] == key]
        dates = "아래 일별 표 참조" if len(days) > 12 else ", ".join(days)
        lines.append(f"| `{key}` | {count} | {dates} |")
    lines += ["", "## 결합 거리 가중치 w[s]의 변동", "",
              "라우터에 전달한 소수점 4자리 가중치로 계산했다. 사주만·점성술만의 동일 통계도 summary.json에 있다.", "",
              "| 속성 | 최소 | 최대 | 평균 | 표준편차 (ddof=0) |", "|---|---:|---:|---:|---:|"]
    for s, row in summary["weight_statistics"]["combined"].items():
        lines.append(f"| {s} | {row['min']:.4f} | {row['max']:.4f} | {row['mean']:.6f} | {row['std_population']:.6f} |")
    lines += ["", "## 민감도 방안 비교", "",
              f"| 방안 | 서로 다른 경로 | 최빈 경로 사용일 | 전일 대비 변경 / {p['days']-1} | 평균 우회(m) | 최대 우회(m) | 최소 비용 배수 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for key, row in summary["experiments"].items():
        lines.append(f"| {VARIANTS[key]['label']} | {row['unique_route_count']} | {row['modal_route_days']} | "
                     f"{row['day_to_day_changes']} | {row['mean_detour_m']:.1f} | {row['max_detour_m']:.1f} | {row['min_edge_cost_factor']:.6f} |")
    lines += ["", "최소 비용 배수는 모든 날짜 × 모든 구간에서 `cost / length`의 최솟값이다. "
              "모든 실험에서 양수임을 확인했으며 음수 비용을 잘라내거나 잘못된 Dijkstra를 실행하지 않았다.", "",
              "### (a) 행렬 희소화", "",
              "기존 행렬의 각 성질에서 가장 큰 계수 2개 또는 3개를 유지하고 나머지를 0으로 만들었다. "
              "동률은 기존 CSV 열 순서로 처리했다. 남긴 계수는 **원래 행의 합을 보존하도록 같은 비율로 확대**했다. "
              "성질별 투영 총량을 바꾸지 않고 연결의 집중도만 비교하기 위한 선택이다. 확대 후 일부 계수는 1을 넘을 수 있으나 "
              "확률이 아닌 투영 계수이며 최종 거리 가중치는 기존처럼 정규화한다.", "",
              "| 성질 | 2개 유지 | 3개 유지 |", "|---|---|---|"]
    for q in matrices["baseline"]:
        cols = [", ".join(s for s, v in matrices[k][q].items() if v) for k in ("sparse_2", "sparse_3")]
        lines.append(f"| {q} | {cols[0]} | {cols[1]} |")
    lines += ["", "행렬 수치는 summary.json의 experimental_matrices에 모두 저장했다. 계수와 동률 처리 규칙은 초기 실험 설계값이다.", "",
              "### (b) 가중치 중심화", "", "```text",
              "d[s] = w[s] − mean(w)", "luck_centered(edge) = Σs d[s] × attribute(edge,s)",
              "cost(edge) = length(edge) × (1.6 − luck_centered(edge))", "```", "",
              "반올림된 w의 실제 평균을 빼고 다시 정규화하거나 확대하지 않았다. "
              "평균보다 낮은 속성은 음의 계수를 갖는다. 이는 그 속성을 덜 선호하는 것에서 비용으로 불리하게 반영하는 것으로 의미가 바뀐다. "
              "예를 들어 그날 green이 평균보다 낮으면 녹지가 많은 구간도 상대적으로 불리해질 수 있다.",
              f"음의 luck 발생: {summary['experiments']['centered']['negative_luck_segment_days']} / "
              f"{p['days']*p['segment_count']} 구간·일.", "",
              "### (c) luck 영향 계수", "", "```text", "cost(edge) = length(edge) × (1.6 − α × luck(edge))", "```", "",
              "기존 α=1과 α=1.5, 2.0을 비교했다. 가중치·행렬은 그대로다. "
              f"이번 {p['days']}일의 최대 luck은 {summary['baseline_max_luck']:.7f}이므로 비용이 양수인 α의 상한은 "
              f"{summary['positive_cost_alpha_bound']:.6f} 미만이다. 이 상한은 현재 입력에만 해당한다. "
              "속성이 모두 1인 구간까지 허용하는 일반 입력에서는 α=2의 양수 비용을 보장할 수 없다.", "",
              "### 결과 해석", "",
              f"기존 결합은 {base['combined']['unique_route_count']}종 중 한 경로가 {base['combined']['modal_route_days']}일을 차지한다. "
              "희소화는 기존의 양의 선호 의미를 유지하고, 중심화는 음의 선호를 도입한다. "
              "실제 네트워크에서 먼저 비교할 후보로는 2개·3개 연결 희소화를 권한다. 다양성만으로 품질을 판정하지 않는다.", "",
              ("**모든 평균 우회가 0m인 것은 합성 격자의 구조에 의존한다.** 이번에 선택된 경로들은 구간이 달라도 "
               "모두 같은 최단 길이를 갖는다. 따라서 α를 키워도 이들 사이의 순위는 바뀌지 않는다. "
               if all(abs(r['max_detour_m']) < 1e-7 for r in summary['experiments'].values())
               else "우회 거리는 표에 제시했다. 같은 길이의 대체 경로에서는 α를 키워도 선호 순서가 바뀌지 않는다. ") +
              "길이가 같은 경로 P의 비용은 `1.6 × 공통길이 − α × Σ(length × luck)`이어서 양의 α는 선호 순서를 그대로 둔다. "
              "실제 도로의 비슷하지만 길이가 다른 후보에서는 우회 거리와 순위가 달라질 수 있으므로 재실험이 필요하다.", "",
              "## 일별 결과 및 생성 경로", "",
              f"{p['days']}개 결합 경로 GeoJSON은 combined_routes/에 저장했다. "
              "사주·점성술 단독과 각 실험의 모든 일별 구간 목록·노드·비용은 daily_results.json에 있다.", "",
              "| 날짜 | 사주 경로 | 점성술 경로 | 결합 경로 파일 | 단독 경로 분기 |", "|---|---|---|---|---|"]
    for d in daily:
        b = d["baseline"]
        lines.append(f"| {d['date']} | `{b['saju']['route_id']}` | `{b['astrology']['route_id']}` | "
                     f"[{b['combined']['route_id']}](combined_routes/{d['date']}.geojson) | {'예' if d['saju_astrology_diverged'] else '아니오'} |")
    lines += ["", "## 재현 및 파일", "", "```bash",
              f".venv/bin/python analysis/route_sensitivity.py --start {p['start_date']} --days {p['days']}", "```", "",
              "- [summary.json](summary.json): 전체 통계, 실험 행렬·계수, 백엔드 버전, 입력 SHA-256.",
              f"- [daily_results.json](daily_results.json): {p['days']}일 × 모든 시나리오의 실제 가중치와 경로·비용.",
              "- [readings.json](readings.json): 매일 계산한 원자료와 리딩.",
              "- [Williamsburg 전환 범위](williamsburg_migration_scope.md): 실제 보행망·속성 자료로 전환할 작업."]
    return "\n".join(lines) + "\n"


def run(start, days, out_dir):
    if days < 1:
        raise ValueError("days must be positive")
    segments_path = ROOT / "data/processed/street_segments.geojson"
    profile_path = ROOT / "engine/daily_reading.json"
    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    birth, birth_time = date.fromisoformat(saved["birth"]), saved["birth_time"]
    fresh = engine.combine(birth, date.fromisoformat(saved["date"]), birth_time)
    if fresh != saved or {k: v["backend"] for k, v in fresh["raw"].items()} != {"saju": "lunar_python", "astrology": "astronomy_engine"}:
        raise RuntimeError("Use matching precise backends; saved reading replay must match exactly")
    protected = [*sorted((ROOT / "config").glob("*")), *sorted((ROOT / "engine").glob("*.py")),
                 profile_path, segments_path, ROOT / "grasshopper/lucky_route_ghpython.py",
                 ROOT / "outputs/lucky_route.geojson", ROOT / "outputs/fastest_route.geojson",
                 ROOT / "outputs/design_space.csv"]
    before = {str(p.relative_to(ROOT)): sha256(p) for p in protected if p.is_file()}
    segments = router.load_segments(str(segments_path))
    if len({s["id"] for s in segments}) != len(segments):
        raise ValueError("Segment IDs must be unique")
    origin, destination = [-74.0020, 40.7280], [-73.9948, 40.7352]
    graph = router.build_graph(segments, lambda s: s["length"])
    a, b = router.nearest_node(graph, origin), router.nearest_node(graph, destination)
    fastest = route(segments, a, b)
    matrix = read_matrix(ROOT / "config/quality_street_matrix.csv")
    matrices = {name: sparse_matrix(matrix, v["top_k"]) if v["top_k"] else matrix for name, v in VARIANTS.items()}
    readings, daily = [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        reading = engine.combine(birth, day, birth_time)
        readings.append(reading)
        weights = {name: engine.street_weights(reading[name]["quality"]) for name in ("saju", "astrology", "combined")}
        base = {name: route(segments, a, b, w) for name, w in weights.items()}
        experiment_routes, experiment_weights = {}, {}
        for name, v in VARIANTS.items():
            w = weights_from_matrix(reading["combined"]["quality"], matrices[name])
            if name == "baseline" and w != weights["combined"]:
                raise AssertionError("Experimental baseline does not match production projection")
            if v["center"]:
                w = center_weights(w)
            experiment_weights[name] = w
            experiment_routes[name] = route(segments, a, b, w, v["alpha"])
        if experiment_routes["baseline"] != base["combined"]:
            raise AssertionError("Experimental baseline route differs")
        for r in [*base.values(), *experiment_routes.values()]:
            r["detour_m"] = r["length_m"] - fastest["length_m"]
        daily.append({"date": day.isoformat(), "weights": weights, "baseline": base,
                      "saju_astrology_diverged": base["saju"]["segment_ids"] != base["astrology"]["segment_ids"],
                      "saju_astrology_overlap": overlap(base["saju"]["segment_indices"], base["astrology"]["segment_indices"], segments),
                      "experimental_weights": experiment_weights, "experiments": experiment_routes})
    baseline_summary = {name: summarize_routes([d["baseline"][name] for d in daily], fastest["length_m"])
                        for name in ("saju", "astrology", "combined")}
    divergent_dates = [d["date"] for d in daily if d["saju_astrology_diverged"]]
    baseline_summary.update({"saju_astrology_divergence_days": len(divergent_dates),
                             "saju_astrology_divergence_dates": divergent_dates})
    max_luck = max(d["baseline"]["combined"]["max_edge_luck"] for d in daily)
    summary = {"inputs": {"start_date": start.isoformat(), "end_date": daily[-1]["date"], "days": days,
                           "birth": saved["birth"], "birth_time": birth_time, "replay_date": saved["date"], "origin": origin, "destination": destination,
                           "segment_count": len(segments), "data_kind": "synthetic_grid",
                           "python": sys.version.split()[0], "versions": {p: importlib.metadata.version(p) for p in ("lunar_python", "astronomy-engine")},
                           "sha256": before, "analysis_script_sha256": sha256(Path(__file__))},
               "definitions": {"std_ddof": 0, "route_identity": "ordered segment_id sequence", "detour": "route length minus shortest physical length; equal weight per day"},
               "fastest": fastest, "baseline": baseline_summary,
               "weight_statistics": {name: vector_stats([d["weights"][name] for d in daily]) for name in ("saju", "astrology", "combined")},
               "experiments": {name: summarize_routes([d["experiments"][name] for d in daily], fastest["length_m"]) for name in VARIANTS},
               "experimental_parameters": VARIANTS, "experimental_matrices": matrices,
               "baseline_max_luck": max_luck, "positive_cost_alpha_bound": router.LUCK_BIAS / max_luck}
    for relative, expected in before.items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"Production input changed during analysis: {relative}")
    for d in daily:
        write_json(out_dir / "combined_routes" / f"{d['date']}.geojson",
                   geojson_route(segments, d["baseline"]["combined"], d["weights"]["combined"], d["date"]))
    for name, value in [("readings.json", readings), ("daily_results.json", daily), ("summary.json", summary)]:
        write_json(out_dir / name, value)
    (out_dir / "report.md").write_text(markdown_report(summary, daily, matrices), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    result = run(args.start, args.days, args.out_dir or ROOT / "outputs" / f"sensitivity_{args.start}_{args.days}d")
    print(json.dumps({"baseline": result["baseline"], "weight_statistics": result["weight_statistics"]["combined"],
                      "experiments": result["experiments"]}, ensure_ascii=False, indent=2))
