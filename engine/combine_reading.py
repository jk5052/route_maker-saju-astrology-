"""해석 엔진 — 계산된 원자료를 명시적 규칙표에 통과시켜 오늘의 리딩을 만든다.

원칙: 계산 결과는 라이브러리가 만들고(saju_engine, astrology_engine),
      해석 규칙은 CSV로 명시적으로 관리하고(config/*_rules.csv),
      LLM은 완성된 결과를 설명만 한다(llm_payload).

흐름:
  raw_saju ──× config/saju_rules.csv ──────┐  event(3)·quality(6) + evidence
                                            ├─ combined (단순 평균, 출처 보존)
  raw_astrology ─× config/astrology_rules.csv┘
                                            │
  combined.quality ×config/quality_street_matrix.csv → 거리 품질 가중치(라우터용)
                                            │
                              daily_reading.json (+ 문장 템플릿, llm_payload)

규칙 점수 = weight × strength
  - 사주 신호: strength = 1.0 (발생 여부만)
  - 애스펙트: strength = 각 계수 × (1 − orb/max_orb), 트랜짓 행성 1.0배·출생 행성 0.5배
누적 점수는 1−e^(−x) 포화 곡선으로 0~1 정규화 (신호가 많아도 포화되지 않고
순서가 보존됨), 출처(saju/astrology)별로 따로 보존한다.

사용:  python engine/combine_reading.py --birth 1994-02-02 [--birth-time HH:MM] [--date YYYY-MM-DD]
"""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

from saju_engine import compute_saju
from astrology_engine import compute_astrology

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
OUTPUT = Path(__file__).resolve().parent / "daily_reading.json"

EVENTS = ["encounter", "opportunity", "discovery"]
QUALITIES = ["activation", "receptivity", "clarity",
             "expansion", "grounding", "flow"]

NATAL_PLANET_FACTOR = 0.5   # 애스펙트에서 출생 행성 규칙의 상대 기여
MIN_ASPECT_STRENGTH = 0.35  # 이보다 약한 애스펙트는 무시
MAX_ASPECTS = 6             # 강한 순으로 상위 N개만 해석
TOP_QUALITIES = 2
MAX_EVIDENCE = 8

EVENT_EN = {"encounter": "Encounter", "opportunity": "Opportunity",
            "discovery": "Discovery"}
QUALITY_EN = {"activation": "Activation", "receptivity": "Receptivity",
              "clarity": "Clarity", "expansion": "Expansion",
              "grounding": "Grounding", "flow": "Flow"}
ATTENTION = {
    "encounter": "conversations and chance companions you meet along the way",
    "opportunity": "practical offers and exchanges passing in front of you",
    "discovery": "new information found on unfamiliar streets and places",
}

# 한글 신호 키(사주 엔진/규칙표 공용) → 영어 표기
STEM_EN = {"갑": "Jia", "을": "Yi", "병": "Bing", "정": "Ding", "무": "Wu",
           "기": "Ji", "경": "Geng", "신": "Xin", "임": "Ren", "계": "Gui"}
BRANCH_EN = {"자": "Zi", "축": "Chou", "인": "Yin", "묘": "Mao", "진": "Chen",
             "사": "Si", "오": "Wu", "미": "Wei", "신": "Shen", "유": "You",
             "술": "Xu", "해": "Hai"}
TEN_GOD_EN = {"비견": "Friend (Bijian)", "겁재": "Rob Wealth (Jiecai)",
              "식신": "Eating God (Shishen)", "상관": "Hurting Officer (Shangguan)",
              "정재": "Direct Wealth (Zhengcai)", "편재": "Indirect Wealth (Piancai)",
              "정관": "Direct Officer (Zhengguan)", "편관": "Seven Killings (Piangan)",
              "정인": "Direct Resource (Zhengyin)", "편인": "Indirect Resource (Pianyin)"}


