import csv
import getpass
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


API_URL = "https://places.googleapis.com/v1/places:searchNearby"

# =============================================================================
# 실행 설정
# =============================================================================
# 이 스크립트는 v1.3 전체 수집을 다시 하지 않습니다.
# v1.3의 잔여 포화 CSV에 기록된 위치만 더 작은 타입 묶음으로 재검색한 뒤,
# 기존 장소 CSV와 Place ID 기준으로 병합합니다.
TEST_MODE = False
TEST_JOB_LIMIT = 10

REQUEST_DELAY_SECONDS = 0.15
MAX_RETRIES = 3
MAX_RESULTS = 20

INPUT_PLACES = Path(
    "places_output_v1_3/"
    "williamsburg_places_scored_v1_3_full.csv"
)
INPUT_RESIDUAL = Path(
    "places_output_v1_3/"
    "williamsburg_saturated_refine_v1_3_full.csv"
)
OUTPUT_DIR = Path("places_output_v1_4")

# 프로젝트 Williamsburg 분석 범위
MIN_LAT = 40.708
MAX_LAT = 40.722
MIN_LON = -73.970
MAX_LON = -73.950

# v1.3 잔여 포화 원은 반경 약 105m입니다.
# 1차: 같은 원에서 타입 묶음만 더 작게 나눠 검색
# 2차: 그래도 20개면 3x3, 반경 60m
# 3차: 그래도 20개면 다시 3x3, 반경 30m
FINE_OFFSET_M = 50.0
FINE_RADIUS_M = 60.0

MICRO_OFFSET_M = 24.0
MICRO_RADIUS_M = 30.0


# =============================================================================
# v1.4 보정용 검색 그룹
# =============================================================================
# 이것들은 새 지표가 아니라 API 20개 제한을 피하기 위한 수집 묶음입니다.
PATCH_GROUPS: Dict[str, Dict[str, List[str]]] = {
    "access_health_civic": {
        "access_health": [
            "medical_clinic",
            "doctor",
            "dentist",
        ],
        "access_civic_finance": [
            "bank",
            "atm",
            "post_office",
        ],
        "access_daily_services": [
            "laundry",
            "fitness_center",
            "gym",
        ],
    },
    "social_restaurants_food": {
        "social_restaurants": [
            "restaurant",
        ],
        "social_snacks_food": [
            "bakery",
            "food_court",
            "ice_cream_shop",
        ],
    },
    "access_retail_goods": {
        "access_retail_electronics": [
            "electronics_store",
            "cell_phone_store",
            "hardware_store",
            "bicycle_store",
        ],
        "access_retail_home": [
            "home_goods_store",
            "furniture_store",
            "gift_shop",
            "pet_store",
        ],
        "access_retail_clothing": [
            "clothing_store",
        ],
    },
    "access_personal_mixed": {
        "access_personal_services": [
            "beauty_salon",
            "hair_salon",
            "barber_shop",
        ],
        "access_misc_destinations": [
            "florist",
            "shopping_mall",
        ],
    },
    "social_cafes_bars": {
        "social_cafes": [
            "cafe",
            "coffee_shop",
        ],
        "social_bars": [
            "bar",
            "pub",
            "night_club",
        ],
    },
}


