# 해석 규칙의 출처와 거리 변환 계수의 설계 이유

작성 기준일: 2026-09-30. 우선 검토한 경로 날짜: **2026-07-21**.

후속 요청에서 지정한 **2026-07-21**을 기준으로 한다. 이 날짜는 현재 저장된
[`engine/daily_reading.json`](../engine/daily_reading.json)의 날짜와 같다.
다른 날짜를 선택하면 그 날짜의 리딩과 전체 규칙 발화 내역을 다시 확인해야 한다.

## 기준 입력과 기여 범위

- 리딩 입력: 생년월일 `1994-02-02`, 출생 시각 `08:30`, 대상 날짜 `2026-07-21`.
- 저장된 계산 백엔드: 사주 `lunar_python`, 점성술 `astronomy_engine`.
- 거리 데이터: [`data/processed/street_segments.geojson`](../data/processed/street_segments.geojson).
- 경로 끝점: `(-74.0020, 40.7280)` → `(-73.9948, 40.7352)`.
- 기준 산출물: [`outputs/lucky_route.geojson`](../outputs/lucky_route.geojson).
  경로 파일 자체에는 날짜가 없으므로 저장된 리딩으로 구간 점수와 경로를 재현해 대응을 확인한다.

규칙의 우선순위는 저장된 `raw.saju`와 `raw.astrology`를 현재
`interpret_saju` / `interpret_astrology`에 다시 통과시킨 전체 발화 내역으로 정했다.
`daily_reading.json.evidence`는 상위 8개로 잘리므로 우선순위 선정에 사용하지 않았다.
점성술은 강도 `0.35` 이상인 애스펙트 중 상위 6개와 활성 원소를 사용한다.

전체 발화는 18회이며 서로 다른 규칙은 **사주 4개 + 점성술 10개 = 14개**다.
같은 규칙이 여러 애스펙트에서 발화하면 모두 누적된다.
`event`는 경험 설명에 쓰이고, 경로 비용에는 `quality`를 거리 가중치로 변환한 값이 사용된다.
여기서 **기여**는 양의 점수가 경로 비용 계산에 포함되었다는 뜻이다.
특정 규칙을 제거하면 선택된 경로가 반드시 바뀐다는 의미는 아니며, 그 반사실 비교는 수행하지 않았다.

## CSV 메타데이터의 의미

[`saju_rules.csv`](saju_rules.csv)와 [`astrology_rules.csv`](astrology_rules.csv)에
다음 5개 열을 추가했다. 기존 열의 값과 행 순서는 유지한다.

| 열 | 기록 범위 |
|---|---|
| `basis_type` | 확인한 상징적 의미의 출처 계열. `classical` / `modern` / `folk_verified` / `no_external_basis` 중 하나 |
| `reference` | 문헌·저자·절과 URL. 외부 출처를 확인하지 못했다면 그 사실과 내부 구현 위치를 명시 |
| `source_claim` | 출처에서 확인한 의미만 요약. 기존 `explanation` 전체에 대한 근거로 확대하지 않음 |
| `design_decision` | 경험 유형·성질로 옮기는 해석, 적용 범위의 변경, 숫자가 초기 설계값이라는 사실 |
| `verification_status` | `verified`: 명시한 `source_claim`을 출처에서 확인. `pending`: 외부 근거 미확인 또는 검토 대기 |

`verified`는 상징적 서술의 출처를 확인했다는 뜻이다. 경험 분류의 타당성이나
숫자 가중치, 경로 효과를 검증했다는 뜻이 아니다.
외부 출처는 원저자의 본문 또는 고전의 전사본으로 확인했다.
일부 사이트는 직접 열기에 접근 확인 화면을 반환하여 웹 검색의 색인 본문으로 확인했다.
고전은 인용한 절의 의미만 확인했으며 판본 간 대조는 하지 않았다.

