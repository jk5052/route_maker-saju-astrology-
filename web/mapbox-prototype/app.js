// Lucky Path — Mapbox 프로토타입 (reference 무드: 다크 맵 + 라임 글로우 루트 + 화이트 시트)
// 레포 루트에서 `python -m http.server` 실행 후
// http://localhost:8000/web/mapbox-prototype/ 접속
// 토큰이 없으면 geojson을 SVG로 직접 투영해 그리는 폴백 모드로 동작한다.

const MAPBOX_TOKEN = "YOUR_MAPBOX_TOKEN_HERE"; // https://account.mapbox.com 에서 발급
const LIME = "#d7fb3f";
const WALK_M_PER_MIN = 80;

const QUALITY_LABELS = {
  green: "Greenery", water: "Water", sunlight: "Sunlight", open_sky: "Open Sky",
  quiet: "Quiet", vibrant: "Vibrancy", rest: "Rest", culture: "Culture",
};
const EVENT_LABELS = { encounter: "Encounter", opportunity: "Opportunity", discovery: "Discovery" };
const DAILY_QUALITY_LABELS = {
  activation: "Activation", receptivity: "Receptivity", clarity: "Clarity",
  expansion: "Expansion", grounding: "Grounding", flow: "Flow",
};
// 사주 엔진의 한글 간지 → 영어 표기
const STEM_EN = { "갑": "Jia", "을": "Yi", "병": "Bing", "정": "Ding", "무": "Wu",
  "기": "Ji", "경": "Geng", "신": "Xin", "임": "Ren", "계": "Gui" };
const BRANCH_EN = { "자": "Zi", "축": "Chou", "인": "Yin", "묘": "Mao", "진": "Chen",
  "사": "Si", "오": "Wu", "미": "Wei", "신": "Shen", "유": "You", "술": "Xu", "해": "Hai" };
const cap = (s) => s ? s[0].toUpperCase() + s.slice(1) : s;

// 파이널 3개 지표 — quality_street_matrix의 해당 컬럼과 오늘의 성질(6)의 가중평균으로 산출
const FINAL_METRICS = [
  { col: "green",    label: "Street-Tree Presence",  word: "Green" },
  { col: "quiet",    label: "Major-Road Separation", word: "Still" },
  { col: "open_sky", label: "Visual Openness",       word: "Open"  },
];

const ROUTES = {
  fastest: { url: "../../outputs/fastest_route.geojson", color: "#565a50", width: 2.5 },
  lucky: { url: "../../outputs/lucky_route.geojson", color: LIME, width: 4 },
};

const $ = (id) => document.getElementById(id);

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json();
}

async function fetchMatrix() {
  const res = await fetch("../../config/quality_street_matrix.csv");
  if (!res.ok) throw new Error(`quality_street_matrix.csv → ${res.status}`);
  const [head, ...rows] = (await res.text()).trim().split(/\r?\n/).map((l) => l.split(","));
  const cols = head.slice(1);
  const matrix = {};
  for (const r of rows)
    matrix[r[0]] = Object.fromEntries(cols.map((c, i) => [c, Number(r[i + 1])]));
  return matrix; // matrix[성질][거리품질] → 0~1
}

/* ── 공용 지오메트리 헬퍼 ─────────────────────────────────────────── */
function coordsOf(gj) {
  return gj.features.flatMap((f) => f.geometry.coordinates);
}