# =============================================================================
# 성분 루브릭: Google place type -> (social, access)
# =============================================================================
# 허용 단계: 0.0 / 0.3 / 0.5 / 0.8 / 1.0
#
# P_social:
# "낯선 사람들과 같은 공간에 머무르는 것이 이 장소의 본질인가?"
#
# P_access:
# "물건·정보·활동·서비스를 획득하는 것이 이 장소의 존재 이유인가?"
COMP: Dict[str, Tuple[float, float]] = {
    # Social 1.0
    "cafe": (1.0, 0.3),
    "coffee_shop": (1.0, 0.3),
    "bar": (1.0, 0.0),
    "pub": (1.0, 0.0),

    # Social 0.8
    "food_court": (0.8, 0.5),
    "event_venue": (0.8, 0.0),
    "live_music_venue": (0.8, 0.0),
    "night_club": (0.8, 0.0),
    "community_center": (0.8, 0.5),
    "farmers_market": (0.8, 1.0),

    # Social 0.5
    "restaurant": (0.5, 0.3),
    "bakery": (0.5, 0.5),
    "ice_cream_shop": (0.5, 0.3),
    "park": (0.5, 0.3),
    "plaza": (0.5, 0.0),
    "performing_arts_theater": (0.5, 0.5),
    "movie_theater": (0.5, 0.5),
    "market": (0.5, 1.0),
    "shopping_mall": (0.5, 0.8),

    # Social 0.3
    "library": (0.3, 1.0),
    "book_store": (0.3, 1.0),
    "art_gallery": (0.3, 0.5),
    "museum": (0.3, 0.5),
    "gym": (0.3, 0.8),
    "fitness_center": (0.3, 0.8),
    "coworking_space": (0.3, 0.8),
    "bicycle_store": (0.3, 0.8),

    # Access 1.0
    "supermarket": (0.0, 1.0),
    "grocery_store": (0.0, 1.0),
    "pharmacy": (0.0, 1.0),
    "drugstore": (0.0, 1.0),
    "medical_clinic": (0.0, 1.0),
    "doctor": (0.0, 1.0),
    "dentist": (0.0, 1.0),
    "department_store": (0.0, 1.0),

    # Access 0.8
    "convenience_store": (0.0, 0.8),
    "clothing_store": (0.0, 0.8),
    "electronics_store": (0.0, 0.8),
    "hardware_store": (0.0, 0.8),
    "home_goods_store": (0.0, 0.8),
    "pet_store": (0.0, 0.8),
    "cell_phone_store": (0.0, 0.8),
    "furniture_store": (0.0, 0.8),
    "gift_shop": (0.0, 0.8),
    "bank": (0.0, 0.8),
    "post_office": (0.0, 0.8),
    "laundry": (0.0, 0.8),
    "beauty_salon": (0.0, 0.8),
    "hair_salon": (0.0, 0.8),
    "barber_shop": (0.0, 0.8),
    "florist": (0.0, 0.8),

    # Access 0.3
    "atm": (0.0, 0.3),
}

GENERIC_TYPES: Set[str] = {
    "store",
    "food",
    "point_of_interest",
    "establishment",
    "health",
}


# =============================================================================
# 검증 및 좌표 유틸리티
# =============================================================================
def validate_configuration() -> None:
    allowed_scores = {0.0, 0.3, 0.5, 0.8, 1.0}

    for place_type, (social, access) in COMP.items():
        if social not in allowed_scores or access not in allowed_scores:
            raise ValueError(
                f"COMP[{place_type!r}]의 성분값이 허용 단계를 벗어남: "
                f"({social}, {access})"
            )

    seen_patch_types: Dict[str, str] = {}

    for source_group, subgroups in PATCH_GROUPS.items():
        if not subgroups:
            raise ValueError(f"{source_group!r}의 보정 그룹이 비어 있습니다.")

        for subgroup_name, place_types in subgroups.items():
            if not place_types:
                raise ValueError(f"{subgroup_name!r}가 비어 있습니다.")
            if len(place_types) > 50:
                raise ValueError(f"{subgroup_name!r} 타입 수가 50개를 넘습니다.")

            for place_type in place_types:
                if place_type not in COMP:
                    raise ValueError(
                        f"검색 타입 {place_type!r}가 COMP에 없습니다."
                    )
                if place_type in seen_patch_types:
                    raise ValueError(
                        f"보정 타입 {place_type!r} 중복: "
                        f"{seen_patch_types[place_type]!r}, {subgroup_name!r}"
                    )
                seen_patch_types[place_type] = subgroup_name


def require_input_files() -> None:
    missing = [
        str(path)
        for path in (INPUT_PLACES, INPUT_RESIDUAL)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "필요한 v1.3 파일을 찾을 수 없습니다:\n- "
            + "\n- ".join(missing)
            + "\n스크립트를 route_maker/test 폴더에서 실행하는지 확인하세요."
        )


def meters_per_lon_degree(latitude: float) -> float:
    return 111_320.0 * math.cos(math.radians(latitude))