# ── 규칙표 로드/적용 ─────────────────────────────────────────────────
def load_rules(path: Path) -> dict:
    """CSV → {(signal_type, signal): [row, ...]} (한 신호에 여러 규칙 허용)."""
    index = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            weight_col = "weight" if "weight" in row else "base_weight"
            row["weight"] = float(row[weight_col])
            index.setdefault((row["signal_type"], row["signal"]), []).append(row)
    return index


class Accumulator:
    def __init__(self, source: str):
        self.source = source
        self.event = {e: 0.0 for e in EVENTS}
        self.quality = {q: 0.0 for q in QUALITIES}
        self.evidence = []

    def fire(self, rules: dict, signal_type: str, signal: str,
             strength: float, detail: str):
        for rule in rules.get((signal_type, signal), []):
            score = rule["weight"] * strength
            self.event[rule["event"]] += score
            self.quality[rule["quality"]] += score
            self.evidence.append({
                "source": self.source, "signal_type": signal_type,
                "signal": signal, "detail": detail,
                "event": rule["event"], "quality": rule["quality"],
                "score": round(score, 3),
                "explanation": rule["explanation"],
            })

    def result(self) -> dict:
        saturate = lambda d: {k: round(1 - math.exp(-v), 3) for k, v in d.items()}
        return {"event": saturate(self.event), "quality": saturate(self.quality)}


def interpret_saju(raw: dict, rules: dict) -> Accumulator:
    acc = Accumulator("saju")
    sig = raw["signals"]

    today_stem = raw["today"]["pillar"]["stem"]
    day_master = raw["natal"]["day_master"]["stem"]
    acc.fire(rules, "ten_god", sig["daily_ten_god"], 1.0,
             f"today's stem ({STEM_EN.get(today_stem, today_stem)}) is "
             f"{TEN_GOD_EN.get(sig['daily_ten_god'], sig['daily_ten_god'])} relative to "
             f"the day master ({STEM_EN.get(day_master, day_master)})")
    for el in sig["active_elements"]:
        acc.fire(rules, "element", el, 1.0, f"{el} is active in today's pillar")
    for it in sig["interactions"]:
        verb = "combination (He)" if it["type"] == "combination" else "clash (Chong)"
        acc.fire(rules, "interaction", it["type"], 1.0,
                 f"today's branch ({BRANCH_EN.get(it['today_branch'], it['today_branch'])}) "
                 f"forms a {verb} with the natal {it['natal_pillar']} pillar branch "
                 f"({BRANCH_EN.get(it['natal_branch'], it['natal_branch'])})")
    for el in sig["deficient_elements_active"]:
        acc.fire(rules, "natal_balance", "deficient_element_active", 1.0,
                 f"{el}, lacking in the natal chart, arrives today")
    for el in sig["excess_elements_active"]:
        acc.fire(rules, "natal_balance", "excess_element_active", 1.0,
                 f"{el}, already abundant in the natal chart, is emphasized further today")
    return acc


def interpret_astrology(raw: dict, rules: dict) -> Accumulator:
    acc = Accumulator("astrology")

    aspects = [a for a in raw["aspects"] if a["strength"] >= MIN_ASPECT_STRENGTH]
    for a in aspects[:MAX_ASPECTS]:
        detail = (f"transit {a['transit']} {a['aspect']} natal {a['natal']} "
                  f"(orb {a['orb']}°, strength {a['strength']})")
        acc.fire(rules, "planet", a["transit"], a["strength"], detail)
        acc.fire(rules, "planet", a["natal"],
                 a["strength"] * NATAL_PLANET_FACTOR, detail)
    for el in raw["signals"]["active_elements"]:
        acc.fire(rules, "element", el, 1.0,
                 f"transit sun/moon sign element: {el}")
    return acc