우선 규칙 14개는 5개 열을 모두 채웠다. 그중 13개는 `verified`이며,
`natal_balance / deficient_element_active`는 외부 근거를 확인하지 못해 `pending`이다.
후속 요청으로 비활성 규칙 `element / wood`도 출처를 확인해 5개 열을 채웠다.
기본 메타데이터를 모두 작성한 행은 총 15개이며 그중 14개가 `verified`다.
나머지 18개 행은 `basis_type`과 `verification_status`만 채웠다.
이 행들은 보수적으로 `no_external_basis / pending`으로 두었다.
이는 **현재 행별 근거 기록을 확보하지 않았다는 상태**이며, 해당 개념에 전통적 배경이
없다는 주장이 아니다. 추후 출처를 확인하면 `basis_type`도 함께 갱신한다.
확인하지 못한 항목을 민간 관행으로 간주하지 않았으며 `folk_verified`로 지정한 행은 없다.

모든 `weight`, `base_weight` 및 아래의 행렬 계수는 **초기 설계값**이다.
문헌은 숫자의 크기나 상대 비율을 정당화하지 않는다.
비우선 행의 `design_decision`은 비워 두되, 초기 설계값이라는 원칙은 그 행에도 동일하게 적용한다.

## 우선 작성한 규칙

키는 `signal_type / signal / event / quality`이다. 발화 횟수는 규칙의 중요도나
문헌의 신뢰도가 아니라 이 입력에서 규칙이 호출된 횟수다.

| 파일 | 규칙 키 | 초기 설계값 | 발화 횟수 | 출처 확인 상태 |
|---|---|---:|---:|---|
| saju | ten_god / 정인 / discovery / receptivity | 0.60 | 1 | classical / verified |
| saju | element / fire / encounter / activation | 0.40 | 1 | classical / verified |
| saju | element / metal / opportunity / clarity | 0.40 | 1 | classical / verified |
| saju | natal_balance / deficient_element_active / opportunity / flow | 0.30 | 1 | no_external_basis / pending |
| astrology | planet / uranus / discovery / expansion | 0.80 | 1 | modern / verified |
| astrology | planet / mars / discovery / activation | 0.55 | 4 | modern / verified |
| astrology | planet / jupiter / opportunity / expansion | 0.80 | 1 | modern / verified |
| astrology | planet / moon / encounter / receptivity | 0.60 | 2 | modern / verified |
| astrology | planet / saturn / opportunity / grounding | 0.55 | 1 | modern / verified |
| astrology | planet / venus / encounter / receptivity | 0.75 | 1 | modern / verified |
| astrology | planet / neptune / encounter / flow | 0.50 | 1 | modern / verified |
| astrology | planet / mercury / discovery / clarity | 0.70 | 1 | modern / verified |
| astrology | element / air / discovery / clarity | 0.40 | 1 | modern / verified |
| astrology | element / water / encounter / receptivity | 0.40 | 1 | modern / verified |