def offset_coordinate(
    latitude: float,
    longitude: float,
    east_m: float,
    north_m: float,
) -> Tuple[float, float]:
    new_latitude = latitude + north_m / 111_320.0
    new_longitude = longitude + east_m / meters_per_lon_degree(latitude)
    return new_latitude, new_longitude


def make_3x3_centers(
    latitude: float,
    longitude: float,
    offset_m: float,
) -> List[Tuple[float, float]]:
    centers: List[Tuple[float, float]] = []
    for north_m in (-offset_m, 0.0, offset_m):
        for east_m in (-offset_m, 0.0, offset_m):
            centers.append(
                offset_coordinate(
                    latitude=latitude,
                    longitude=longitude,
                    east_m=east_m,
                    north_m=north_m,
                )
            )
    return centers


def inside_bbox(latitude: float, longitude: float) -> bool:
    return (
        MIN_LAT <= latitude <= MAX_LAT
        and MIN_LON <= longitude <= MAX_LON
    )


def query_key(
    subgroup_name: str,
    latitude: float,
    longitude: float,
    radius_m: float,
) -> Tuple[str, int, int, int]:
    return (
        subgroup_name,
        int(round(latitude * 1_000_000)),
        int(round(longitude * 1_000_000)),
        int(round(radius_m * 10)),
    )


# =============================================================================
# 입력 CSV
# =============================================================================
def split_pipe(value: str) -> Set[str]:
    return {
        item.strip()
        for item in (value or "").split("|")
        if item.strip()
    }


def load_existing_places() -> Dict[str, dict]:
    places_by_id: Dict[str, dict] = {}

    with INPUT_PLACES.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required = {
            "place_id",
            "name",
            "latitude",
            "longitude",
            "primary_type",
            "types",
            "query_groups",
            "search_passes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"기존 장소 CSV에 필수 열이 없습니다: {sorted(missing)}"
            )

        for row in reader:
            place_id = (row.get("place_id") or "").strip()
            if not place_id:
                continue

            places_by_id[place_id] = {
                "place_id": place_id,
                "name": row.get("name", ""),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "primary_type": row.get("primary_type", ""),
                "types": split_pipe(row.get("types", "")),
                "query_groups": split_pipe(row.get("query_groups", "")),
                "search_passes": split_pipe(row.get("search_passes", "")),
            }

    return places_by_id


def load_residual_rows() -> List[dict]:
    rows: List[dict] = []

    with INPUT_RESIDUAL.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required = {"group", "latitude", "longitude", "radius_m"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"잔여 포화 CSV에 필수 열이 없습니다: {sorted(missing)}"
            )

        for row in reader:
            source_group = (row.get("group") or "").strip()
            if source_group not in PATCH_GROUPS:
                raise ValueError(
                    f"PATCH_GROUPS에 정의되지 않은 잔여 그룹: {source_group!r}"
                )

            rows.append({
                "group": source_group,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "radius_m": float(row["radius_m"]),
            })

    return rows


# =============================================================================
# Google Places 호출
# =============================================================================
def search_nearby(
    api_key: str,
    latitude: float,
    longitude: float,
    included_types: Sequence[str],
    radius_m: float,
) -> List[dict]:
    request_body = {
        "includedTypes": list(included_types),
        "maxResultCount": MAX_RESULTS,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_m,
            }
        },
    }

    body = json.dumps(request_body).encode("utf-8")

    for attempt in range(1, MAX_RETRIES + 1):
        request = urllib.request.Request(
            API_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": (
                    "places.id,"
                    "places.displayName,"
                    "places.location,"
                    "places.primaryType,"
                    "places.types"
                ),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response).get("places", [])

        except urllib.error.HTTPError as error:
            error_text = error.read().decode("utf-8", errors="replace")

            if error.code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"Nearby Search 실패: HTTP {error.code}\n"
                    f"중심: {latitude}, {longitude}\n"
                    f"반경: {radius_m}m\n"
                    f"타입: {', '.join(included_types)}\n"
                    f"응답:\n{error_text}"
                ) from error

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Nearby Search가 {MAX_RETRIES}회 후 실패. "
                    f"HTTP {error.code}\n{error_text}"
                ) from error

            wait_seconds = 2 ** (attempt - 1)
            print(
                f"  일시적 HTTP {error.code}; {wait_seconds}초 후 재시도 "
                f"({attempt}/{MAX_RETRIES})"
            )
            time.sleep(wait_seconds)

        except urllib.error.URLError as error:
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Google Places 연결 실패: {error.reason}"
                ) from error

            wait_seconds = 2 ** (attempt - 1)
            print(
                f"  네트워크 오류; {wait_seconds}초 후 재시도 "
                f"({attempt}/{MAX_RETRIES}): {error.reason}"
            )
            time.sleep(wait_seconds)

    return []


