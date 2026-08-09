import csv
import getpass
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


API_URL = "https://places.googleapis.com/v1/places:searchNearby"

# =============================================================================
# 실행 설정
# =============================================================================
# 첫 실행은 True: 검색점 1개 x 7개 그룹 = 7회만 호출해 설정을 확인합니다.
# 테스트 성공 후 False로 바꾸고 전체 수집하세요.
TEST_MODE = False

# 기본 검색에서 결과가 20개로 잘린 요청만 더 작은 원 3x3으로 재검색합니다.
AUTO_TARGETED_REFINE = True

REQUEST_DELAY_SECONDS = 0.15
MAX_RETRIES = 3
MAX_RESULTS = 20

OUTPUT_DIR = Path("places_output_v1_3")

# 프로젝트 Williamsburg 분석 범위
MIN_LAT = 40.708
MAX_LAT = 40.722
MIN_LON = -73.970
MAX_LON = -73.950

# 그룹을 쪼갰으므로 기본 원부터 v1.2보다 작게 사용합니다.
BASE_GRID_SPACING_M = 220.0
BASE_SEARCH_RADIUS_M = 180.0

# 기본 요청이 20개로 포화되었을 때만 실행되는 지역 재검색
# 포화 원 중심 주변 3x3 지점에서 더 작은 원으로 같은 그룹만 다시 검색합니다.
REFINE_OFFSET_M = 80.0
REFINE_SEARCH_RADIUS_M = 105.0


# =============================================================================
# 검색 그룹
# =============================================================================
# 점수 축은 여전히 P_social / P_access 두 개입니다.
# 아래 그룹은 Google Nearby Search의 20개 제한을 피하기 위한 '수집 묶음'일 뿐입니다.
# 각 타입은 한 그룹에만 넣어 불필요한 중복 요청을 줄입니다.
SEARCH_GROUPS: Dict[str, List[str]] = {
    "social_cafes_bars": [
        "cafe",
        "coffee_shop",
        "bar",
        "pub",
        "night_club",
    ],
    "social_restaurants_food": [
        "restaurant",
        "bakery",
        "food_court",
        "ice_cream_shop",
    ],
    "social_culture_public": [
        "community_center",
        "coworking_space",
        "library",
        "book_store",
        "art_gallery",
        "museum",
        "performing_arts_theater",
        "movie_theater",
        "event_venue",
        "live_music_venue",
        "park",
        "plaza",
    ],
    "access_daily_resources": [
        "farmers_market",
        "market",
        "supermarket",
        "grocery_store",
        "convenience_store",
        "department_store",
        "pharmacy",
        "drugstore",
    ],
    "access_health_civic": [
        "medical_clinic",
        "doctor",
        "dentist",
        "bank",
        "atm",
        "post_office",
        "laundry",
        "fitness_center",
        "gym",
    ],
    "access_retail_goods": [
        "clothing_store",
        "electronics_store",
        "hardware_store",
        "home_goods_store",
        "bicycle_store",
        "pet_store",
        "cell_phone_store",
        "furniture_store",
        "gift_shop",
    ],
    "access_personal_mixed": [
        "beauty_salon",
        "hair_salon",
        "barber_shop",
        "florist",
        "shopping_mall",
    ],
}


# =============================================================================
# 성분 루브릭: Google place type -> (social, access)
# =============================================================================
# 허용 단계: 0.0 / 0.3 / 0.5 / 0.8 / 1.0
#
# Social 질문:
# "낯선 사람들과 같은 공간에 머무르는 것이 이 장소의 본질인가?"
#
# Access 질문:
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

