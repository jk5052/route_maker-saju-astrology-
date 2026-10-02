"""Replay one saved reading with Saju, astrology, and their existing 50:50 blend.

Uses saved raw signals so an unavailable astronomy/calendar backend cannot change
the comparison. Writes three GeoJSON routes and a JSON/Markdown comparison.
"""

import argparse
import csv
import hashlib
import itertools
import json
import sys
from pathlib import Path

import combine_reading as reading_engine

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grasshopper"))
import lucky_route_ghpython as router


def project(quality, matrix):
    columns = list(next(iter(matrix.values())))
    return {
        street: sum(quality[q] * matrix[q][street] for q in matrix)
        for street in columns
    }


def decompose(saju, astrology, combined, matrix, routed_weights):
    """Attribute linear mass before normalization; isolate rounding as residual.

    S and A are the engine's separately saturated, three-decimal quality scores.
    The ideal case does not round their average. The production case does, and
    subsequently rounds normalized street weights to four decimal places.
    No rounding residual is silently assigned to either symbolic system.
    """
    s = {k: 0.5 * v for k, v in project(saju, matrix).items()}
    a = {k: 0.5 * v for k, v in project(astrology, matrix).items()}
    actual = project(combined, matrix)
    ideal_total = sum(s.values()) + sum(a.values())
    production_total = sum(actual.values())
    if min(ideal_total, production_total) <= 0:
        raise ValueError("Cannot attribute a zero preference vector")
    rows = {}
    for street in s:
        ideal_s = s[street] / ideal_total
        ideal_a = a[street] / ideal_total
        production_s = s[street] / production_total
        production_a = a[street] / production_total
        intermediate_residual = (
            actual[street] - s[street] - a[street]
        ) / production_total
        final_residual = routed_weights[street] - actual[street] / production_total
        rows[street] = {
            "ideal_saju": ideal_s,
            "ideal_astrology": ideal_a,
            "ideal_combined": ideal_s + ideal_a,
            "saju_fraction_within_attribute": s[street] / (s[street] + a[street])
            if s[street] + a[street] else None,
            "production_saju": production_s,
            "production_astrology": production_a,
            "intermediate_rounding_residual": intermediate_residual,
            "final_rounding_residual": final_residual,
            "routed_combined": routed_weights[street],
        }
    return {
        "unscaled_saju_mass": 2 * sum(s.values()),
        "unscaled_astrology_mass": 2 * sum(a.values()),
        "ideal_denominator": ideal_total,
        "production_denominator": production_total,
        "ideal_saju_share": sum(s.values()) / ideal_total,
        "ideal_astrology_share": sum(a.values()) / ideal_total,
        "production_saju_share": sum(s.values()) / production_total,
        "production_astrology_share": sum(a.values()) / production_total,
        "intermediate_rounding_residual_total": sum(
            row["intermediate_rounding_residual"] for row in rows.values()
        ),
        "final_rounding_residual_total": sum(
            row["final_rounding_residual"] for row in rows.values()
        ),
        "attributes": rows,
    }


def overlap(left, right, segments):
    """Undirected segment-set overlap, weighted by stored length_m, not count."""
    left, right = set(left), set(right)
    length = lambda indices: sum(segments[i]["length"] for i in sorted(indices))
    shared = length(left & right)
    union = length(left | right)
    left_length, right_length = length(left), length(right)
    return {
        "shared_segment_count": len(left & right),
        "shared_length_m": shared,
        "union_length_m": union,
        "length_jaccard": shared / union if union else None,
        "fraction_of_left": shared / left_length if left_length else None,
        "fraction_of_right": shared / right_length if right_length else None,
    }