def merge_place(
    places_by_id: Dict[str, dict],
    place: dict,
    subgroup_name: str,
    pass_name: str,
) -> bool:
    """새 Place ID이면 True, 기존 장소 갱신이면 False."""
    place_id = place.get("id")
    location = place.get("location", {})
    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if not place_id or latitude is None or longitude is None:
        return False

    latitude = float(latitude)
    longitude = float(longitude)

    if not inside_bbox(latitude, longitude):
        return False

    name = place.get("displayName", {}).get("text", "")
    primary_type = place.get("primaryType", "")
    types = set(place.get("types", []))

    if place_id not in places_by_id:
        places_by_id[place_id] = {
            "place_id": place_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "primary_type": primary_type,
            "types": types,
            "query_groups": {subgroup_name},
            "search_passes": {pass_name},
        }
        return True

    existing = places_by_id[place_id]
    existing["types"].update(types)
    existing["query_groups"].add(subgroup_name)
    existing["search_passes"].add(pass_name)

    if not existing["name"] and name:
        existing["name"] = name
    if not existing["primary_type"] and primary_type:
        existing["primary_type"] = primary_type

    return False


# =============================================================================
# 보정 작업 생성 및 실행
# =============================================================================
def build_split_jobs(residual_rows: Sequence[dict]) -> List[dict]:
    jobs: Dict[Tuple[str, int, int, int], dict] = {}

    for row in residual_rows:
        source_group = row["group"]
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
        radius_m = float(row["radius_m"])

        for subgroup_name, included_types in PATCH_GROUPS[source_group].items():
            key = query_key(
                subgroup_name,
                latitude,
                longitude,
                radius_m,
            )
            jobs[key] = {
                "source_group": source_group,
                "subgroup": subgroup_name,
                "included_types": included_types,
                "latitude": latitude,
                "longitude": longitude,
                "radius_m": radius_m,
            }

    rows = list(jobs.values())
    rows.sort(
        key=lambda row: (
            row["subgroup"],
            row["latitude"],
            row["longitude"],
        )
    )

    if TEST_MODE:
        rows = rows[:TEST_JOB_LIMIT]

    return rows


def build_refine_jobs(
    saturated_rows: Sequence[dict],
    offset_m: float,
    radius_m: float,
) -> List[dict]:
    jobs: Dict[Tuple[str, int, int, int], dict] = {}

    for row in saturated_rows:
        subgroup_name = row["subgroup"]
        included_types = row["included_types"]
        source_group = row["source_group"]

        for latitude, longitude in make_3x3_centers(
            float(row["latitude"]),
            float(row["longitude"]),
            offset_m,
        ):
            key = query_key(
                subgroup_name,
                latitude,
                longitude,
                radius_m,
            )
            jobs[key] = {
                "source_group": source_group,
                "subgroup": subgroup_name,
                "included_types": included_types,
                "latitude": latitude,
                "longitude": longitude,
                "radius_m": radius_m,
            }

    rows = list(jobs.values())
    rows.sort(
        key=lambda row: (
            row["subgroup"],
            row["latitude"],
            row["longitude"],
        )
    )
    return rows


