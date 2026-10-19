"use strict";

const API = {
  health: "/api/health",
  places: "/api/places",
  optimize: "/api/optimize",
};

const MAX_INTERMEDIATES = 10;
const DEFAULT_CENTER = [39.92, 116.4];

const FALLBACK_CITIES = [
  {
    id: "beijing",
    name: "北京",
    center: [39.92, 116.4],
    places: [
      { id: "tiananmen", name: "天安门广场", lat: 39.9087, lng: 116.3975 },
      { id: "forbidden-city", name: "故宫博物院", lat: 39.9163, lng: 116.3972 },
      { id: "jingshan", name: "景山公园", lat: 39.9251, lng: 116.3967 },
      { id: "beihai", name: "北海公园", lat: 39.9254, lng: 116.3891 },
      { id: "shichahai", name: "什刹海", lat: 39.9403, lng: 116.383 },
      { id: "nanluoguxiang", name: "南锣鼓巷", lat: 39.9376, lng: 116.4032 },
    ],
  },
];

const state = {
  origin: null,
  destination: null,
  intermediates: [],
  travelMode: "DRIVE",
  optimize: true,
  provider: "auto",
  cities: [],
  activeCityId: null,
  sampleIndex: 0,
  pickTarget: null,
  editIntermediateIndex: null,
  pickingOnMap: false,
  mapPickCounter: 0,
  result: null,
  health: null,
  placesLoaded: false,
  busy: false,
};

const $ = (selector) => document.querySelector(selector);

const originName = $("#originName");
const destinationName = $("#destinationName");
const intermediateList = $("#intermediateList");
const addStopBtn = $("#addStopBtn");
const stopCount = $("#stopCount");
const originBtn = $("#originBtn");
const destinationBtn = $("#destinationBtn");
const travelMode = $("#travelMode");
const optimizeToggle = $("#optimizeToggle");
const providerSelect = $("#providerSelect");
const providerHint = $("#providerHint");
const optimizeBtn = $("#optimizeBtn");
const buttonLabel = optimizeBtn.querySelector(".button-label");
const buttonMeta = $("#buttonMeta");
const spinner = optimizeBtn.querySelector(".spinner");
const resultSection = $("#resultSection");
const emptyState = $("#emptyState");
const resultTitle = $("#resultTitle");
const resultProvider = $("#resultProvider");
const totalDistance = $("#totalDistance");
const totalDuration = $("#totalDuration");
const totalStops = $("#totalStops");
const resultNote = $("#resultNote");
const fallbackNote = $("#fallbackNote");
const resultStops = $("#resultStops");
const sourceBadge = $("#sourceBadge");
const locateBtn = $("#locateBtn");
const mapStatus = $("#mapStatus");
const pickBanner = $("#pickBanner");
const cancelPickBtn = $("#cancelPickBtn");
const overlay = $("#pickerOverlay");
const pickerTitle = $("#pickerTitle");
const pickerClose = $("#pickerClose");
const cityTabs = $("#cityTabs");
const placeGrid = $("#placeGrid");
const mapPickBtn = $("#mapPickBtn");
const geolocateBtn = $("#geolocateBtn");
const coordForm = $("#coordForm");
const coordName = $("#coordName");
const coordLat = $("#coordLat");
const coordLng = $("#coordLng");
const toast = $("#toast");
const sampleBtn = $("#sampleBtn");
const rerunBtn = $("#rerunBtn");
const resetBtn = $("#resetBtn");

const DEFAULT_TILE_URL = "https://tile.openstreetmap.de/{z}/{x}/{y}.png";
const DEFAULT_TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const map = L.map("map", {
  zoomControl: false,
  attributionControl: false,
}).setView(DEFAULT_CENTER, 12);

L.control.zoom({ position: "bottomright" }).addTo(map);

const attributionControl = L.control({ position: "bottomright" });
attributionControl.onAdd = () => {
  const container = L.DomUtil.create("div", "map-attribution leaflet-control");
  container.innerHTML = `
    <details>
      <summary aria-label="查看地图署名" title="地图署名">
        <span id="mapAttributionLabel">© 署名</span>
      </summary>
      <div class="map-attribution-body" id="mapAttributionBody"></div>
    </details>
  `;
  L.DomEvent.disableClickPropagation(container);
  L.DomEvent.disableScrollPropagation(container);
  return container;
};
attributionControl.addTo(map);