사주의 정인은 [『淵海子平』 「論印綬」](https://www.chinese-classics.org/read/shushu/mingli/yuan-hai-zi-ping/001)의
생조·도움이라는 의미에 한정해 근거를 연결했다. 학습과 발견이라는 분류는 별도 설계다.
불과 금은 [『尚書』 「洪範」 五行段](https://ctext.org/shang-shu/great-plan/zh)에 서술된
성질을 참고했다. 특히 금의 가공·변형에서 `clarity`를 도출하는 것은 프로젝트의 비유다.
그 고전이 명료함 점수나 거리 선택을 제시한다고 해석하지 않는다.

점성술의 기본 출처는 CSV에 기재한 Michael R. Meyer, Robert Hand, Astrodienst의 현대 해석이다.
이 열들과 `basis_type=modern`은 유지하고, 아래처럼 고전 근거를 별도 열에 병기했다.
기호를 일일 경험 점수로 바꾸고 두 체계를 같은 축에 놓는 작업은 프로젝트 설계다.

## wood 출처 재검토

후보인 『尚書』 「洪範」의 목에 대한 성질 서술만으로 경험적 확장을 바로 도출하기는 어렵다.
이번에는 [『禮記』 「月令」의 孟春之月](https://www.chinese-classics.org/read/confucius/li-ji/li-ji-yue-ling)을
확인했다. 이 절은 입춘을 목과 연결하고 같은 계절의 초목이 싹트는 모습을 서술한다.
따라서 **봄·목·생장의 연관**을 `source_claim`으로 제한해 `classical / verified`로 갱신했다.
일진의 목을 `discovery / expansion`에 연결하거나 숫자 `0.40`을 부여하는 부분은 초기 설계다.
이 날짜에는 wood 규칙이 발화하지 않으므로 이 출처 수정은 비교 경로에 영향을 주지 않는다.

## 점성술의 고전 근거 병기

추가한 열은 `classical_reference`, `classical_source_claim`,
`classical_mapping_limit`, `classical_verification_status`다.
기존 modern 근거와 그 확인 상태는 그대로 둔다.

검토한 고전은 Ptolemy 『Tetrabiblos』의 F. E. Robbins 영어 번역(Loeb Classical Library, 1940)이다.
이것은 고전 본문의 번역에 근거한 분류이며, 번역 연도를 이유로 현대 점성술 이론으로 분류하지 않는다.
William Lilly 원문은 이번 결과의 확인 근거로 사용하지 않았다.

| 우선 규칙 | 확인 범위 | 고전 메타데이터 상태 |
|---|---|---|
| moon | III.13 도입부: 감각적 반응의 부분적 배경 | verified |
| mercury | III.13 도입부와 수성 단락: 이성·학습의 부분적 배경 | verified |
| venus | III.13 금성 단락: 애정·호감의 부분적 배경 | verified |
| mars | III.13 화성 단락: 활동성의 부분적 배경 | verified |
| jupiter | I.4–5: 생육·길성의 부분적 배경 | verified |
| saturn | III.13 토성 단락: 사고·근면의 부분적 배경 | verified |
| uranus | I.4–5의 행성 목록에 이 행성의 해석이 없음 | pending |
| neptune | I.4–5의 행성 목록에 이 행성의 해석이 없음 | pending |
| air | I.18에 삼각군은 있으나 사고·명료의 직접 대응 미확인 | pending |
| water | I.18에 삼각군은 있으나 감수성·수용의 직접 대응 미확인 | pending |

관련 본문: [I.4–5 및 I.18](https://penelope.uchicago.edu/thayer/e/roman/texts/ptolemy/tetrabiblos/1b%2A.html),
[III.13](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/3D%2A.html).
고전의 행성별 성향은 배치·지배·상호 관계의 조건을 전제한다.
`verified`인 6개도 CSV의 `classical_source_claim`에 적힌 제한된 의미만 확인한 것이며,
조건을 제거한 일일 경험 분류나 항상 양수인 가중치의 근거로 확대하지 않는다.
특히 토성의 단일 목적 지향과 근면을 현대적 구조·안정 전체와 동일시하지 않는다.

천왕성과 해왕성은 각각 1781년과 1846년에 행성으로 발견되었다.
두 요청 고전보다 뒤의 발견이라는 점은 [NASA JPL의 행성 발견 기록](https://ssd.jpl.nasa.gov/planets/discovery.html)으로 대조했다.
이 기록은 연대를 확인하는 자료이며 점성술적 의미의 고전 근거는 아니다.
이 두 행성에 다른 행성의 고전 상징을 대신 붙이지 않았다.
공기·물의 삼각군 분류가 있다는 사실 역시 현대 심리적 의미의 직접 근거가 되지 않으므로
두 행의 고전 의미 확인 상태는 `pending`으로 유지한다.

## 체계별 경로 비교 결과

2026-07-21에 동일한 끝점과 거리 데이터로 사주만, 점성술만, 결합 경로를 생성했다.
실행 코드: [`engine/compare_reading_routes.py`](../engine/compare_reading_routes.py).
상세 수치와 재실행 명령: [비교 보고서](../outputs/comparison_2026-07-21/comparison.md).

세 경로는 모두 12개 구간, 1406.4m이며 구간 순서까지 동일하다.
결합과 점성술만의 길이 Jaccard 및 결합 경로 포함률은 모두 100%다.
사주만의 경로도 같으므로 이것만으로 점성술이 경로 선택을 지배했다고 결론내릴 수 없다.

중간 반올림을 제외한 식 `C=0.5S+0.5A`의 최종 거리 가중치 총량은
**사주 31.7805% / 점성술 68.2195%**로 분해된다.
이는 체계별 투영 총량이 다르기 때문이며 경로 선택에 대한 인과 기여율은 아니다.
기존 엔진의 3자리·4자리 반올림 잔차는 어느 체계에도 배분하지 않고 보고서에 별도 표시했다.
분석에 사용한 거리 데이터는 README에 합성 샘플 격자로 명시되어 있다.

## 거리 변환의 계산 범위

[`quality_street_matrix.csv`](quality_street_matrix.csv)는 6개 경험 성질 × 8개 거리 속성의
계수 행렬이다. 설명 열을 추가하지 않고 숫자 행렬을 그대로 유지한다.
이 절 이후의 이유는 현재 계수에 부여한 **프로젝트의 설계 해석과 검토 가설**이다.
원래 작성자의 의도를 확인한 기록이나 문헌·사용자 실험에서 도출한 계수가 아니다.

계산은 다음과 같다.

```text
Q[q] = combined.quality[q]
u[s] = Σ_q Q[q] × M[q,s]
w[s] = u[s] / Σ_s u[s]           # 이후 소수점 4자리 반올림
luck(segment) = Σ_s w[s] × segment.qualities[s]
cost(segment) = length_m × (1.6 − luck(segment))
```

이 날짜의 경험 성질 점수는 다음과 같다. 설명에서 강조하는 상위 2개 성질만이 아니라
**6개 성질 모두** 행렬 계산에 들어간다.

| 성질 | Q[q] | 양의 기여가 있는 계수 수 |
|---|---:|---:|
| receptivity | 0.595 | 8 |
| activation | 0.469 | 8 |
| clarity | 0.384 | 8 |
| expansion | 0.355 | 8 |
| flow | 0.253 | 8 |
| grounding | 0.083 | 8 |

모든 Q[q]와 행렬 계수가 양수이므로 **48개 계수가 전부 우선 작성 대상**이다.
기준 경로에도 거리 속성 8종 각각에 양의 값이 있는 구간이 존재한다.
아래는 Q[q]가 큰 성질부터 정리했다. 이 순서는 개별 계수의 한계효과 순위를 뜻하지 않는다.

예를 들어 `expansion → open_sky`의 정규화 전 기여는 `0.355 × 0.80 = 0.284`다.
전체 정규화 분모는 `7.89805`이며 이 항의 정규화 후 몫은 약 `0.03596`이다.
다른 성질의 기여까지 합친 `open_sky`의 최종 가중치는 `0.1469`다.
정규화 때문에 한 계수를 바꾸면 다른 거리 속성의 최종 가중치도 달라진다.
행별 계수 합도 서로 다르므로 Q[q]의 크기만으로 성질별 최종 영향력을 판단하지 않는다.

## receptivity → 거리 속성

설계 방향: 주변의 분위기를 받아들이고 타인과 머무를 여지를 갖는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.60 | 식생의 모습과 변화를 살펴보는 환경을 수용의 경험에 연결해 중간 이상으로 반영한다. |
| water | 0.80 | 물의 표면과 움직임을 관찰하는 경험을 주요 공간적 비유로 선택한다. 수 오행을 보충한다는 처방을 뜻하지 않는다. |
| sunlight | 0.20 | 밝기는 보조 조건으로 두고 높은 일조량 자체를 수용성의 핵심으로 삼지 않는다. |
| open_sky | 0.30 | 주변을 바라볼 여지는 반영하되 시야의 넓이보다 머무르며 관찰하는 환경에 우선순위를 둔다. |
| quiet | 0.70 | 조용한 곳에서 주변에 주의를 두는 경험을 의도해 높은 선호를 부여한다. |
| vibrant | 0.20 | 사람과의 접점은 남기되 상업적 활기를 수용의 주된 공간 조건으로 삼지 않는다. |
| rest | 0.70 | 멈추어 관찰하거나 대화할 수 있는 좌석을 수용의 경험에 직접 연결한다. |
| culture | 0.40 | 전시와 문화적 표현을 받아들이는 접점을 보조적으로 반영한다. |

## activation → 거리 속성

설계 방향: 밖으로 움직이고 활동에 참여하는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.20 | 녹지는 활동의 배경으로 포함하되 이 성질의 주요 선택 기준으로 삼지 않는다. |
| water | 0.10 | 수변 관찰은 활동 참여와의 연결이 약하다고 보고 작은 선호만 부여한다. |
| sunlight | 0.90 | 밝고 드러난 거리라는 이미지를 외향적 활동의 공간적 비유로 선택한다. 일조의 효과를 측정한 값은 아니다. |
| open_sky | 0.50 | 개방된 환경을 활동의 배경으로 반영하되 실제 참여 지점을 대신하는 핵심 지표로 삼지 않는다. |
| quiet | 0.05 | 조용함을 활성의 주요 목표로 삼지 않아 거의 중립에 가깝게 둔다. 소음을 선호하는 음의 계수는 아니다. |
| vibrant | 1.00 | 상점과 활동의 접점이 있는 거리를 밖으로 나서는 경험의 가장 직접적인 지표로 선택한다. |
| rest | 0.10 | 좌석은 보조적인 머무름 가능성으로 남기고 활동의 중심 지표로 두지 않는다. |
| culture | 0.40 | 문화시설을 방문하거나 참여할 수 있는 장소로 해석해 보조 선호를 부여한다. |

## clarity → 거리 속성

설계 방향: 주변을 살피고 생각을 정리하는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.30 | 식생을 관찰 대상으로 포함하되 녹지량이 명료함을 직접 측정한다고 보지 않는다. |
| water | 0.30 | 물을 바라보는 상황을 보조적인 관찰 경험으로 포함한다. |
| sunlight | 0.60 | 거리의 모습을 살피는 경험을 밝은 환경에 대응시켜 중간 이상으로 반영한다. |
| open_sky | 0.90 | 시야가 열리는 이미지를 명료함의 핵심 공간 비유로 선택한다. 실제 길찾기 가독성과 같은 지표는 아니다. |
| quiet | 0.60 | 생각을 정리할 때 조용한 거리를 선택하도록 의도해 중간 이상으로 반영한다. |
| vibrant | 0.30 | 도시의 정보를 접할 여지는 남기되 높은 상업적 활기를 최우선으로 삼지 않는다. |
| rest | 0.30 | 멈추어 생각할 가능성을 보조적으로 반영한다. |
| culture | 0.50 | 정보를 접하고 해석할 수 있는 장소로 문화시설을 포함한다. |

## expansion → 거리 속성

설계 방향: 시야와 탐색의 범위를 넓히는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.70 | 공원과 식생이 있는 환경을 탐색의 대상으로 강조한다. 녹지량이 경험의 다양성을 직접 측정한다는 뜻은 아니다. |
| water | 0.40 | 수변을 탐색할 환경의 한 종류로 포함하되 시야가 열린 정도는 open_sky로 따로 반영한다. |
| sunlight | 0.50 | 드러난 외부 환경이라는 이미지를 보조적으로 반영한다. |
| open_sky | 0.80 | 넓어진 시야를 확장의 주요 공간적 비유로 선택한다. |
| quiet | 0.20 | 조용함은 허용하되 탐색 범위를 넓히는 경험의 중심 조건으로 두지 않는다. |
| vibrant | 0.50 | 상점과 도시 활동의 접점을 탐색 대상으로 포함한다. |
| rest | 0.20 | 머무를 여지는 남기되 탐색보다 우선하지 않도록 낮게 둔다. |
| culture | 0.60 | 문화시설을 새로운 내용과 만나는 장소로 선택해 중간 이상으로 반영한다. |

## flow → 거리 속성

설계 방향: 변화를 따라가고 유연하게 주변과 연결되는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.50 | 식생이 이어지는 모습을 흐름의 보조적 이미지로 선택한다. 현재 green 점수는 실제 연속성을 측정하지 않는다. |
| water | 0.90 | 물의 움직임을 흐름의 가장 직접적인 공간적 비유로 선택한다. 수변의 경로 연결성을 측정한 값은 아니다. |
| sunlight | 0.30 | 밝기를 배경 조건으로 포함하되 흐름의 주요 기준으로 두지 않는다. |
| open_sky | 0.40 | 시선이 주변으로 이어질 여지를 보조적으로 반영한다. 실제 보행 동선의 연속성과 구별한다. |
| quiet | 0.50 | 자신의 속도로 주변을 살피는 경험을 의도해 조용함에 중간 선호를 부여한다. |
| vibrant | 0.40 | 도시 활동과 느슨하게 접촉하는 경험을 포함하되 활기의 극대화를 목표로 삼지 않는다. |
| rest | 0.30 | 이동과 머무름 사이에서 선택할 수 있도록 좌석을 보조적으로 반영한다. |
| culture | 0.30 | 이동 중 문화적 표현을 접하는 가능성을 보조적으로 포함한다. |

## grounding → 거리 속성

설계 방향: 잠시 머무르고 일상의 기반을 느끼는 경험.

| 거리 속성 | 초기 설계값 | 설계 이유 |
|---|---:|---|
| green | 0.70 | 나무와 식생이 있는 환경을 안정의 공간적 이미지로 선택한다. |
| water | 0.30 | 물가 관찰을 보조적으로 포함하되 머무를 수 있는 조건에 더 큰 우선순위를 둔다. |
| sunlight | 0.30 | 밝기는 배경 조건으로 남기고 높은 일조를 안정의 핵심 기준으로 삼지 않는다. |
| open_sky | 0.20 | 시야 확장보다 머무름을 강조하므로 낮은 선호를 부여한다. 폐쇄된 환경을 요구하는 음의 계수는 아니다. |
| quiet | 0.70 | 조용한 곳에 머무르는 경험을 의도해 높은 선호를 부여한다. |
| vibrant | 0.20 | 도시 활동과의 접점은 남기되 높은 상업적 활기를 주된 목표로 두지 않는다. |
| rest | 0.90 | 앉아서 머무를 수 있는 좌석을 안정의 가장 직접적인 공간 조건으로 선택한다. |
| culture | 0.30 | 머무를 장소의 한 종류로 문화시설을 보조적으로 포함한다. |

## 수치 검증과 다음 검토

현재 기록은 의미와 설계 판단을 분리하는 작업이다. 숫자를 조정하거나 문헌으로 숫자를
정당화하지 않는다. `weight` / `base_weight`뿐 아니라 신호 강도 계수, 출생 행성 배율,
임계값, 상위 애스펙트 수, 포화 함수, 50:50 결합, 경로 비용의 `1.6`도 구현에서 정한
초기 설계 설정이다.

문헌 확인이 끝난 항목에도 경험 분류와 공간 변환에 대한 사용자 검토는 별도로 필요하다.
추후에는 한 규칙·계수를 바꾸었을 때 거리 가중치와 선택 경로가 어떻게 달라지는지 비교하고,
수용·확장 등의 안내와 실제 보행 경험이 부합하는지 검토한다.

이번 CSV의 추가 열은 출처 관리용이다. 현재 엔진은 이 열을 점수 계산에 사용하지 않으며,
`evidence`와 `llm_payload`에도 자동으로 전달하지 않는다.