def run_jobs(
    api_key: str,
    places_by_id: Dict[str, dict],
    jobs: Sequence[dict],
    pass_name: str,
) -> Tuple[List[dict], int, int, Counter]:
    saturated: List[dict] = []
    new_place_count = 0
    raw_result_count = 0
    group_result_counts: Counter = Counter()

    print(f"\n[{pass_name}] 요청 수: {len(jobs)}")

    for index, job in enumerate(jobs, start=1):
        subgroup_name = job["subgroup"]
        latitude = float(job["latitude"])
        longitude = float(job["longitude"])
        radius_m = float(job["radius_m"])
        included_types = list(job["included_types"])

        print(
            f"[{pass_name} {index}/{len(jobs)}] "
            f"{subgroup_name}: "
            f"{latitude:.6f}, {longitude:.6f} / {radius_m:.0f}m"
        )

        places = search_nearby(
            api_key=api_key,
            latitude=latitude,
            longitude=longitude,
            included_types=included_types,
            radius_m=radius_m,
        )

        result_count = len(places)
        raw_result_count += result_count
        group_result_counts[subgroup_name] += result_count

        if result_count == MAX_RESULTS:
            saturated.append({
                "pass_name": pass_name,
                "source_group": job["source_group"],
                "subgroup": subgroup_name,
                "included_types": included_types,
                "latitude": latitude,
                "longitude": longitude,
                "radius_m": radius_m,
                "result_count": result_count,
            })

        for place in places:
            is_new = merge_place(
                places_by_id=places_by_id,
                place=place,
                subgroup_name=subgroup_name,
                pass_name=pass_name,
            )
            if is_new:
                new_place_count += 1

        time.sleep(REQUEST_DELAY_SECONDS)

    return saturated, new_place_count, raw_result_count, group_result_counts


# =============================================================================
# 점수 및 출력
# =============================================================================
def component_score(types: Iterable[str]) -> Tuple[float, float]:
    social_values: List[float] = []
    access_values: List[float] = []

    for place_type in types:
        social, access = COMP.get(place_type, (0.0, 0.0))
        social_values.append(social)
        access_values.append(access)

    return (
        max(social_values, default=0.0),
        max(access_values, default=0.0),
    )


