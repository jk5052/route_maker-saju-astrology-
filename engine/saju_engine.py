"""사주 계산 엔진 — 해석 없이 구조화된 원자료(raw signals)만 산출한다.

이 파일은 '운세'를 만들지 않는다. 출력은 오직:
  - 원국(natal): 연·월·일·[시]주, 일간, 오행 분포, 과다/부족 오행
  - 오늘(today): 일진 간지, 활성 오행
  - 신호(signals): 십성 관계, 합·충, 원국 균형 대비 오늘 오행의 보충/증폭

해석(Event/Quality 변환)은 combine_reading.py 가 config/saju_rules.csv 로 수행한다.

계산 백엔드:
  - lunar_python 설치 시(레포 .venv): 만세력 기반 정밀 사주 (월주·시주 포함)
  - 미설치 시: 갑자일 앵커(1949-10-01, 검증됨) + 입춘 근사 연주 (월주·시주 없음)

MVP 해석 체계 선언:
  일간·오행·십성·일진과 주요 합·충만 사용한다.
  용신, 격국, 신살, 대운·세운의 세부 판단은 초기 버전에서 제외한다.
"""

import argparse
import json
from datetime import date

try:
    from lunar_python import Solar
    _HAS_LUNAR = True
except ImportError:
    _HAS_LUNAR = False

HANZI_STEMS = "甲乙丙丁戊己庚辛壬癸"
HANZI_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

STEMS = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
BRANCHES = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

STEM_ELEMENTS = ["wood", "wood", "fire", "fire", "earth",
                 "earth", "metal", "metal", "water", "water"]
BRANCH_ELEMENTS = ["water", "earth", "wood", "wood", "earth", "fire",
                   "fire", "earth", "metal", "metal", "earth", "water"]

ELEMENTS = ["wood", "fire", "earth", "metal", "water"]

GENERATES = {"wood": "fire", "fire": "earth", "earth": "metal",
             "metal": "water", "water": "wood"}
CONTROLS = {"wood": "earth", "earth": "water", "water": "fire",
            "fire": "metal", "metal": "wood"}

# 지지 육합 / 충 (쌍은 정렬된 튜플로 저장)
COMBINATIONS = {("자", "축"), ("인", "해"), ("묘", "술"),
                ("진", "유"), ("사", "신"), ("오", "미")}
CLASHES = {("자", "오"), ("축", "미"), ("인", "신"),
           ("묘", "유"), ("진", "술"), ("사", "해")}

ANCHOR_JIAZI = date(1949, 10, 1)   # 갑자일 (lunar_python으로 검증)
EXCESS_THRESHOLD = 3               # 원국 글자 중 3개 이상이면 과다로 표기


def _pillar_from_hanzi(gz: str) -> dict:
    si = HANZI_STEMS.index(gz[0])
    bi = HANZI_BRANCHES.index(gz[1])
    return _pillar(si, bi)


def _pillar(stem_idx: int, branch_idx: int) -> dict:
    return {
        "stem": STEMS[stem_idx],
        "branch": BRANCHES[branch_idx],
        "stem_element": STEM_ELEMENTS[stem_idx],
        "branch_element": BRANCH_ELEMENTS[branch_idx],
        "stem_polarity": "yang" if stem_idx % 2 == 0 else "yin",
    }


def day_pillar(d: date) -> dict:
    if _HAS_LUNAR:
        gz = Solar.fromYmd(d.year, d.month, d.day).getLunar().getDayInGanZhi()
        return _pillar_from_hanzi(gz)
    idx = (d - ANCHOR_JIAZI).days % 60
    return _pillar(idx % 10, idx % 12)


def _approx_year_pillar(d: date) -> dict:
    """입춘(2/4 근사) 기준 연주. 1984 = 갑자년."""
    y = d.year if (d.month, d.day) >= (2, 4) else d.year - 1
    idx = (y - 1984) % 60
    return _pillar(idx % 10, idx % 12)