# 응답에 자주 붙는 상위 타입. 미분류 검수 CSV에서는 제외합니다.
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
                f"COMP[{place_type!r}]에 허용되지 않은 성분값: "
                f"({social}, {access})"
            )

    seen_types: Dict[str, str] = {}

    for group_name, place_types in SEARCH_GROUPS.items():
        if not place_types:
            raise ValueError(f"SEARCH_GROUPS[{group_name!r}]가 비어 있습니다.")
        if len(place_types) > 50:
            raise ValueError(
                f"SEARCH_GROUPS[{group_name!r}] 타입 수가 50개를 넘습니다."
            )

        local_duplicates = [
            place_type
            for place_type, count in Counter(place_types).items()
            if count > 1
        ]
        if local_duplicates:
            raise ValueError(
                f"{group_name} 내부 중복 타입: {local_duplicates}"
            )

        for place_type in place_types:
            if place_type in seen_types:
                raise ValueError(
                    f"타입 {place_type!r}가 두 그룹에 중복됨: "
                    f"{seen_types[place_type]!r}, {group_name!r}"
                )
            seen_types[place_type] = group_name

            if place_type not in COMP:
                raise ValueError(
                    f"검색 타입 {place_type!r}가 COMP에 없습니다. "
                    "성분값을 먼저 지정하세요."
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


def make_grid(spacing_m: float) -> List[Tuple[float, float]]:
    middle_lat = (MIN_LAT + MAX_LAT) / 2.0
    height_m = (MAX_LAT - MIN_LAT) * 111_320.0
    width_m = (MAX_LON - MIN_LON) * meters_per_lon_degree(middle_lat)

    lat_steps = max(1, math.ceil(height_m / spacing_m))
    lon_steps = max(1, math.ceil(width_m / spacing_m))

    points: List[Tuple[float, float]] = []

    for row in range(lat_steps + 1):
        latitude = MIN_LAT + (MAX_LAT - MIN_LAT) * (row / lat_steps)
        for column in range(lon_steps + 1):
            longitude = MIN_LON + (MAX_LON - MIN_LON) * (column / lon_steps)
            points.append((latitude, longitude))

    return points


def make_refine_centers(
    latitude: float,
    longitude: float,
) -> List[Tuple[float, float]]:
    centers: List[Tuple[float, float]] = []

    for north_m in (-REFINE_OFFSET_M, 0.0, REFINE_OFFSET_M):
        for east_m in (-REFINE_OFFSET_M, 0.0, REFINE_OFFSET_M):
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


def query_key(group_name: str, latitude: float, longitude: float) -> Tuple[str, int, int]:
    # 약 1m보다 작은 차이는 같은 재검색 지점으로 간주합니다.
    return (
        group_name,
        int(round(latitude * 1_000_000)),
        int(round(longitude * 1_000_000)),
    )


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
                    f"검색 중심: {latitude}, {longitude}\n"
                    f"검색 타입: {', '.join(included_types)}\n"
                    f"응답 본문:\n{error_text}"
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
    group_name: str,
    pass_name: str,
) -> None:
    place_id = place.get("id")
    location = place.get("location", {})
    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if not place_id or latitude is None or longitude is None:
        return

    latitude = float(latitude)
    longitude = float(longitude)

    if not inside_bbox(latitude, longitude):
        return

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
            "query_groups": {group_name},
            "search_passes": {pass_name},
        }
        return

    existing = places_by_id[place_id]
    existing["types"].update(types)
    existing["query_groups"].add(group_name)
    existing["search_passes"].add(pass_name)

    if not existing["name"] and name:
        existing["name"] = name
    if not existing["primary_type"] and primary_type:
        existing["primary_type"] = primary_type


# =============================================================================
# 수집 패스
# =============================================================================
def collect_base_pass(
    api_key: str,
    places_by_id: Dict[str, dict],
    test_mode: bool,
) -> Tuple[List[dict], int, Counter]:
    grid = make_grid(BASE_GRID_SPACING_M)
    if test_mode:
        grid = grid[:1]

    total_requests = len(grid) * len(SEARCH_GROUPS)
    saturated: List[dict] = []
    group_result_counts: Counter = Counter()
    request_index = 0

    print("\n[base] 기본 수집")
    print(f"검색 지점: {len(grid)}개")
    print(f"검색 그룹: {len(SEARCH_GROUPS)}개")
    print(f"예상 요청: {total_requests}회")
    print(
        f"반경 {BASE_SEARCH_RADIUS_M:.0f}m / "
        f"격자 간격 {BASE_GRID_SPACING_M:.0f}m\n"
    )

    for group_name, included_types in SEARCH_GROUPS.items():
        for latitude, longitude in grid:
            request_index += 1
            print(
                f"[base {request_index}/{total_requests}] "
                f"{group_name}: {latitude:.6f}, {longitude:.6f}"
            )

            places = search_nearby(
                api_key=api_key,
                latitude=latitude,
                longitude=longitude,
                included_types=included_types,
                radius_m=BASE_SEARCH_RADIUS_M,
            )

            group_result_counts[group_name] += len(places)

            if len(places) == MAX_RESULTS:
                saturated.append({
                    "pass_name": "base",
                    "group": group_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_m": BASE_SEARCH_RADIUS_M,
                    "result_count": len(places),
                })

            for place in places:
                merge_place(
                    places_by_id=places_by_id,
                    place=place,
                    group_name=group_name,
                    pass_name="base",
                )

            time.sleep(REQUEST_DELAY_SECONDS)

    return saturated, total_requests, group_result_counts