def build_output_rows(
    places_by_id: Dict[str, dict],
) -> Tuple[List[dict], Counter, int]:
    output_rows: List[dict] = []
    unmapped_type_counter: Counter = Counter()
    scored_count = 0

    for place in places_by_id.values():
        types = sorted(place["types"])
        social_component, access_component = component_score(types)

        if social_component > 0.0 or access_component > 0.0:
            scored_count += 1

        for place_type in types:
            if place_type not in COMP and place_type not in GENERIC_TYPES:
                unmapped_type_counter[place_type] += 1

        output_rows.append({
            "place_id": place["place_id"],
            "name": place["name"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "primary_type": place["primary_type"],
            "types": "|".join(types),
            "social_component": social_component,
            "access_component": access_component,
            "query_groups": "|".join(sorted(place["query_groups"])),
            "search_passes": "|".join(sorted(place["search_passes"])),
        })

    output_rows.sort(
        key=lambda row: (
            -float(row["social_component"]),
            -float(row["access_component"]),
            str(row["name"]).lower(),
        )
    )

    return output_rows, unmapped_type_counter, scored_count


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[dict],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_places_csv(rows: Sequence[dict], suffix: str) -> Path:
    path = OUTPUT_DIR / f"williamsburg_places_scored_v1_4_{suffix}.csv"
    write_csv(
        path,
        [
            "place_id",
            "name",
            "latitude",
            "longitude",
            "primary_type",
            "types",
            "social_component",
            "access_component",
            "query_groups",
            "search_passes",
        ],
        rows,
    )
    return path


def write_unmapped_types(counter: Counter, suffix: str) -> Path:
    path = OUTPUT_DIR / f"williamsburg_unmapped_types_v1_4_{suffix}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["type", "count"])
        for place_type, count in counter.most_common():
            writer.writerow([place_type, count])
    return path


def write_saturation_csv(
    rows: Sequence[dict],
    suffix: str,
    stage: str,
) -> Path:
    path = OUTPUT_DIR / f"williamsburg_saturated_{stage}_v1_4_{suffix}.csv"

    serializable_rows = []
    for row in rows:
        serializable_rows.append({
            "pass_name": row["pass_name"],
            "source_group": row["source_group"],
            "subgroup": row["subgroup"],
            "included_types": "|".join(row["included_types"]),
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "radius_m": row["radius_m"],
            "result_count": row["result_count"],
        })

    write_csv(
        path,
        [
            "pass_name",
            "source_group",
            "subgroup",
            "included_types",
            "latitude",
            "longitude",
            "radius_m",
            "result_count",
        ],
        serializable_rows,
    )
    return path


def write_patch_summary(
    suffix: str,
    split_jobs: Sequence[dict],
    fine_jobs: Sequence[dict],
    micro_jobs: Sequence[dict],
    split_saturated: Sequence[dict],
    fine_saturated: Sequence[dict],
    micro_saturated: Sequence[dict],
    split_results: Counter,
    fine_results: Counter,
    micro_results: Counter,
) -> Path:
    path = OUTPUT_DIR / f"patch_group_summary_v1_4_{suffix}.csv"

    job_counts = Counter(row["subgroup"] for row in split_jobs)
    fine_job_counts = Counter(row["subgroup"] for row in fine_jobs)
    micro_job_counts = Counter(row["subgroup"] for row in micro_jobs)

    split_sat_counts = Counter(row["subgroup"] for row in split_saturated)
    fine_sat_counts = Counter(row["subgroup"] for row in fine_saturated)
    micro_sat_counts = Counter(row["subgroup"] for row in micro_saturated)

    all_subgroups = sorted({
        subgroup
        for subgroups in PATCH_GROUPS.values()
        for subgroup in subgroups
    })

    rows = []
    for subgroup in all_subgroups:
        rows.append({
            "subgroup": subgroup,
            "split_jobs": job_counts[subgroup],
            "split_raw_results": split_results[subgroup],
            "split_saturated": split_sat_counts[subgroup],
            "fine_jobs": fine_job_counts[subgroup],
            "fine_raw_results": fine_results[subgroup],
            "fine_saturated": fine_sat_counts[subgroup],
            "micro_jobs": micro_job_counts[subgroup],
            "micro_raw_results": micro_results[subgroup],
            "micro_saturated": micro_sat_counts[subgroup],
        })

    write_csv(
        path,
        [
            "subgroup",
            "split_jobs",
            "split_raw_results",
            "split_saturated",
            "fine_jobs",
            "fine_raw_results",
            "fine_saturated",
            "micro_jobs",
            "micro_raw_results",
            "micro_saturated",
        ],
        rows,
    )
    return path


def write_component_rubric() -> Path:
    path = OUTPUT_DIR / "component_rubric_v1_4.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["type", "social_component", "access_component"])
        for place_type, (social, access) in sorted(COMP.items()):
            writer.writerow([place_type, social, access])
    return path


# =============================================================================
# main
# =============================================================================
def main() -> None:
    validate_configuration()
    require_input_files()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    api_key = getpass.getpass("Google Places API key: ").strip()
    if not api_key:
        raise ValueError("API key가 입력되지 않았습니다.")

    places_by_id = load_existing_places()
    existing_place_count = len(places_by_id)
    residual_rows = load_residual_rows()

    print("\n" + "=" * 72)
    print("v1.4 잔여 포화 보정")
    print("=" * 72)
    print(f"기존 v1.3 장소 수: {existing_place_count}")
    print(f"잔여 포화 원: {len(residual_rows)}")
    print(f"실행 모드: {'TEST' if TEST_MODE else 'FULL'}")

    split_jobs = build_split_jobs(residual_rows)

    (
        split_saturated,
        new_split,
        split_raw_results,
        split_group_results,
    ) = run_jobs(
        api_key=api_key,
        places_by_id=places_by_id,
        jobs=split_jobs,
        pass_name="v1_4_split",
    )

    fine_jobs: List[dict] = []
    fine_saturated: List[dict] = []
    new_fine = 0
    fine_raw_results = 0
    fine_group_results: Counter = Counter()

    if not TEST_MODE and split_saturated:
        fine_jobs = build_refine_jobs(
            saturated_rows=split_saturated,
            offset_m=FINE_OFFSET_M,
            radius_m=FINE_RADIUS_M,
        )
        (
            fine_saturated,
            new_fine,
            fine_raw_results,
            fine_group_results,
        ) = run_jobs(
            api_key=api_key,
            places_by_id=places_by_id,
            jobs=fine_jobs,
            pass_name="v1_4_fine",
        )

    micro_jobs: List[dict] = []
    micro_saturated: List[dict] = []
    new_micro = 0
    micro_raw_results = 0
    micro_group_results: Counter = Counter()

    if not TEST_MODE and fine_saturated:
        micro_jobs = build_refine_jobs(
            saturated_rows=fine_saturated,
            offset_m=MICRO_OFFSET_M,
            radius_m=MICRO_RADIUS_M,
        )
        (
            micro_saturated,
            new_micro,
            micro_raw_results,
            micro_group_results,
        ) = run_jobs(
            api_key=api_key,
            places_by_id=places_by_id,
            jobs=micro_jobs,
            pass_name="v1_4_micro",
        )

    output_rows, unmapped_counter, scored_count = build_output_rows(
        places_by_id
    )

    suffix = "test" if TEST_MODE else "full"

    places_file = write_places_csv(output_rows, suffix)
    unmapped_file = write_unmapped_types(unmapped_counter, suffix)
    split_sat_file = write_saturation_csv(
        split_saturated, suffix, "split"
    )
    fine_sat_file = write_saturation_csv(
        fine_saturated, suffix, "fine"
    )
    micro_sat_file = write_saturation_csv(
        micro_saturated, suffix, "micro"
    )
    summary_file = write_patch_summary(
        suffix=suffix,
        split_jobs=split_jobs,
        fine_jobs=fine_jobs,
        micro_jobs=micro_jobs,
        split_saturated=split_saturated,
        fine_saturated=fine_saturated,
        micro_saturated=micro_saturated,
        split_results=split_group_results,
        fine_results=fine_group_results,
        micro_results=micro_group_results,
    )
    rubric_file = write_component_rubric()

    final_place_count = len(output_rows)
    new_total = final_place_count - existing_place_count
    coverage = (
        scored_count / final_place_count * 100.0
        if final_place_count
        else 0.0
    )
    total_requests = len(split_jobs) + len(fine_jobs) + len(micro_jobs)

    print("\n" + "=" * 72)
    print("v1.4 보정 완료")
    print("=" * 72)
    print(f"총 추가 API 요청 수: {total_requests}")
    print(f"기존 v1.3 장소 수: {existing_place_count}")
    print(f"v1.4 최종 장소 수: {final_place_count}")
    print(f"새로 추가된 장소 수: {new_total}")
    print(
        "패스별 신규 장소: "
        f"split {new_split}, fine {new_fine}, micro {new_micro}"
    )
    print(f"성분 배정 장소 수: {scored_count}")
    print(f"성분 커버리지: {coverage:.1f}%")
    print(f"split 포화 요청 수: {len(split_saturated)}")
    print(f"fine 포화 요청 수: {len(fine_saturated)}")
    print(f"micro 잔여 포화 요청 수: {len(micro_saturated)}")

    print(f"\n최종 장소 데이터: {places_file}")
    print(f"미분류 타입: {unmapped_file}")
    print(f"split 포화 기록: {split_sat_file}")
    print(f"fine 포화 기록: {fine_sat_file}")
    print(f"micro 포화 기록: {micro_sat_file}")
    print(f"보정 그룹 요약: {summary_file}")
    print(f"성분 루브릭: {rubric_file}")

    if TEST_MODE:
        print("\n테스트 모드입니다.")
        print("TEST_MODE = False로 바꾼 뒤 다시 실행하세요.")
    elif micro_saturated:
        print("\n주의: 30m 반경에서도 20개 제한에 걸린 요청이 남았습니다.")
        print(
            "williamsburg_saturated_micro_v1_4_full.csv에서 "
            "남은 subgroup만 확인하세요."
        )
    else:
        print("\n통과: micro 단계 후 잔여 포화 요청이 없습니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자가 실행을 중단했습니다.")
    except Exception as error:
        print("\n실행 실패")
        print(error)
        raise