let baseLayer = null;
let baseLayerUrl = "";
let tileErrorShown = false;

function updateMapAttribution() {
  const body = document.getElementById("mapAttributionBody");
  if (!body) return;
  const attribution =
    state.health?.map_tile_attribution || DEFAULT_TILE_ATTRIBUTION;
  body.innerHTML = attribution;

  const label = document.getElementById("mapAttributionLabel");
  if (!label) return;
  if (attribution.includes("OpenStreetMap")) {
    label.textContent = "© OpenStreetMap";
  } else if (attribution.includes("Esri")) {
    label.textContent = "© Esri";
  } else {
    label.textContent = "© 署名";
  }
}

function applyMapTiles() {
  const health = state.health || {};
  const url = health.map_tile_url || DEFAULT_TILE_URL;
  const maxZoom = Number(health.map_tile_max_zoom) || 19;

  if (!baseLayer || baseLayerUrl !== url) {
    if (baseLayer) map.removeLayer(baseLayer);

    baseLayerUrl = url;
    tileErrorShown = false;
    baseLayer = L.tileLayer(url, { maxZoom }).addTo(map);
    baseLayer.on("tileerror", () => {
      if (tileErrorShown) return;
      tileErrorShown = true;
      showMapStatus("底图加载失败，路线仍可正常显示", 6000);
    });
  }
  updateMapAttribution();
}

applyMapTiles();

const previewLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const meLayer = L.layerGroup().addTo(map);

let toastTimer = null;
let statusTimer = null;
let lastFocused = null;
let resizeTimer = null;

const HTML_ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => HTML_ESCAPES[character]);
}

function showToast(message, kind) {
  toast.textContent = message;
  toast.className = "toast" + (kind === "error" ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.add("hidden");
  }, 4600);
}

function showMapStatus(message, duration = 4200) {
  mapStatus.textContent = message;
  mapStatus.classList.remove("hidden");
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    mapStatus.classList.add("hidden");
  }, duration);
}

function hideMapStatus() {
  clearTimeout(statusTimer);
  mapStatus.classList.add("hidden");
}