def collect_targeted_refine(
    api_key: str,
    places_by_id: Dict[str, dict],
    base_saturated: Sequence[dict],
) -> Tuple[List[dict], int, Counter]:
    # 이웃한 포화 원들이 같은 지역을 만들 수 있으므로 재검색 지점을 중복 제거합니다.
    refine_jobs: Dict[Tuple[str, int, int], Tuple[str, float, float]] = {}

    for row in base_saturated:
        group_name = str(row["group"])
        center_lat = float(row["latitude"])
        center_lon = float(row["longitude"])

        for latitude, longitude in make_refine_centers(center_lat, center_lon):
            key = query_key(group_name, latitude, longitude)
            refine_jobs[key] = (group_name, latitude, longitude)

    total_requests = len(refine_jobs)
    residual_saturated: List[dict] = []
    group_result_counts: Counter = Counter()

    print("\n[refine] 포화 지역만 정밀 재수집")
    print(f"중복 제거 후 정밀 요청: {total_requests}회")
    print(
        f"정밀 반경 {REFINE_SEARCH_RADIUS_M:.0f}m / "
        f"중심 오프셋 {REFINE_OFFSET_M:.0f}m\n"
    )

    for request_index, (_, job) in enumerate(refine_jobs.items(), start=1):
        group_name, latitude, longitude = job
        included_types = SEARCH_GROUPS[group_name]

        print(
            f"[refine {request_index}/{total_requests}] "
            f"{group_name}: {latitude:.6f}, {longitude:.6f}"
        )

        places = search_nearby(
            api_key=api_key,
            latitude=latitude,
            longitude=longitude,
            included_types=included_types,
            radius_m=REFINE_SEARCH_RADIUS_M,
        )

        group_result_counts[group_name] += len(places)

        if len(places) == MAX_RESULTS:
            residual_saturated.append({
                "pass_name": "refine",
                "group": group_name,
                "latitude": latitude,
                "longitude": longitude,
                "radius_m": REFINE_SEARCH_RADIUS_M,
                "result_count": len(places),
            })

        for place in places:
            merge_place(
                places_by_id=places_by_id,
                place=place,
                group_name=group_name,
                pass_name="refine",
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    return residual_saturated, total_requests, group_result_counts


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


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_places_csv(rows: Sequence[dict], suffix: str) -> Path:
    path = OUTPUT_DIR / f"williamsburg_places_scored_v1_3_{suffix}.csv"
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
    path = OUTPUT_DIR / f"williamsburg_unmapped_types_v1_3_{suffix}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["type", "count"])
        for place_type, count in counter.most_common():
            writer.writerow([place_type, count])
    return path


def write_saturation_csv(rows: Sequence[dict], suffix: str, stage: str) -> Path:
    path = OUTPUT_DIR / f"williamsburg_saturated_{stage}_v1_3_{suffix}.csv"
    write_csv(
        path,
        [
            "pass_name",
            "group",
            "latitude",
            "longitude",
            "radius_m",
            "result_count",
        ],
        rows,
    )
    return path


def write_component_rubric() -> Path:
    path = OUTPUT_DIR / "component_rubric_v1_3.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["type", "social_component", "access_component"])
        for place_type, (social, access) in sorted(COMP.items()):
            writer.writerow([place_type, social, access])
    return path


def write_group_summary(
    suffix: str,
    base_saturated: Sequence[dict],
    residual_saturated: Sequence[dict],
    base_result_counts: Counter,
    refine_result_counts: Counter,
) -> Path:
    path = OUTPUT_DIR / f"collection_group_summary_v1_3_{suffix}.csv"

    base_sat_counts = Counter(row["group"] for row in base_saturated)
    residual_sat_counts = Counter(row["group"] for row in residual_saturated)

    rows = []
    for group_name, place_types in SEARCH_GROUPS.items():
        rows.append({
            "group": group_name,
            "type_count": len(place_types),
            "base_raw_results": base_result_counts[group_name],
            "base_saturated_requests": base_sat_counts[group_name],
            "refine_raw_results": refine_result_counts[group_name],
            "residual_saturated_requests": residual_sat_counts[group_name],
            "types": "|".join(place_types),
        })

    write_csv(
        path,
        [
            "group",
            "type_count",
            "base_raw_results",
            "base_saturated_requests",
            "refine_raw_results",
            "residual_saturated_requests",
            "types",
        ],
        rows,
    )
    return path


# =============================================================================
# main
# =============================================================================
def main() -> None:
    validate_configuration()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    api_key = getpass.getpass("Google Places API key: ").strip()
    if not api_key:
        raise ValueError("API key가 입력되지 않았습니다.")

    places_by_id: Dict[str, dict] = {}

    base_saturated, base_requests, base_result_counts = collect_base_pass(
        api_key=api_key,
        places_by_id=places_by_id,
        test_mode=TEST_MODE,
    )

    base_ratio = (
        len(base_saturated) / base_requests
        if base_requests
        else 0.0
    )

    print(
        f"\n[base] 포화 요청: {len(base_saturated)}/{base_requests} "
        f"({base_ratio:.1%})"
    )

    residual_saturated: List[dict] = []
    refine_requests = 0
    refine_result_counts: Counter = Counter()

    if (
        not TEST_MODE
        and AUTO_TARGETED_REFINE
        and base_saturated
    ):
        (
            residual_saturated,
            refine_requests,
            refine_result_counts,
        ) = collect_targeted_refine(
            api_key=api_key,
            places_by_id=places_by_id,
            base_saturated=base_saturated,
        )

        residual_ratio = (
            len(residual_saturated) / refine_requests
            if refine_requests
            else 0.0
        )

        print(
            f"\n[refine] 여전히 포화된 요청: "
            f"{len(residual_saturated)}/{refine_requests} "
            f"({residual_ratio:.1%})"
        )

    output_rows, unmapped_counter, scored_count = build_output_rows(
        places_by_id
    )

    suffix = "test" if TEST_MODE else "full"
    places_file = write_places_csv(output_rows, suffix)
    unmapped_file = write_unmapped_types(unmapped_counter, suffix)
    base_sat_file = write_saturation_csv(
        base_saturated, suffix, "base"
    )
    residual_sat_file = write_saturation_csv(
        residual_saturated, suffix, "refine"
    )
    rubric_file = write_component_rubric()
    summary_file = write_group_summary(
        suffix=suffix,
        base_saturated=base_saturated,
        residual_saturated=residual_saturated,
        base_result_counts=base_result_counts,
        refine_result_counts=refine_result_counts,
    )

    total_places = len(output_rows)
    coverage = (
        scored_count / total_places * 100.0
        if total_places
        else 0.0
    )
    total_requests = base_requests + refine_requests

    print("\n" + "=" * 72)
    print("v1.3 수집 완료")
    print("=" * 72)
    print(f"실행 모드: {'TEST' if TEST_MODE else 'FULL'}")
    print(f"검색 그룹 수: {len(SEARCH_GROUPS)}")
    print(f"총 API 요청 수: {total_requests}")
    print(f"Place ID 중복 제거 후 장소 수: {total_places}")
    print(f"성분 배정 장소 수: {scored_count}")
    print(f"성분 커버리지: {coverage:.1f}%")
    print(f"기본 포화 요청 수: {len(base_saturated)}")
    print(f"정밀 검색 후 잔여 포화 요청 수: {len(residual_saturated)}")
    print(f"\n장소 데이터: {places_file}")
    print(f"미분류 타입: {unmapped_file}")
    print(f"기본 포화 기록: {base_sat_file}")
    print(f"잔여 포화 기록: {residual_sat_file}")
    print(f"그룹 요약: {summary_file}")
    print(f"성분 루브릭: {rubric_file}")

    if TEST_MODE:
        print("\n테스트가 성공했습니다.")
        print("코드 상단의 TEST_MODE = False로 바꾼 뒤 다시 실행하세요.")
    elif residual_saturated:
        print("\n주의: 정밀 검색에서도 20개 제한에 걸린 원이 남아 있습니다.")
        print(
            "williamsburg_saturated_refine_v1_3_full.csv를 확인하세요. "
            "이 경우 해당 그룹만 더 쪼개거나 반경을 줄이면 됩니다."
        )
    else:
        print("\n통과: 정밀 검색 후 잔여 포화 요청이 없습니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자가 실행을 중단했습니다.")
    except Exception as error:
        print("\n실행 실패")
        print(error)
        raise
