"""점성술 계산 엔진 — 해석 없이 구조화된 원자료(raw signals)만 산출한다.

출력은 오직:
  - natal_positions / transit_positions: 9행성의 황경과 별자리
  - aspects: 트랜짓 행성 × 출생 행성의 각(conjunction/sextile/square/trine/opposition),
             오브(orb)와 그로부터 계산한 strength(0~1)
  - signals: 활성 원소(트랜짓 태양·달 별자리의 원소), 달 위상

해석(Event/Quality 변환)은 combine_reading.py 가 config/astrology_rules.csv 로 수행한다.

계산 백엔드:
  - astronomy_engine 설치 시(레포 .venv): 실제 지구중심 황경 기반 정밀 계산
  - 미설치 시: 태양궁 날짜 테이블 + 삭망월 근사 (행성 위치·애스펙트 없음)

MVP 제한 선언:
  하우스는 출생 시각·장소가 필요하므로 초기 버전에서 제외한다.
  트랜짓 각도는 정오(UTC 12:00) 기준 하루 1회 계산한다.
"""

import argparse
import json
from datetime import date

try:
    import astronomy
    _HAS_ASTRO = True
except ImportError:
    _HAS_ASTRO = False

SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra",
         "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"]
SIGN_ELEMENTS = ["fire", "earth", "air", "water"] * 3  # aries부터 순환

PLANETS = ["sun", "moon", "mercury", "venus", "mars",
           "jupiter", "saturn", "uranus", "neptune"]

# (각도, 최대 오브, 기본 강도 계수)
ASPECTS = {
    "conjunction": (0, 6.0, 1.00),
    "sextile": (60, 4.0, 0.60),
    "square": (90, 5.0, 0.70),
    "trine": (120, 5.0, 0.90),
    "opposition": (180, 6.0, 0.80),
}

# 폴백용 태양궁 경계 (월, 일)
SIGN_BOUNDS = [
    ((1, 20), "aquarius"), ((2, 19), "pisces"), ((3, 21), "aries"),
    ((4, 20), "taurus"), ((5, 21), "gemini"), ((6, 21), "cancer"),
    ((7, 23), "leo"), ((8, 23), "virgo"), ((9, 23), "libra"),
    ((10, 23), "scorpio"), ((11, 22), "sagittarius"), ((12, 22), "capricorn"),
]
SYNODIC_MONTH = 29.530588
NEW_MOON_EPOCH = date(2000, 1, 6)
PHASE_NAMES = ["new", "waxing_crescent", "first_quarter", "waxing_gibbous",
               "full", "waning_gibbous", "last_quarter", "waning_crescent"]


def _sign_of(lon: float) -> str:
    return SIGNS[int(lon // 30) % 12]


def _element_of_sign(sign: str) -> str:
    return SIGN_ELEMENTS[SIGNS.index(sign)]


# ── 정밀 백엔드 ───────────────────────────────────────────────────────
def _noon(d: date):
    return astronomy.Time.Make(d.year, d.month, d.day, 12, 0, 0)


def _positions(d: date) -> dict:
    t = _noon(d)
    out = {}
    for name in PLANETS:
        body = getattr(astronomy.Body, name.capitalize())
        lon = astronomy.Ecliptic(astronomy.GeoVector(body, t, True)).elon
        out[name] = {"lon": round(lon, 2), "sign": _sign_of(lon)}
    return out


def _angular_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def find_aspects(transit: dict, natal: dict) -> list:
    found = []
    for tp, tpos in transit.items():
        for np_, npos in natal.items():
            sep = _angular_distance(tpos["lon"], npos["lon"])
            for name, (angle, max_orb, factor) in ASPECTS.items():
                orb = abs(sep - angle)
                if orb <= max_orb:
                    found.append({
                        "transit": tp, "natal": np_, "aspect": name,
                        "orb": round(orb, 2),
                        "strength": round(factor * (1 - orb / max_orb), 3),
                    })
    return sorted(found, key=lambda a: -a["strength"])


def _moon_phase_precise(d: date):
    t = _noon(d)
    angle = astronomy.MoonPhase(t)  # 0=삭, 180=망
    frac = angle / 360.0
    fullness = astronomy.Illumination(astronomy.Body.Moon, t).phase_fraction
    return {"angle_deg": round(angle, 1),
            "name": PHASE_NAMES[int(frac * 8 + 0.5) % 8],
            "fullness": round(fullness, 3)}


# ── 폴백 백엔드 (stdlib 근사) ─────────────────────────────────────────
def _sun_sign_table(d: date) -> str:
    sign = "capricorn"
    for (m, dd), s in SIGN_BOUNDS:
        if (d.month, d.day) >= (m, dd):
            sign = s
    return sign


def _moon_phase_approx(d: date):
    age = (d - NEW_MOON_EPOCH).days % SYNODIC_MONTH
    frac = age / SYNODIC_MONTH
    return {"angle_deg": round(frac * 360, 1),
            "name": PHASE_NAMES[int(frac * 8 + 0.5) % 8],
            "fullness": round(1.0 - abs(frac - 0.5) * 2, 3)}


# ── 공통 진입점 ──────────────────────────────────────────────────────
def compute_astrology(birth: date, today: date) -> dict:
    if _HAS_ASTRO:
        natal = _positions(birth)
        transit = _positions(today)
        aspects = find_aspects(transit, natal)
        moon = _moon_phase_precise(today)
        active_elements = sorted({
            _element_of_sign(transit["sun"]["sign"]),
            _element_of_sign(transit["moon"]["sign"]),
        })
    else:
        sun_sign = _sun_sign_table(today)
        natal = {"sun": {"lon": None, "sign": _sun_sign_table(birth)}}
        transit = {"sun": {"lon": None, "sign": sun_sign}}
        aspects = []
        moon = _moon_phase_approx(today)
        active_elements = [_element_of_sign(sun_sign)]

    return {
        "date": today.isoformat(),
        "birth": birth.isoformat(),
        "backend": "astronomy_engine" if _HAS_ASTRO else "builtin_approx",
        "natal_positions": natal,
        "transit_positions": transit,
        "aspects": aspects,
        "signals": {
            "active_elements": active_elements,
            "moon_phase": moon,
            "natal_sun_sign": natal["sun"]["sign"],
            "transit_sun_sign": transit["sun"]["sign"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="점성술 원자료 계산 (해석 없음)")
    parser.add_argument("--birth", required=True, help="YYYY-MM-DD")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    birth = date.fromisoformat(args.birth)
    today = date.fromisoformat(args.date) if args.date else date.today()
    print(json.dumps(compute_astrology(birth, today), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