# ── 결합/출력 ────────────────────────────────────────────────────────
def combine_scores(a: dict, b: dict) -> dict:
    return {section: {k: round((a[section][k] + b[section][k]) / 2, 3)
                      for k in a[section]}
            for section in ("event", "quality")}


def street_weights(quality: dict) -> dict:
    """일일 성질(6) × quality_street_matrix(6×8) → 라우터용 거리 품질 가중치."""
    with open(CONFIG / "quality_street_matrix.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        cols = next(reader)[1:]
        out = {c: 0.0 for c in cols}
        for row in reader:
            q, values = row[0], [float(v) for v in row[1:]]
            for c, v in zip(cols, values):
                out[c] += quality.get(q, 0.0) * v
    total = sum(out.values()) or 1.0
    return {c: round(v / total, 4) for c, v in out.items()}


def build_sentence(dominant_event: str, top_qualities: list) -> str:
    q1, q2 = (QUALITY_EN[q] for q in top_qualities[:2])
    return (f"Today's dominant luck type is '{EVENT_EN[dominant_event]}'. "
            f"{q1} and {q2} are the qualities emphasized today. "
            f"Pay attention to {ATTENTION[dominant_event]}.")


def build_llm_payload(dominant_event, top_qualities, evidence) -> dict:
    return {
        "dominant_event": dominant_event,
        "top_qualities": top_qualities,
        "evidence": [f"[{e['source']}] {e['detail']} → {e['explanation']}"
                     for e in evidence],
        "instructions": (
            "Do not alter the computed results or add new astrology/Saju signals. "
            "Explain today's luck type and qualities in plain English, "
            "in three sentences or fewer. Do not make definitive predictions; "
            "frame everything as possibilities to notice and gentle suggestions."
        ),
    }


def combine(birth: date, today: date, birth_time: str | None = None) -> dict:
    raw_saju = compute_saju(birth, today, birth_time)
    raw_astro = compute_astrology(birth, today)

    saju_acc = interpret_saju(raw_saju, load_rules(CONFIG / "saju_rules.csv"))
    astro_acc = interpret_astrology(raw_astro,
                                    load_rules(CONFIG / "astrology_rules.csv"))

    saju_res, astro_res = saju_acc.result(), astro_acc.result()
    combined = combine_scores(saju_res, astro_res)

    dominant_event = max(combined["event"], key=combined["event"].get)
    top_qualities = sorted(combined["quality"],
                           key=combined["quality"].get, reverse=True)[:TOP_QUALITIES]

    evidence = sorted(saju_acc.evidence + astro_acc.evidence,
                      key=lambda e: -e["score"])[:MAX_EVIDENCE]

    return {
        "date": today.isoformat(),
        "birth": birth.isoformat(),
        "birth_time": birth_time,
        "saju": saju_res,
        "astrology": astro_res,
        "combined": combined,
        "dominant_event": dominant_event,
        "top_qualities": top_qualities,
        "evidence": evidence,
        "sentence": build_sentence(dominant_event, top_qualities),
        "llm_payload": build_llm_payload(dominant_event, top_qualities, evidence),
        "quality_weights": street_weights(combined["quality"]),  # 라우터용
        "raw": {"saju": raw_saju, "astrology": raw_astro},
    }


def main():
    parser = argparse.ArgumentParser(description="오늘의 리딩 생성 (규칙 기반 해석)")
    parser.add_argument("--birth", required=True, help="YYYY-MM-DD")
    parser.add_argument("--birth-time", default=None, help="HH:MM (있으면 시주 포함)")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--out", default=str(OUTPUT), help="출력 경로")
    args = parser.parse_args()

    birth = date.fromisoformat(args.birth)
    today = date.fromisoformat(args.date) if args.date else date.today()

    reading = combine(birth, today, args.birth_time)
    Path(args.out).write_text(json.dumps(reading, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"saved: {args.out}")
    print(json.dumps({k: reading[k] for k in
                      ("combined", "dominant_event", "top_qualities", "sentence")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