def natal_chart(birth: date, birth_time: str | None) -> dict:
    """원국 계산. birth_time("HH:MM")이 있어야 시주 포함."""
    pillars = {}
    if _HAS_LUNAR:
        if birth_time:
            hh, mm = (int(v) for v in birth_time.split(":"))
            solar = Solar.fromYmdHms(birth.year, birth.month, birth.day, hh, mm, 0)
        else:
            solar = Solar.fromYmdHms(birth.year, birth.month, birth.day, 12, 0, 0)
        ec = solar.getLunar().getEightChar()
        pillars["year"] = _pillar_from_hanzi(ec.getYear())
        pillars["month"] = _pillar_from_hanzi(ec.getMonth())
        pillars["day"] = _pillar_from_hanzi(ec.getDay())
        if birth_time:
            pillars["hour"] = _pillar_from_hanzi(ec.getTime())
    else:
        pillars["year"] = _approx_year_pillar(birth)
        pillars["day"] = day_pillar(birth)

    dist = {el: 0 for el in ELEMENTS}
    for p in pillars.values():
        dist[p["stem_element"]] += 1
        dist[p["branch_element"]] += 1

    return {
        "pillars": pillars,
        "day_master": {
            "stem": pillars["day"]["stem"],
            "element": pillars["day"]["stem_element"],
            "polarity": pillars["day"]["stem_polarity"],
        },
        "element_distribution": dist,
        "excess_elements": [el for el, n in dist.items() if n >= EXCESS_THRESHOLD],
        "deficient_elements": [el for el, n in dist.items() if n == 0],
    }


def ten_god(day_master_stem: str, other_stem: str) -> str:
    """일간 대비 다른 천간의 십성."""
    di, oi = STEMS.index(day_master_stem), STEMS.index(other_stem)
    dm_el, o_el = STEM_ELEMENTS[di], STEM_ELEMENTS[oi]
    same_pol = (di % 2) == (oi % 2)
    if o_el == dm_el:
        return "비견" if same_pol else "겁재"
    if GENERATES[dm_el] == o_el:
        return "식신" if same_pol else "상관"
    if CONTROLS[dm_el] == o_el:
        return "편재" if same_pol else "정재"
    if CONTROLS[o_el] == dm_el:
        return "편관" if same_pol else "정관"
    return "편인" if same_pol else "정인"  # GENERATES[o_el] == dm_el


def branch_interactions(natal_pillars: dict, today_branch: str) -> list:
    """오늘 지지와 원국 각 지지 사이의 합·충."""
    found = []
    for name, p in natal_pillars.items():
        pair = tuple(sorted((p["branch"], today_branch)))
        if pair in COMBINATIONS:
            found.append({"type": "combination", "natal_pillar": name,
                          "natal_branch": p["branch"], "today_branch": today_branch})
        elif pair in CLASHES:
            found.append({"type": "clash", "natal_pillar": name,
                          "natal_branch": p["branch"], "today_branch": today_branch})
    return found


def compute_saju(birth: date, today: date, birth_time: str | None = None) -> dict:
    natal = natal_chart(birth, birth_time)
    tp = day_pillar(today)
    active = sorted({tp["stem_element"], tp["branch_element"]})

    return {
        "date": today.isoformat(),
        "birth": birth.isoformat(),
        "birth_time": birth_time,
        "backend": "lunar_python" if _HAS_LUNAR else "builtin_approx",
        "natal": natal,
        "today": {"pillar": tp, "active_elements": active},
        "signals": {
            "daily_ten_god": ten_god(natal["day_master"]["stem"], tp["stem"]),
            "active_elements": active,
            "interactions": branch_interactions(natal["pillars"], tp["branch"]),
            "deficient_elements_active":
                sorted(set(active) & set(natal["deficient_elements"])),
            "excess_elements_active":
                sorted(set(active) & set(natal["excess_elements"])),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="사주 원자료 계산 (해석 없음)")
    parser.add_argument("--birth", required=True, help="YYYY-MM-DD")
    parser.add_argument("--birth-time", default=None, help="HH:MM (있으면 시주 포함)")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    birth = date.fromisoformat(args.birth)
    today = date.fromisoformat(args.date) if args.date else date.today()
    print(json.dumps(compute_saju(birth, today, args.birth_time),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