def find_route(segments, weights, origin, destination):
    graph = router.build_graph(
        segments, lambda s: s["length"] * (router.LUCK_BIAS - router.luck_score(s, weights))
    )
    start = router.nearest_node(graph, origin)
    goal = router.nearest_node(graph, destination)
    nodes, indices = router.dijkstra(graph, start, goal)
    if not nodes or not indices:
        raise ValueError("Comparison requires a nonempty connected walking route")
    return nodes, indices


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def markdown_report(result):
    inputs, cases, attribution = result["inputs"], result["scenarios"], result["attribution"]
    names = {"saju": "사주만 C=S", "astrology": "점성술만 C=A", "combined": "결합 C=0.5S+0.5A"}
    lines = [
        f"# {inputs['date']} 체계별 경로 비교",
        "",
        f"입력: 생년월일 {inputs['birth']}, 시각 {inputs['birth_time']}. "
        f"출발 {inputs['origin']}, 도착 {inputs['destination']}.",
        f"거리 데이터: `{inputs['segments_path']}` ({inputs['segment_count']}개 구간).",
        "현재 저장소 README가 합성 샘플 격자로 명시한 입력을 사용했다. 실제 Williamsburg 거리 데이터에 대한 결과로 일반화하지 않는다.",
        "",
        "## 실행 조건",
        "",
        "저장된 raw 신호에서 사주·점성술 점수를 재현하고 기존 리딩과 일치하는지 확인했다. "
        "S와 A는 각각 포화 변환 후 소수점 3자리로 저장된 quality 벡터다. "
        "결합 경로는 기존 엔진처럼 평균을 소수점 3자리로 반올림하고 거리 가중치를 소수점 4자리로 반올림한다. "
        "세 경우 모두 같은 그래프·끝점·비용 함수·탐색 알고리즘을 사용한다.",
        "",
        "## 실제 라우터에 전달한 거리 가중치 w[s]",
        "",
        "| 거리 속성 | 사주만 | 점성술만 | 결합 |",
        "|---|---:|---:|---:|",
    ]
    for street in cases["combined"]["weights"]:
        lines.append(f"| {street} | " + " | ".join(
            f"{cases[key]['weights'][street]:.4f}" for key in names
        ) + " |")
    lines += ["", "독립 반올림 때문에 열의 합이 정확히 1이 아닐 수 있다. 사후 재정규화는 하지 않았다.", "",
              "## 생성 경로", "", "| 경우 | 길이(m) | 구간 수 | 파일 |", "|---|---:|---:|---|"]
    for key, label in names.items():
        case = cases[key]
        lines.append(f"| {label} | {case['length_m']:.1f} | {len(case['segment_ids'])} | [{case['route_file']}]({case['route_file']}) |")
    lines += ["", "## 경로 겹침", "",
              "길이 Jaccard = 공통 구간 길이 / 두 경로 구간 합집합 길이. "
              "방향별 포함률도 함께 제시한다. 구간 개수 비율이나 경로를 둘러싼 면적 비율이 아니다.", "",
              "| 왼쪽 / 오른쪽 | 공통 길이(m) | 길이 Jaccard | 왼쪽 포함률 | 오른쪽 포함률 |",
              "|---|---:|---:|---:|---:|"]
    for pair in result["overlaps"]:
        lines.append(f"| {names[pair['left']]} / {names[pair['right']]} | {pair['shared_length_m']:.1f} | "
                     f"{pair['length_jaccard']:.2%} | {pair['fraction_of_left']:.2%} | {pair['fraction_of_right']:.2%} |")
    identical = len({tuple(case["segment_ids"]) for case in cases.values()}) == 1
    lines += ["", f"세 경로의 순서 있는 구간 목록까지 동일: **{identical}**."]
    if identical:
        lines += ["", "세 경우의 공통 구간 ID: `" + ", ".join(map(str, cases["combined"]["segment_ids"])) + "`.",
                  "", "이 사례에서는 가중치가 달라도 선택 경로가 바뀌지 않았다. "
                  "점성술 단독과의 일치만으로 점성술이 경로 선택을 지배한다고 판단할 수 없다. "
                  "사주 단독도 같은 경로이며, 가중치 총량의 몫은 경로 선택의 인과 기여율과 구별해야 한다."]
    lines += ["", "거리 가중치의 L1 거리(각 속성 가중치 차이의 절댓값 합):", ""]
    for pair in result["overlaps"]:
        lines.append(f"- {names[pair['left']]} / {names[pair['right']]}: {pair['weight_l1_distance']:.6f}")
    lines += ["", "## 체계별 거리 가중치 기여: 중간 반올림 없는 결합식", "",
              "```text", "uS[s] = 0.5 × Σq S[q] M[q,s]", "uA[s] = 0.5 × Σq A[q] M[q,s]",
              "D = Σs (uS[s] + uA[s])", "사주 몫 = uS[s] / D", "점성술 몫 = uA[s] / D", "```", "",
              "각 체계를 따로 정규화한 wS와 wA를 50:50으로 평균한 것이 아니다. "
              "공통 분모로 나누어야 두 몫이 합쳐져 결합 가중치가 된다.", "",
              f"사주 투영 총량: **{attribution['unscaled_saju_mass']:.6f}**, "
              f"점성술 투영 총량: **{attribution['unscaled_astrology_mass']:.6f}**.", "",
              "| 거리 속성 | 사주 몫 | 점성술 몫 | 합계 | 속성 내 사주 비율 |",
              "|---|---:|---:|---:|---:|"]
    for street, row in attribution["attributes"].items():
        lines.append(f"| {street} | {row['ideal_saju']:.6f} | {row['ideal_astrology']:.6f} | "
                     f"{row['ideal_combined']:.6f} | {row['saju_fraction_within_attribute']:.2%} |")
    lines += [f"| 총합 | {attribution['ideal_saju_share']:.6f} | {attribution['ideal_astrology_share']:.6f} | 1.000000 | — |", "",
              f"따라서 최종 가중치 총량의 몫은 **사주 {attribution['ideal_saju_share']:.4%} / "
              f"점성술 {attribution['ideal_astrology_share']:.4%}**다. "
              "입력 계수 0.5:0.5가 같은 최종 몫을 보장하지 않는 이유는 체계별 점수 총량과 행렬 투영 총량이 다르기 때문이다.", "",
              "## 실제 엔진의 반올림까지 분리한 기여", "",
              "생산 계산의 공통 분모 Dprod로 uS·uA를 나눈 뒤, 평균 점수의 3자리 반올림 잔차와 "
              "최종 가중치의 4자리 반올림 잔차를 별도로 남긴다. 잔차를 어느 체계에도 임의로 배분하지 않는다.", "",
              f"D = {attribution['ideal_denominator']:.6f}; Dprod = {attribution['production_denominator']:.6f}.", "",
              "| 거리 속성 | 사주 몫 | 점성술 몫 | 중간 반올림 잔차 | 최종 반올림 잔차 | 실제 w[s] |",
              "|---|---:|---:|---:|---:|---:|"]
    for street, row in attribution["attributes"].items():
        lines.append(f"| {street} | {row['production_saju']:.8f} | {row['production_astrology']:.8f} | "
                     f"{row['intermediate_rounding_residual']:+.8f} | {row['final_rounding_residual']:+.8f} | {row['routed_combined']:.4f} |")
    lines += ["", f"총합: 사주 {attribution['production_saju_share']:.6%}, "
              f"점성술 {attribution['production_astrology_share']:.6%}, "
              f"중간 반올림 잔차 {attribution['intermediate_rounding_residual_total']:.6%}, "
              f"최종 반올림 잔차 {attribution['final_rounding_residual_total']:.6%}.", "",
              f"평균 점수의 중간 반올림을 생략해도 기존 결합 경로와 같은 구간을 선택: "
              f"**{result['unrounded_blend_check']['same_segment_sequence']}**.", "",
              "## 재실행", "", "```bash",
              f"python3 engine/compare_reading_routes.py --date {inputs['date']} "
              f"--origin={','.join(map(str, inputs['origin']))} --dest={','.join(map(str, inputs['destination']))}",
              "```", "", "입력 파일 SHA-256과 전체 정밀도 수치는 [comparison.json](comparison.json)에 저장했다.",
              "메타데이터 출처 검토는 [design_rationale.md](../../config/design_rationale.md)를 참고한다."]
    return "\n".join(lines) + "\n"