function formatDistance(meters) {
  if (!Number.isFinite(meters) || meters < 0) return "—";
  if (meters < 1000) return `${Math.round(meters)} m`;
  const kilometers = meters / 1000;
  return `${kilometers.toFixed(kilometers < 10 ? 1 : 0)} km`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

function setStopName(element, place, placeholder) {
  if (place) {
    element.textContent = place.name;
    element.classList.remove("placeholder");
  } else {
    element.textContent = placeholder;
    element.classList.add("placeholder");
  }
}

function isSamePlace(a, b) {
  return (
    Math.abs(Number(a.lat) - Number(b.lat)) < 0.000001 &&
    Math.abs(Number(a.lng) - Number(b.lng)) < 0.000001
  );
}

function makeIcon(label, kind) {
  return L.divIcon({
    className: "pin-marker",
    html: `<span class="pin ${kind}"><span>${escapeHtml(label)}</span></span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

function renderStops() {
  setStopName(originName, state.origin, "选择起点");
  setStopName(destinationName, state.destination, "选择终点");

  intermediateList.innerHTML = state.intermediates
    .map(
      (place, index) => `
        <div class="stop-row">
          <span class="stop-dot stop" aria-hidden="true">${index + 1}</span>
          <button
            type="button"
            class="stop-main"
            data-edit-intermediate="${index}"
            aria-label="编辑途经点 ${index + 1}"
          >
            <span class="stop-label">途经点 ${index + 1}</span>
            <span class="stop-name">${escapeHtml(place.name)}</span>
          </button>
          <button
            type="button"
            class="remove-stop"
            data-remove="${index}"
            aria-label="删除途经点 ${index + 1}"
          >×</button>
        </div>
      `,
    )
    .join("");

  stopCount.textContent = `${state.intermediates.length} / ${MAX_INTERMEDIATES}`;
  addStopBtn.disabled = state.intermediates.length >= MAX_INTERMEDIATES;
  buttonMeta.textContent = `${state.intermediates.length} 个途经点`;
}

function renderPreview() {
  previewLayer.clearLayers();
  routeLayer.clearLayers();

  const ordered = [
    state.origin,
    ...state.intermediates,
    state.destination,
  ].filter(Boolean);
  if (!ordered.length) {
    map.setView(DEFAULT_CENTER, 12);
    return;
  }

  const latlngs = ordered.map((place) => [Number(place.lat), Number(place.lng)]);
  if (latlngs.length > 1) {
    L.polyline(latlngs, {
      color: "#e4572e",
      weight: 3,
      opacity: 0.55,
      dashArray: "7 9",
      lineCap: "round",
    }).addTo(previewLayer);
  }

  if (state.origin) {
    L.marker([state.origin.lat, state.origin.lng], {
      icon: makeIcon("起", "start"),
      title: state.origin.name,
    }).addTo(previewLayer);
  }
  state.intermediates.forEach((place, index) => {
    L.marker([place.lat, place.lng], {
      icon: makeIcon(String(index + 1), "stop"),
      title: place.name,
    }).addTo(previewLayer);
  });
  if (state.destination) {
    L.marker([state.destination.lat, state.destination.lng], {
      icon: makeIcon("终", "end"),
      title: state.destination.name,
    }).addTo(previewLayer);
  }

  if (latlngs.length > 1) {
    map.fitBounds(L.latLngBounds(latlngs), {
      paddingTopLeft: [34, 96],
      paddingBottomRight: [34, 44],
      maxZoom: 15,
    });
  } else {
    map.setView(latlngs[0], 14);
  }
}

function drawResult(data) {
  previewLayer.clearLayers();
  routeLayer.clearLayers();

  const latlngs = (data.geometry || [])
    .map(([lng, lat]) => [Number(lat), Number(lng)])
    .filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng));

  if (latlngs.length > 1) {
    L.polyline(latlngs, {
      color: "#ffffff",
      weight: 10,
      opacity: 0.9,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(routeLayer);
    L.polyline(latlngs, {
      color: "#e4572e",
      weight: 5,
      opacity: 0.96,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(routeLayer);
  }

  let intermediateNumber = 0;
  data.stops.forEach((stop) => {
    let label;
    let kind;
    if (stop.role === "origin") {
      label = "起";
      kind = "start";
    } else if (stop.role === "destination") {
      label = "终";
      kind = "end";
    } else {
      intermediateNumber += 1;
      label = String(intermediateNumber);
      kind = "stop";
    }

    const marker = L.marker([stop.lat, stop.lng], {
      icon: makeIcon(label, kind),
      title: stop.name,
      zIndexOffset: kind === "stop" ? 0 : 1000,
    }).addTo(routeLayer);

    const legText =
      stop.role === "origin"
        ? "行程起点"
        : `上一站到此 ${formatDistance(stop.leg_distance_meters)} · ${formatDuration(
            stop.leg_duration_seconds,
          )}`;
    marker.bindPopup(
      `<strong>${escapeHtml(stop.name)}</strong><br><span>${legText}</span>`,
    );
  });

  if (latlngs.length > 1) {
    map.fitBounds(L.latLngBounds(latlngs), {
      paddingTopLeft: [34, 96],
      paddingBottomRight: [34, 44],
      maxZoom: 15,
    });
  } else if (data.stops.length) {
    map.setView([data.stops[0].lat, data.stops[0].lng], 14);
  }
  setTimeout(() => map.invalidateSize(), 120);
}

function renderResult(data) {
  resultSection.classList.remove("hidden");
  emptyState.classList.add("hidden");

  resultTitle.textContent = data.optimized
    ? `已优化为 ${data.stops.length} 站顺路行程`
    : `${data.stops.length} 站行程 · 保持输入顺序`;
  resultProvider.textContent = data.provider_label;
  resultProvider.className = `provider-chip ${data.provider}`;

  totalDistance.textContent = formatDistance(data.total_distance_meters);
  totalDuration.textContent = formatDuration(data.total_duration_seconds);
  totalStops.textContent = `${data.stops.length} 个`;
  resultNote.textContent = data.note || "";

  if (data.fallback_reason) {
    fallbackNote.textContent = `自动降级：${data.fallback_reason}`;
    fallbackNote.classList.remove("hidden");
  } else {
    fallbackNote.textContent = "";
    fallbackNote.classList.add("hidden");
  }

  let intermediateNumber = 0;
  resultStops.innerHTML = data.stops
    .map((stop) => {
      let label;
      let kind;
      let meta;
      let time;
      if (stop.role === "origin") {
        label = "起";
        kind = "start";
        meta = "行程起点";
        time = "—";
      } else if (stop.role === "destination") {
        label = "终";
        kind = "end";
        meta = `上一站 → 本站 ${formatDistance(
          stop.leg_distance_meters,
        )} · ${formatDuration(stop.leg_duration_seconds)}`;
        time = `累计 ${formatDuration(stop.cumulative_duration_seconds)}`;
      } else {
        intermediateNumber += 1;
        label = String(intermediateNumber);
        kind = "";
        meta = `上一站 → 本站 ${formatDistance(
          stop.leg_distance_meters,
        )} · ${formatDuration(stop.leg_duration_seconds)}`;
        time = `累计 ${formatDuration(stop.cumulative_duration_seconds)}`;
      }

      return `
        <li class="result-stop ${kind}">
          <span class="result-stop-dot">${label}</span>
          <div class="result-stop-main">
            <span class="result-stop-name">${escapeHtml(stop.name)}</span>
            <span class="result-stop-meta">${meta}</span>
          </div>
          <span class="result-stop-time">${time}</span>
        </li>
      `;
    })
    .join("");

  setTimeout(() => {
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 80);
}

function updateSourceBadgeFromHealth() {
  if (!state.health) {
    sourceBadge.textContent = "数据源检测中";
    sourceBadge.className = "source-badge";
    return;
  }
  if (state.health.google_configured) {
    sourceBadge.textContent = "Google 已配置";
  } else {
    sourceBadge.textContent = "OSRM 免费模式";
  }
  sourceBadge.className = "source-badge ready";
}

function updateSourceBadgeForResult(data) {
  const labels = {
    google: "Google 实时路况",
    osrm: "OSRM 真实道路",
    local: "本地模拟",
  };
  sourceBadge.textContent = labels[data.provider] || data.provider_label;
  sourceBadge.className = "source-badge ready";
}

function updateProviderHint() {
  const googleReady = Boolean(state.health && state.health.google_configured);
  let hint;

  if (state.provider === "local") {
    hint = "本地模拟：直线距离 + 平均速度估算，适合离线验证排序逻辑。";
  } else if (state.provider === "google") {
    hint = googleReady
      ? "Google Routes：使用真实路网与实时路况，按调用量计费。"
      : "Google Routes 需要在服务端配置 GOOGLE_MAPS_API_KEY。";
  } else if (state.provider === "osrm" && state.travelMode !== "DRIVE") {
    hint = "OSRM 公共演示服务仅支持驾车；步行/骑行请切换数据源或使用本地模拟。";
  } else if (state.provider === "osrm") {
    hint = "OSRM 公共演示服务：真实道路 + 行程顺序优化，公共实例不保证 SLA。";
  } else if (googleReady) {
    hint = "自动模式优先使用 Google Routes 实时路况，失败时回退到 OSRM / 本地模拟。";
  } else {
    hint = "自动模式使用 OSRM 公共演示服务；步行/骑行会回退到本地估算。";
  }

  providerHint.textContent = hint;
}

function invalidateResult() {
  state.result = null;
  resultSection.classList.add("hidden");
  emptyState.classList.remove("hidden");
  routeLayer.clearLayers();
  updateSourceBadgeFromHealth();
  renderPreview();
}

function setBusy(busy) {
  state.busy = busy;
  optimizeBtn.disabled = busy;
  buttonLabel.textContent = busy ? "正在规划路线…" : "开始优化行程";
  buttonMeta.classList.toggle("hidden", busy);
  spinner.classList.toggle("hidden", !busy);
}

function extractError(payload) {
  if (!payload) return "请求失败，请稍后重试。";
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => item.msg || JSON.stringify(item))
      .join("；");
  }
  return "请求失败，请稍后重试。";
}

async function runOptimize() {
  if (state.busy) return;
  if (!state.origin || !state.destination) {
    showToast("请先选择起点和终点。", "error");
    openPicker(!state.origin ? "origin" : "destination");
    return;
  }

  const payload = {
    origin: {
      name: state.origin.name,
      lat: state.origin.lat,
      lng: state.origin.lng,
    },
    destination: {
      name: state.destination.name,
      lat: state.destination.lat,
      lng: state.destination.lng,
    },
    intermediates: state.intermediates.map((place) => ({
      name: place.name,
      lat: place.lat,
      lng: place.lng,
    })),
    travel_mode: state.travelMode,
    optimize: state.optimize,
    provider: state.provider,
  };

  setBusy(true);
  hideMapStatus();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);

  try {
    const response = await fetch(API.optimize, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(extractError(data));
    }

    state.result = data;
    renderResult(data);
    drawResult(data);
    updateSourceBadgeForResult(data);
    showMapStatus(`已生成 ${data.stops.length} 个地点的路线`);
    if (data.fallback_reason) {
      showToast("实时路线暂不可用，已自动使用本地模拟。");
    }
  } catch (error) {
    if (error.name === "AbortError") {
      showToast("请求超时，请稍后重试或切换数据源。", "error");
    } else if (error instanceof TypeError) {
      showToast("无法连接服务器，请检查网络后重试。", "error");
    } else {
      showToast(error.message || "规划失败，请稍后重试。", "error");
    }
  } finally {
    clearTimeout(timeout);
    setBusy(false);
  }
}

function nearestCity(place) {
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  state.cities.forEach((city) => {
    if (!Array.isArray(city.center) || city.center.length < 2) return;
    const [lat, lng] = city.center;
    const distance =
      (Number(lat) - place.lat) ** 2 + (Number(lng) - place.lng) ** 2;
    if (distance < bestDistance) {
      bestDistance = distance;
      best = city;
    }
  });
  return best;
}

async function openPicker(target, intermediateIndex = null) {
  state.pickTarget = target;
  state.editIntermediateIndex =
    target === "intermediate" && Number.isInteger(intermediateIndex)
      ? intermediateIndex
      : null;

  const current =
    target === "origin"
      ? state.origin
      : target === "destination"
        ? state.destination
        : state.editIntermediateIndex !== null
          ? state.intermediates[state.editIntermediateIndex]
          : null;

  if (current) {
    const city = nearestCity(current);
    if (city) state.activeCityId = city.id;
  }

  pickerTitle.textContent =
    state.editIntermediateIndex !== null
      ? "编辑途经点"
      : target === "origin"
        ? "选择起点"
        : target === "destination"
          ? "选择终点"
          : "添加途经点";

  lastFocused = document.activeElement;
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
  document.documentElement.classList.add("picker-open");

  if (!state.placesLoaded) {
    await loadPlaces();
  }
  renderCityTabs();
  renderPlaces();
  setTimeout(() => pickerClose.focus(), 30);
}

function hidePicker() {
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
  document.documentElement.classList.remove("picker-open");
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus();
  }
  lastFocused = null;
}

function closePicker() {
  hidePicker();
  state.pickTarget = null;
  state.editIntermediateIndex = null;
}

function renderCityTabs() {
  cityTabs.innerHTML = "";
  state.cities.forEach((city) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "city-tab" + (city.id === state.activeCityId ? " active" : "");
    button.textContent = city.name;
    button.dataset.cityId = city.id;
    button.setAttribute("role", "tab");
    button.setAttribute(
      "aria-selected",
      city.id === state.activeCityId ? "true" : "false",
    );
    cityTabs.appendChild(button);
  });
}

function activeCity() {
  return (
    state.cities.find((city) => city.id === state.activeCityId) ||
    state.cities[0] ||
    null
  );
}

function renderPlaces() {
  placeGrid.innerHTML = "";
  const city = activeCity();
  if (!city || !Array.isArray(city.places) || !city.places.length) {
    const empty = document.createElement("p");
    empty.className = "place-empty";
    empty.textContent = "暂无可选地点，请手动输入坐标。";
    placeGrid.appendChild(empty);
    return;
  }

  city.places.forEach((place) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "place-option";
    button.dataset.placeId = place.id;

    const name = document.createElement("strong");
    name.textContent = place.name;

    const coords = document.createElement("small");
    coords.textContent = `${Number(place.lat).toFixed(4)}, ${Number(
      place.lng,
    ).toFixed(4)}`;

    button.append(name, coords);
    placeGrid.appendChild(button);
  });
}

function applyPlace(place, target = state.pickTarget) {
  if (!target) return;

  const normalized = {
    name: String(place.name || "").trim().slice(0, 80) || "自定义地点",
    lat: Number(place.lat),
    lng: Number(place.lng),
  };

  if (
    !Number.isFinite(normalized.lat) ||
    normalized.lat < -90 ||
    normalized.lat > 90 ||
    !Number.isFinite(normalized.lng) ||
    normalized.lng < -180 ||
    normalized.lng > 180
  ) {
    showToast("坐标不合法：纬度需在 -90~90，经度需在 -180~180。", "error");
    return;
  }

  const editIndex = state.editIntermediateIndex;

  if (target === "intermediate") {
    if (editIndex === null && state.intermediates.length >= MAX_INTERMEDIATES) {
      showToast(`最多添加 ${MAX_INTERMEDIATES} 个途经点。`, "error");
      return;
    }
    const duplicate = state.intermediates.some(
      (item, index) => index !== editIndex && isSamePlace(item, normalized),
    );
    if (duplicate) {
      showToast("该地点已经在途经点列表中。", "error");
      return;
    }
    if (editIndex !== null) {
      state.intermediates[editIndex] = normalized;
    } else {
      state.intermediates.push(normalized);
    }
  } else if (target === "origin") {
    state.origin = normalized;
  } else if (target === "destination") {
    state.destination = normalized;
  }

  state.pickTarget = null;
  state.editIntermediateIndex = null;
  hidePicker();
  renderStops();
  invalidateResult();
  showToast(`${normalized.name} 已加入行程`);
}

function removeIntermediate(index) {
  if (!Number.isInteger(index) || index < 0 || index >= state.intermediates.length) {
    return;
  }
  const [removed] = state.intermediates.splice(index, 1);
  renderStops();
  invalidateResult();
  showToast(`已移除${removed.name}`);
}

function startMapPick() {
  if (!state.pickTarget) return;
  hidePicker();
  state.pickingOnMap = true;
  pickBanner.classList.remove("hidden");
  map.getContainer().classList.add("picking");
  showMapStatus("点击地图上的位置即可加入行程", 6000);
}

function cancelMapPick() {
  state.pickingOnMap = false;
  state.pickTarget = null;
  state.editIntermediateIndex = null;
  pickBanner.classList.add("hidden");
  map.getContainer().classList.remove("picking");
  hideMapStatus();
}

function locate(onSuccess) {
  if (!navigator.geolocation) {
    showToast("当前浏览器不支持定位。", "error");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (position) => {
      onSuccess(position.coords.latitude, position.coords.longitude);
    },
    () => {
      showToast("定位失败，请检查浏览器定位权限。", "error");
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  );
}

async function loadHealth() {
  try {
    const response = await fetch(API.health);
    if (!response.ok) throw new Error("health request failed");
    state.health = await response.json();
    applyMapTiles();

    const googleOption = providerSelect.querySelector('option[value="google"]');
    if (googleOption) {
      if (state.health.google_configured) {
        googleOption.disabled = false;
        googleOption.textContent = "Google Routes";
      } else {
        googleOption.disabled = true;
        googleOption.textContent = "Google Routes（未配置）";
      }
    }

    updateSourceBadgeFromHealth();
    updateProviderHint();
  } catch {
    state.health = null;
    sourceBadge.textContent = "后端未连接";
    sourceBadge.className = "source-badge offline";
    showToast("无法连接后端服务，请刷新页面重试。", "error");
  }
}

async function loadPlaces() {
  if (state.placesLoaded) return state.cities;
  state.placesLoaded = true;

  try {
    const response = await fetch(API.places);
    if (!response.ok) throw new Error("places request failed");
    const payload = await response.json();
    state.cities =
      Array.isArray(payload.cities) && payload.cities.length
        ? payload.cities
        : FALLBACK_CITIES;
  } catch {
    state.cities = FALLBACK_CITIES;
    showToast("地点库加载失败，已载入内置北京示例。", "error");
  }

  state.activeCityId = state.cities[0]?.id || null;
  return state.cities;
}

function loadSample(cityIndex = state.sampleIndex, silent = false) {
  const cities = state.cities.length ? state.cities : FALLBACK_CITIES;
  if (!cities.length) return;

  const city = cities[cityIndex % cities.length];
  const places = Array.isArray(city.places) ? city.places : [];
  if (places.length < 2) return;

  state.sampleIndex = (cityIndex + 1) % cities.length;
  state.activeCityId = city.id;
  state.origin = { ...places[0] };
  state.destination = { ...places[Math.min(5, places.length - 1)] };
  state.intermediates = places
    .slice(1, Math.min(5, places.length - 1))
    .map((place) => ({ ...place }));
  state.result = null;
  state.pickTarget = null;
  state.editIntermediateIndex = null;

  renderStops();
  invalidateResult();

  if (!silent) {
    showToast(`已载入${city.name}示例路线`);
  }
}

async function init() {
  renderStops();
  updateProviderHint();

  await Promise.all([loadHealth(), loadPlaces()]);

  if (state.cities.length) {
    loadSample(0, true);
  } else {
    renderPreview();
  }
}

originBtn.addEventListener("click", () => openPicker("origin"));
destinationBtn.addEventListener("click", () => openPicker("destination"));
addStopBtn.addEventListener("click", () => openPicker("intermediate"));

document.querySelectorAll("[data-edit]").forEach((button) => {
  button.addEventListener("click", () => openPicker(button.dataset.edit));
});

intermediateList.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit-intermediate]");
  if (editButton) {
    openPicker("intermediate", Number(editButton.dataset.editIntermediate));
    return;
  }
  const removeButton = event.target.closest("[data-remove]");
  if (removeButton) {
    removeIntermediate(Number(removeButton.dataset.remove));
  }
});

cityTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-city-id]");
  if (!button) return;
  state.activeCityId = button.dataset.cityId;
  renderCityTabs();
  renderPlaces();
});

placeGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-place-id]");
  if (!button) return;
  const city = activeCity();
  if (!city) return;
  const place = city.places.find((item) => item.id === button.dataset.placeId);
  if (place) applyPlace(place);
});

travelMode.addEventListener("click", (event) => {
  const button = event.target.closest("[data-mode]");
  if (!button) return;
  state.travelMode = button.dataset.mode;
  travelMode.querySelectorAll("[data-mode]").forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", active ? "true" : "false");
  });
  updateProviderHint();
  invalidateResult();
});

optimizeToggle.addEventListener("change", () => {
  state.optimize = optimizeToggle.checked;
  invalidateResult();
});

providerSelect.addEventListener("change", () => {
  state.provider = providerSelect.value;
  updateProviderHint();
  invalidateResult();
});

document.querySelector("#routeForm").addEventListener("submit", (event) => {
  event.preventDefault();
  runOptimize();
});

sampleBtn.addEventListener("click", () => loadSample(state.sampleIndex));
rerunBtn.addEventListener("click", () => runOptimize());
resetBtn.addEventListener("click", () => {
  invalidateResult();
  showToast("已清空结果，可继续调整地点。");
});

pickerClose.addEventListener("click", closePicker);
overlay.addEventListener("click", (event) => {
  if (event.target === overlay) closePicker();
});

mapPickBtn.addEventListener("click", startMapPick);
cancelPickBtn.addEventListener("click", cancelMapPick);

geolocateBtn.addEventListener("click", () => {
  locate((lat, lng) => {
    applyPlace({ name: "我的位置", lat, lng });
  });
});

locateBtn.addEventListener("click", () => {
  locate((lat, lng) => {
    map.setView([lat, lng], 15);
    meLayer.clearLayers();
    L.circleMarker([lat, lng], {
      radius: 7,
      color: "#2c5ce6",
      weight: 3,
      fillColor: "#2c5ce6",
      fillOpacity: 0.3,
    }).addTo(meLayer);
    showMapStatus("已定位到当前位置");
  });
});

coordForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = coordName.value.trim() || "自定义地点";
  const lat = Number(coordLat.value);
  const lng = Number(coordLng.value);
  if (
    !Number.isFinite(lat) ||
    lat < -90 ||
    lat > 90 ||
    !Number.isFinite(lng) ||
    lng < -180 ||
    lng > 180
  ) {
    showToast("坐标不合法：纬度需在 -90~90，经度需在 -180~180。", "error");
    return;
  }
  applyPlace({ name, lat, lng });
  coordForm.reset();
});

map.on("click", (event) => {
  if (!state.pickingOnMap || !state.pickTarget) return;
  const target = state.pickTarget;
  const { lat, lng } = event.latlng;
  let name;
  if (target === "intermediate") {
    state.mapPickCounter += 1;
    name = `地图选点 ${state.mapPickCounter}`;
  } else if (target === "origin") {
    name = "地图选点 · 起点";
  } else {
    name = "地图选点 · 终点";
  }
  applyPlace({ name, lat, lng }, target);
  cancelMapPick();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!overlay.classList.contains("hidden")) {
    closePicker();
  } else if (state.pickingOnMap) {
    cancelMapPick();
  }
});

window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => map.invalidateSize(), 150);
});

init();