// 경위도 → 픽셀 투영 (equirectangular, 위도 보정)
function makeProjector(coords, w, h, pad) {
  const latMid = coords.reduce((s, c) => s + c[1], 0) / coords.length;
  const kx = Math.cos((latMid * Math.PI) / 180);
  const xs = coords.map((c) => c[0] * kx), ys = coords.map((c) => c[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min(
    (w - pad.left - pad.right) / (maxX - minX || 1e-9),
    (h - pad.top - pad.bottom) / (maxY - minY || 1e-9));
  const ox = pad.left + (w - pad.left - pad.right - (maxX - minX) * scale) / 2;
  const oy = pad.top + (h - pad.top - pad.bottom - (maxY - minY) * scale) / 2;
  return ([lon, lat]) => [
    ox + (lon * kx - minX) * scale,
    oy + (maxY - lat) * scale, // 북쪽이 위
  ];
}

const fmtKm = (m) => `${(m / 1000).toFixed(1)}`;

/* ── 시트(패널) 렌더 ─────────────────────────────────────────────── */
function bars(el, entries, labels) {
  const max = Math.max(...entries.map(([, v]) => v)) || 1;
  el.innerHTML = entries.map(([q, v]) => `
    <div class="bar-row">
      <span>${labels[q] ?? q}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(v / max) * 100}%"></div></div>
      <span class="val">${v.toFixed(3)}</span>
    </div>`).join("");
}

// 오늘의 성질 프로필로 가중평균한 0~1 절대 스코어
function metricScore(quality, matrix, col) {
  let num = 0, den = 0;
  for (const [q, v] of Object.entries(quality)) {
    if (matrix[q]) { num += v * matrix[q][col]; den += v; }
  }
  return den ? num / den : 0;
}

function renderCityReading(quality, matrix) {
  $("city-reading").innerHTML = FINAL_METRICS.map((m) => {
    const score = metricScore(quality, matrix, m.col);
    return `
    <div class="metric">
      <div class="metric-name">${m.label}</div>
      <div class="metric-row">
        <span class="metric-word">${m.word} — ${score.toFixed(2)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${score * 100}%"></div></div>
      </div>
    </div>`;
  }).join("");
}

function drawThumb(coords) {
  const project = makeProjector(coords, 64, 64, { top: 12, bottom: 12, left: 12, right: 12 });
  const pts = coords.map(project);
  const [x0, y0] = pts[0], [x1, y1] = pts[pts.length - 1];
  $("thumb").innerHTML = `
    <polyline class="lucky-line" points="${pts.map((p) => p.map((n) => n.toFixed(1)).join(",")).join(" ")}"/>
    <circle class="node" cx="${x0}" cy="${y0}" r="2.5"/>
    <circle class="node" cx="${x1}" cy="${y1}" r="2.5"/>`;
}

function renderSheet(reading, matrix, routeData) {
  const astro = reading.raw.astrology.signals;
  const saju = reading.raw.saju;

  const stem = saju.today.pillar.stem, branch = saju.today.pillar.branch;
  $("date").textContent =
    `${reading.date} · ${STEM_EN[stem] ?? stem}-${BRANCH_EN[branch] ?? branch} day · ` +
    `${cap(astro.transit_sun_sign)} · Moon: ${astro.moon_phase.name.replace(/_/g, " ")}`;
  $("sentence").textContent = reading.sentence;

  // 헤더 스탯: 거리·도보 시간·오늘의 유형
  const lucky = routeData.lucky.properties ?? {};
  const meters = lucky.total_length_m ?? 0;
  $("stat-distance").textContent = `${fmtKm(meters)} km`;
  $("stat-duration").textContent = `${Math.max(1, Math.round(meters / WALK_M_PER_MIN))} min`;
  $("stat-mode").textContent = EVENT_LABELS[reading.dominant_event] ?? reading.dominant_event;
  drawThumb(coordsOf(routeData.lucky));

  $("events").innerHTML = Object.entries(reading.combined.event)
    .sort((a, b) => b[1] - a[1])
    .map(([e, v]) => {
      const cls = e === reading.dominant_event ? "top" : "";
      return `<span class="event-chip ${cls}">${EVENT_LABELS[e] ?? e} ${v.toFixed(2)}</span>`;
    }).join("");

  renderCityReading(reading.combined.quality, matrix);

  bars($("daily-qualities"),
    Object.entries(reading.combined.quality).sort((a, b) => b[1] - a[1]),
    DAILY_QUALITY_LABELS);

  $("evidence").innerHTML = reading.evidence
    .slice(0, 5)
    .map((e) => `<li><span class="src">${e.source === "saju" ? "Saju" : "Astro"}</span> ${e.explanation} <span class="val">+${e.score}</span></li>`)
    .join("");

  for (const key of Object.keys(ROUTES)) {
    const stats = routeData[key].properties ?? {};
    $(`${key}-stat`).textContent =
      `${Math.round(stats.total_length_m ?? 0)}m · luck ${(stats.mean_luck ?? 0).toFixed(2)}`;
  }
}

function makeBubble(meters) {
  const el = document.createElement("div");
  el.className = "bubble";
  el.innerHTML = `${fmtKm(meters)}<small>km</small>`;
  return el;
}

/* ── 폴백 렌더 (Mapbox 토큰 없음): geojson → SVG 직접 투영 ────────── */
function renderFallback(routeData) {
  document.body.classList.add("no-map");
  const svg = $("fallback");
  const meters = routeData.lucky.properties?.total_length_m ?? 0;
  const bubble = makeBubble(meters);
  $("map").appendChild(bubble);

  const pad = { top: 150, bottom: 300, left: 60, right: 60 };
  const draw = () => {
    const w = innerWidth, h = innerHeight;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    const all = [...coordsOf(routeData.fastest), ...coordsOf(routeData.lucky)];
    const project = makeProjector(all, w, h, pad);
    const pts = (gj) => coordsOf(gj).map(project);

    const luckyPts = pts(routeData.lucky);
    const [sx, sy] = luckyPts[0], [ex, ey] = luckyPts[luckyPts.length - 1];
    const toStr = (p) => p.map((pt) => pt.map((n) => n.toFixed(1)).join(",")).join(" ");

    svg.innerHTML = `
      <g id="g-fastest"><polyline class="fastest-line" points="${toStr(pts(routeData.fastest))}"/></g>
      <g id="g-lucky">
        <polyline class="lucky-line" points="${toStr(luckyPts)}"/>
        <circle class="halo" cx="${sx}" cy="${sy}" r="10"/><circle class="node" cx="${sx}" cy="${sy}" r="4.5"/>
        <circle class="halo" cx="${ex}" cy="${ey}" r="10"/><circle class="node" cx="${ex}" cy="${ey}" r="4.5"/>
      </g>`;

    const [mx, my] = luckyPts[Math.floor(luckyPts.length / 2)];
    bubble.style.left = `${mx}px`;
    bubble.style.top = `${my}px`;
  };
  draw();
  addEventListener("resize", draw);

  for (const key of Object.keys(ROUTES)) {
    $(`show-${key}`).addEventListener("change", (e) => {
      const g = $(`g-${key}`);
      if (g) g.style.display = e.target.checked ? "" : "none";
      if (key === "lucky") bubble.style.display = e.target.checked ? "" : "none";
    });
  }
}

/* ── Mapbox 렌더 ─────────────────────────────────────────────────── */
function routeBounds(geojsons) {
  const bounds = new mapboxgl.LngLatBounds();
  for (const gj of geojsons)
    for (const c of coordsOf(gj)) bounds.extend(c);
  return bounds;
}

function initMapbox(routeData) {
  mapboxgl.accessToken = MAPBOX_TOKEN;
  const map = new mapboxgl.Map({
    container: "map",
    style: "mapbox://styles/mapbox/dark-v11",
    center: [-73.957, 40.714],
    zoom: 14,
  });

  map.on("load", () => {
    for (const [key, cfg] of Object.entries(ROUTES)) {
      map.addSource(key, { type: "geojson", data: routeData[key] });
      if (key === "lucky")
        map.addLayer({
          id: "lucky-glow", type: "line", source: key,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": LIME, "line-width": 14, "line-opacity": 0.3, "line-blur": 8 },
        });
      map.addLayer({
        id: key, type: "line", source: key,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": cfg.color, "line-width": cfg.width, "line-opacity": 0.95 },
      });
      $(`show-${key}`).addEventListener("change", (e) => {
        const vis = e.target.checked ? "visible" : "none";
        map.setLayoutProperty(key, "visibility", vis);
        if (key === "lucky") map.setLayoutProperty("lucky-glow", "visibility", vis);
      });
    }

    // 출발/도착 노드 + 중간 지점 거리 버블
    const luckyCoords = coordsOf(routeData.lucky);
    for (const c of [luckyCoords[0], luckyCoords[luckyCoords.length - 1]]) {
      const node = document.createElement("div");
      node.className = "map-node";
      new mapboxgl.Marker({ element: node }).setLngLat(c).addTo(map);
    }
    new mapboxgl.Marker({
      element: makeBubble(routeData.lucky.properties?.total_length_m ?? 0),
      anchor: "bottom", offset: [0, -12],
    }).setLngLat(luckyCoords[Math.floor(luckyCoords.length / 2)]).addTo(map);

    map.fitBounds(routeBounds(Object.values(routeData)),
      { padding: { top: 140, bottom: 280, left: 60, right: 60 } });

    // 세그먼트 클릭 → 품질 점수 팝업
    map.on("click", "lucky", (e) => {
      const p = e.features[0].properties;
      const rows = Object.keys(QUALITY_LABELS)
        .map((q) => `${QUALITY_LABELS[q]}: ${Number(p[q]).toFixed(2)}`).join("<br/>");
      new mapboxgl.Popup().setLngLat(e.lngLat)
        .setHTML(`<strong>Segment ${p.segment_id}</strong> · luck ${p.luck_score}<br/>${rows}`)
        .addTo(map);
    });
  });
}

/* ── 초기화 ──────────────────────────────────────────────────────── */
function wireSheet() {
  const sheet = $("sheet");
  const toggle = () => sheet.classList.toggle("open");
  $("sheet-head").addEventListener("click", (e) => {
    if (e.target.closest(".toggle")) return;
    toggle();
  });
  $("fab").addEventListener("click", toggle);
}

async function init() {
  wireSheet();

  const [reading, matrix] = await Promise.all([
    fetchJSON("../../engine/daily_reading.json"),
    fetchMatrix(),
  ]);
  const routeData = {};
  for (const key of Object.keys(ROUTES))
    routeData[key] = await fetchJSON(ROUTES[key].url);

  renderSheet(reading, matrix, routeData);

  // 사주×별자리 상세 분석 오버레이 (••• 버튼 / 시트 링크)
  const openChart = () => window.ChartView.show(reading.birth, reading.birth_time);
  $("open-chart").addEventListener("click", openChart);
  $("open-chart-2").addEventListener("click", openChart);
  $("chart-close").addEventListener("click", () => window.ChartView.hide());

  const hasToken = MAPBOX_TOKEN && !MAPBOX_TOKEN.startsWith("YOUR_");
  if (hasToken) initMapbox(routeData);
  else renderFallback(routeData);
}

init().catch((err) => {
  $("sheet").insertAdjacentHTML(
    "afterbegin",
    `<p class="load-error">Load failed: ${err.message}<br/>Make sure the HTTP server runs from the repo root and the engine/router have been run first.</p>`
  );
  console.error(err);
});
