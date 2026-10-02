# lucky_route.gh

기존 Williamsburg 수업 자료를 Python 반복 실험과 연결하는 방향은
[데이터 교환 설계](data_exchange.md)를 참고한다. 아래 구성은 현재 합성 샘플을 실행하는 예제다.

`.gh` 파일은 바이너리라서 Rhino/Grasshopper에서 직접 만들어 이 폴더에 저장해야 합니다.
핵심 로직은 전부 [lucky_route_ghpython.py](lucky_route_ghpython.py)에 있으므로,
정의(definition)는 아래처럼 얇게 구성하면 됩니다.

## 컴포넌트 구성

```
[File Path] segments_path ──┐
[File Path] reading_path ───┤
[Panel] origin "lon,lat" ───┤
[Panel] destination ────────┼──> [GhPython: lucky_route_ghpython.py] ──> fastest_pts ──> [PolyLine] ──> 미리보기(회색)
[File Path] out_dir ────────┤                                       ──> lucky_pts ────> [PolyLine] ──> 미리보기(금색)
[Button/Toggle] run ────────┘                                       ──> summary ─────> [Panel]
```

1. **GhPython 컴포넌트**를 놓고 입력을 `segments_path, reading_path, origin, destination, out_dir, run`
   (모두 *Item Access*, str/str/str/str/str/bool)으로, 출력을 `fastest_pts, lucky_pts, summary`로 설정.
2. 컴포넌트 안에 `lucky_route_ghpython.py` 내용을 그대로 붙여넣기.
3. `run`을 켜면 경로 계산과 동시에 `outputs/` 에 geojson·csv 3종이 저장됨.

## Rhino 없이 실행

같은 스크립트를 CLI로도 실행할 수 있어서 `.gh` 없이 전체 파이프라인 테스트가 가능합니다:

```bash
python grasshopper/lucky_route_ghpython.py --origin "-73.9990,40.7280" --dest "-73.9930,40.7340"
```

## 좌표계 주의

세그먼트 geojson은 WGS84(경위도)입니다. Rhino 화면에서 왜곡 없이 보려면
GhPython 출력 뒤에 스케일/투영(예: 간단히 x×cos(lat) 보정 또는 EPSG:2263 변환) 컴포넌트를 추가하세요.
저장되는 outputs geojson은 좌표 변환과 무관하게 항상 WGS84입니다.
