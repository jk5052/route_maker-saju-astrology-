# Lucky Path (lucky-path)

사주·점성술의 **계산된 신호**를 **명시적 해석 규칙**에 통과시켜 "오늘의 행운 유형과 성질"을 만들고,
이를 거리 품질 가중치로 변환해 최단 경로 대신 **오늘 나에게 운이 좋은 보행 경로**를 계산하는 프로젝트.

핵심 원칙: **계산 결과는 라이브러리가 만들고, 해석 규칙은 CSV로 명시적으로 설계하고, LLM은 결과를 설명만 한다.**
그래야 결과가 이상할 때 어느 단계(계산/규칙/설명)의 문제인지 추적·수정할 수 있다.

## 파이프라인

```
생년월일[시]
   │
   ├── engine/saju_engine.py ────── raw: 원국(연월일[시]주, 오행 분포, 과다/부족),
   │                                     일진, 십성, 합·충          [계산: lunar_python]
   ├── engine/astrology_engine.py ─ raw: 출생/트랜짓 행성 황경, 애스펙트(각·orb·strength),
   │                                     원소, 달 위상              [계산: astronomy_engine]
   │
   └── engine/combine_reading.py                                    [해석: 규칙표]
         × config/saju_rules.csv, astrology_rules.csv
         → Event(만남·기회·발견) + Quality(활성·수용·명료·확장·안정·흐름)
           출처별(saju/astrology/combined) 보존 + evidence + 문장 템플릿 + llm_payload
         × config/quality_street_matrix.csv
         → 거리 품질 가중치 8종
         → engine/daily_reading.json
                │
data/raw/* ──> data/processed/street_segments.geojson (품질 점수 붙은 세그먼트)
                │
                └── grasshopper/lucky_route.gh  (또는 CLI 실행)
                      → outputs/{fastest,lucky}_route.geojson, design_space.csv
                              │
                              └── web/mapbox-prototype/  (시각화)
```

## 해석 레이어 설계

| 층 | 무엇 | 어디에 |
|---|---|---|
| 계산 | 일주·십성·합충 / 행성 황경·애스펙트·orb | `engine/{saju,astrology}_engine.py` — 해석 단어 없음, 구조화된 신호만 출력 |
| 해석 | 신호 → Event·Quality 점수 (weight × strength 누적, 1−e⁻ˣ 포화 정규화) | `config/{saju,astrology}_rules.csv` + `engine/combine_reading.py` |
| 브리지 | 일일 성질(6) → 물리적 거리 품질(8) | `config/quality_street_matrix.csv` |
| 설명 | 완성된 결과를 자연어로 | `daily_reading.json`의 `llm_payload` (결과 변경·신호 추가 금지, 3문장, 비확정적 표현 제약 포함) |

- **Event**: `encounter`(비견·겁재, Venus·Moon…), `opportunity`(재성·관성, Jupiter·Saturn…), `discovery`(식상·인성, Mercury·Uranus…)
- **Quality**: `activation`(화·Mars), `receptivity`(수·Venus), `clarity`(금·Mercury), `expansion`(목·Jupiter), `grounding`(토·Saturn), `flow`(수·Neptune)
- 사주와 점성술 결과가 다르면 하나를 버리지 않고 `saju`/`astrology`/`combined`를 모두 보존, `evidence`에 발화된 규칙과 기여 점수를 기록한다.

## 실행 순서

```bash
# 1. 오늘의 리딩 (--birth-time 있으면 시주 포함)
.venv/bin/python engine/combine_reading.py --birth 1994-02-02 [--birth-time 08:30]

# 2. 경로 계산 (Rhino 없이도 실행 가능 — grasshopper/README.md 참고)
.venv/bin/python grasshopper/lucky_route_ghpython.py --origin=-74.0020,40.7280 --dest=-73.9948,40.7352

# 3. 웹 프로토타입 (레포 루트에서; app.js 의 MAPBOX_TOKEN 먼저 입력)
python -m http.server   # → http://localhost:8000/web/mapbox-prototype/
```

## 디렉토리

| 경로 | 내용 |
|---|---|
| `config/` | `saju_rules.csv`(십성·오행·합충·원국균형 → Event/Quality), `astrology_rules.csv`(행성·원소 → Event/Quality), `quality_street_matrix.csv`(성질→거리 품질 브리지). **해석의 전부가 여기 있음 — 튜닝 포인트** |
| `data/raw/` | `lion/`(NYC 도로 중심선), `mappluto/`(필지·건물), `facilities/`, `seating/`, `osm/` |
| `data/processed/` | `street_segments.geojson` — 현재는 합성 샘플 격자 84개 |
| `engine/` | 계산 엔진 2 + 해석 엔진 1, 결과물 `daily_reading.json` |
| `grasshopper/` | `lucky_route.gh`(Rhino에서 생성) + GhPython 소스 + 구성 가이드 |
| `outputs/` | 경로 geojson 2종 + `design_space.csv` |
| `web/mapbox-prototype/` | 경로 토글 + 문장·행운 유형·성질·근거 패널 |

## street_segments.geojson 스키마

LineString FeatureCollection, `properties`: `segment_id`, `length_m`,
그리고 0–1 품질 8종 — `green`(가로수·공원), `water`(수변), `sunlight`(일조),
`open_sky`(개방감), `quiet`(저소음), `vibrant`(상업 활성), `rest`(좌석), `culture`(문화시설).
경로 비용: `length × (1.6 − luck)`, `luck = Σ 가중치 × 품질`.

## 계산 백엔드

`.venv`의 라이브러리가 있으면 자동으로 정밀 계산 (`raw.*.backend` 필드로 확인):

- 사주: `lunar_python` 만세력 (월주·시주 포함) → 폴백: 갑자일 앵커(1949-10-01, 검증됨) + 입춘 근사 연주
- 점성술: `astronomy_engine` 실제 황경·애스펙트 → 폴백: 태양궁 테이블 + 삭망월 근사 (애스펙트 없음)

## MVP 해석 체계 선언

본 모델은 **일간, 오행, 십성, 일진과 주요 합·충**(사주) 및 **행성·애스펙트·원소·달 위상**(점성술)을
중심으로 한 제한된 해석 체계를 사용한다. **용신, 격국, 신살, 대운·세운의 세부 판단과 하우스**
(출생 시각·장소 필요)는 초기 버전에서 제외한다.

정교화 단계 계획: 기준 명리학 자료 2–3개 선정 → 규칙표 확장 → 현업 상담가 매핑 검토 →
기준 사례 20–30개 비교 → 규칙별 출처·학파 기록 (`rules CSV`에 컬럼 추가).