def compare(reading_path, segments_path, requested_date, origin, destination, out_dir):
    reading_path, segments_path, out_dir = map(Path, (reading_path, segments_path, out_dir))
    saved = json.loads(reading_path.read_text(encoding="utf-8"))
    if saved["date"] != requested_date:
        raise ValueError(f"Saved reading date {saved['date']} differs from {requested_date}")
    matrix_path = reading_engine.CONFIG / "quality_street_matrix.csv"
    with matrix_path.open(newline="", encoding="utf-8") as f:
        matrix = {row["quality"]: {key: float(value) for key, value in row.items() if key != "quality"}
                  for row in csv.DictReader(f)}
    scores = {}
    for name, interpret in [("saju", reading_engine.interpret_saju), ("astrology", reading_engine.interpret_astrology)]:
        scores[name] = interpret(saved["raw"][name], reading_engine.load_rules(
            reading_engine.CONFIG / f"{name}_rules.csv")).result()
        if scores[name] != saved[name]:
            raise ValueError(f"Current {name} rules no longer reproduce the saved reading")
    scores["combined"] = reading_engine.combine_scores(scores["saju"], scores["astrology"])
    if scores["combined"] != saved["combined"]:
        raise ValueError("Combined score differs from the saved reading")
    segments = router.load_segments(str(segments_path))
    if len({segment["id"] for segment in segments}) != len(segments):
        raise ValueError("Segment IDs must be unique for overlap comparison")
    cases, indices_by_case, files = {}, {}, {}
    for name, score in scores.items():
        weights = reading_engine.street_weights(score["quality"])
        nodes, indices = find_route(segments, weights, origin, destination)
        fc = router.route_feature_collection(segments, indices, weights, name)
        filename = f"{name}_route.geojson"
        fc["properties"].update({"date": requested_date, "quality_weights": weights,
                                  "snapped_origin": list(nodes[0]), "snapped_destination": list(nodes[-1]),
                                  "reading_sha256": digest(reading_path)})
        files[filename] = fc
        indices_by_case[name] = indices
        cases[name] = {"quality": score["quality"], "weights": weights,
                       "length_m": sum(segments[i]["length"] for i in indices),
                       "segment_ids": [segments[i]["id"] for i in indices],
                       "route_file": filename,
                       "cost": sum(segments[i]["length"] * (router.LUCK_BIAS - router.luck_score(segments[i], weights)) for i in indices)}
    if cases["combined"]["weights"] != saved["quality_weights"]:
        raise ValueError("Combined street weights differ from the saved reading")
    pairs = []
    for left, right in itertools.combinations(cases, 2):
        pairs.append({"left": left, "right": right,
                      **overlap(indices_by_case[left], indices_by_case[right], segments),
                      "weight_l1_distance": sum(abs(cases[left]["weights"][s] - cases[right]["weights"][s]) for s in cases[left]["weights"])})
    attribution = decompose(scores["saju"]["quality"], scores["astrology"]["quality"],
                            scores["combined"]["quality"], matrix, cases["combined"]["weights"])
    ideal_quality = {q: (scores["saju"]["quality"][q] + scores["astrology"]["quality"][q]) / 2
                     for q in matrix}
    ideal_weights = reading_engine.street_weights(ideal_quality)
    _, ideal_indices = find_route(segments, ideal_weights, origin, destination)
    input_files = [reading_path, segments_path, matrix_path,
                   reading_engine.CONFIG / "saju_rules.csv", reading_engine.CONFIG / "astrology_rules.csv"]
    result = {
        "inputs": {"date": requested_date, "birth": saved["birth"], "birth_time": saved["birth_time"],
                   "origin": origin, "destination": destination, "segments_path": str(segments_path),
                   "segment_count": len(segments), "sha256": {str(p): digest(p) for p in input_files}},
        "scenarios": cases, "overlaps": pairs, "attribution": attribution,
        "unrounded_blend_check": {"quality": ideal_quality, "weights": ideal_weights,
                                  "segment_ids": [segments[i]["id"] for i in ideal_indices],
                                  "same_segment_sequence": ideal_indices == indices_by_case["combined"]},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in {**files, "comparison.json": result}.items():
        (out_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "comparison.md").write_text(markdown_report(result), encoding="utf-8")
    return result


def coordinate(value):
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("Expected lon,lat")
    return parts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reading", type=Path, default=ROOT / "engine/daily_reading.json")
    parser.add_argument("--segments", type=Path, default=ROOT / "data/processed/street_segments.geojson")
    parser.add_argument("--date", required=True)
    parser.add_argument("--origin", type=coordinate, required=True)
    parser.add_argument("--dest", type=coordinate, required=True)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    out = args.out_dir or ROOT / "outputs" / f"comparison_{args.date}"
    result = compare(args.reading, args.segments, args.date, args.origin, args.dest, out)
    print(f"Saved comparison to {out}")
    print(json.dumps({"overlaps": result["overlaps"],
                      "ideal_saju_share": result["attribution"]["ideal_saju_share"],
                      "ideal_astrology_share": result["attribution"]["ideal_astrology_share"]}, indent=2))


if __name__ == "__main__":
    main()
