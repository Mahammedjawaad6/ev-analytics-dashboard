import { getAnalytics, parseCsv } from "./data.mjs";

const CHART_COLOR = "#5274df";
const state = { data: null, analytics: null, hoveredPoint: -1 };

const elements = {
  file: document.querySelector("#csv-file"),
  uploadPanel: document.querySelector("#upload-panel"),
  uploadButtonLabel: document.querySelector("#upload-button-label"),
  error: document.querySelector("#error-message"),
  status: document.querySelector("#dataset-status"),
  datasetName: document.querySelector("#dataset-name"),
  datasetUpdated: document.querySelector("#dataset-updated"),
  stock: document.querySelector("#metric-stock"),
  stockNote: document.querySelector("#metric-stock-note"),
  growth: document.querySelector("#metric-growth"),
  growthNote: document.querySelector("#metric-growth-note"),
  countries: document.querySelector("#metric-countries"),
  countriesNote: document.querySelector("#metric-countries-note"),
  year: document.querySelector("#metric-year"),
  yearNote: document.querySelector("#metric-year-note"),
  unit: document.querySelector("#unit-select"),
  trendCaption: document.querySelector("#trend-caption"),
  chart: document.querySelector("#trend-chart"),
  chartEmpty: document.querySelector("#trend-empty"),
  chartTooltip: document.querySelector("#chart-tooltip"),
  rankingCaption: document.querySelector("#ranking-caption"),
  search: document.querySelector("#country-search"),
  rankingEmpty: document.querySelector("#ranking-empty"),
  table: document.querySelector("#country-table"),
  countryRows: document.querySelector("#country-rows"),
};

function selectedUnitSeries() {
  const unit = elements.unit.value;
  return [...state.analytics.globalByYearUnit.entries()]
    .filter(([key]) => key.startsWith(`${unit}\u0000`))
    .map(([key, value]) => ({
      year: Number(key.slice(key.lastIndexOf("\u0000") + 1)),
      value,
    }))
    .sort((a, b) => a.year - b.year);
}

function formatCompact(value) {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (absolute >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function formatMillions(value) {
  return `${(value / 1_000_000).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })}M`;
}

function setMetrics() {
  const series = selectedUnitSeries();
  const latest = series[series.length - 1];
  const previous = series.length > 1 ? series[series.length - 2] : null;
  const growth =
    previous && previous.value !== 0
      ? ((latest.value - previous.value) / previous.value) * 100
      : null;
  const latestCountries = state.analytics.countriesByYear.get(state.analytics.latestYear);

  elements.stock.textContent = formatMillions(latest.value);
  elements.stockNote.textContent = `${latest.year} · ${elements.unit.value}`;
  elements.growth.textContent = growth === null ? "—" : `${growth.toFixed(1)}%`;
  elements.growthNote.textContent = previous
    ? `${previous.year} to ${latest.year}`
    : "Need two years to calculate";
  elements.countries.textContent = new Intl.NumberFormat().format(latestCountries.size);
  elements.countriesNote.textContent = `In ${state.analytics.latestYear}`;
  elements.year.textContent = String(latest.year);
  elements.yearNote.textContent = `${state.data.length.toLocaleString()} source rows`;
  elements.trendCaption.textContent = `Historical electric car stock · ${elements.unit.value}`;
  elements.rankingCaption.textContent = `Top countries by electric car stock · ${state.analytics.latestYear}`;
}

function drawChart() {
  const canvas = elements.chart;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;
  const series = selectedUnitSeries();
  elements.chartEmpty.hidden = series.length > 0;
  if (!series.length) return;

  const pad = { top: 17, right: 20, bottom: 30, left: 52 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(...series.map((point) => point.value));
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(maxValue, 1)));
  const step = magnitude / 2;
  const axisMax = Math.ceil(maxValue / step) * step || 1;
  const x = (index) =>
    pad.left + (series.length === 1 ? plotWidth / 2 : (index / (series.length - 1)) * plotWidth);
  const y = (value) => pad.top + plotHeight - (value / axisMax) * plotHeight;

  context.font = "10px DM Sans, Segoe UI, sans-serif";
  context.textBaseline = "middle";
  context.strokeStyle = "#edf0f5";
  context.lineWidth = 1;
  context.fillStyle = "#99a4b5";
  const ticks = 4;
  for (let tick = 0; tick <= ticks; tick += 1) {
    const value = (axisMax / ticks) * tick;
    const tickY = y(value);
    context.beginPath();
    context.moveTo(pad.left, Math.round(tickY) + 0.5);
    context.lineTo(width - pad.right, Math.round(tickY) + 0.5);
    context.stroke();
    context.textAlign = "right";
    context.fillText(formatCompact(value), pad.left - 10, tickY);
  }

  const labelCount = Math.min(series.length, 6);
  const labelIndexes = new Set();
  if (labelCount === 1) labelIndexes.add(0);
  else {
    for (let i = 0; i < labelCount; i += 1) {
      labelIndexes.add(Math.round((i / (labelCount - 1)) * (series.length - 1)));
    }
  }
  context.fillStyle = "#9aa4b4";
  context.textAlign = "center";
  for (const index of labelIndexes) {
    context.fillText(String(series[index].year), x(index), height - 11);
  }

  const gradient = context.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, "rgba(82, 116, 223, 0.18)");
  gradient.addColorStop(1, "rgba(82, 116, 223, 0.005)");
  context.beginPath();
  context.moveTo(x(0), y(series[0].value));
  for (let index = 1; index < series.length; index += 1) {
    const previousX = x(index - 1);
    const currentX = x(index);
    const middleX = (previousX + currentX) / 2;
    context.bezierCurveTo(
      middleX,
      y(series[index - 1].value),
      middleX,
      y(series[index].value),
      currentX,
      y(series[index].value),
    );
  }
  context.lineTo(x(series.length - 1), height - pad.bottom);
  context.lineTo(x(0), height - pad.bottom);
  context.closePath();
  context.fillStyle = gradient;
  context.fill();

  context.beginPath();
  context.moveTo(x(0), y(series[0].value));
  for (let index = 1; index < series.length; index += 1) {
    const previousX = x(index - 1);
    const currentX = x(index);
    const middleX = (previousX + currentX) / 2;
    context.bezierCurveTo(
      middleX,
      y(series[index - 1].value),
      middleX,
      y(series[index].value),
      currentX,
      y(series[index].value),
    );
  }
  context.strokeStyle = CHART_COLOR;
  context.lineWidth = 2.5;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.stroke();

  const last = series.length - 1;
  context.beginPath();
  context.arc(x(last), y(series[last].value), 4, 0, Math.PI * 2);
  context.fillStyle = "#fff";
  context.fill();
  context.lineWidth = 2.5;
  context.strokeStyle = CHART_COLOR;
  context.stroke();

  state.chartPoints = series.map((point, index) => ({ ...point, x: x(index), y: y(point.value) }));
}

function renderCountryRows() {
  const countries = state.analytics.countriesByYear.get(state.analytics.latestYear);
  const search = elements.search.value.trim().toLocaleLowerCase();
  const topCountries = [...countries.entries()]
    .map(([country, value]) => ({ country, value }))
    .sort((a, b) => b.value - a.value || a.country.localeCompare(b.country))
    .slice(0, 10);
  const total = topCountries.reduce((sum, entry) => sum + entry.value, 0);
  const sorted = topCountries
    .map((entry, index) => ({ ...entry, rank: index + 1 }))
    .filter((entry) => entry.country.toLocaleLowerCase().includes(search));

  elements.countryRows.replaceChildren();
  for (const entry of sorted) {
    const row = document.createElement("tr");
    const rank = document.createElement("td");
    rank.className = "rank-number";
    rank.textContent = String(entry.rank).padStart(2, "0");

    const country = document.createElement("td");
    const countryCell = document.createElement("div");
    countryCell.className = "country-cell";
    const badge = document.createElement("span");
    badge.className = "country-badge";
    badge.setAttribute("aria-hidden", "true");
    badge.textContent = entry.country.slice(0, 2).toLocaleUpperCase();
    const countryName = document.createElement("span");
    countryName.textContent = entry.country;
    countryCell.append(badge, countryName);
    country.append(countryCell);

    const stock = document.createElement("td");
    stock.className = "stock-number";
    stock.textContent = formatMillions(entry.value);

    const share = document.createElement("td");
    const track = document.createElement("div");
    track.className = "share-track";
    track.setAttribute("aria-label", `${entry.country} share of displayed markets`);
    const fill = document.createElement("div");
    fill.className = "share-fill";
    fill.style.width = `${total ? Math.max(1, (entry.value / total) * 100) : 0}%`;
    track.append(fill);
    share.append(track);
    row.append(rank, country, stock, share);
    elements.countryRows.append(row);
  }

  elements.rankingEmpty.hidden = sorted.length > 0;
  elements.table.hidden = sorted.length === 0;
  if (!sorted.length) elements.rankingEmpty.textContent = "No matching countries found.";
}

function activateData(file, data) {
  state.data = data;
  state.analytics = getAnalytics(data);
  elements.error.hidden = true;
  elements.status.classList.add("is-loaded");
  elements.datasetName.textContent = file.name;
  elements.datasetUpdated.textContent = `${data.length.toLocaleString()} rows · just now`;
  elements.uploadButtonLabel.textContent = "Replace dataset";

  elements.unit.replaceChildren();
  for (const unit of state.analytics.units) {
    const option = document.createElement("option");
    option.value = unit;
    option.textContent = unit;
    elements.unit.append(option);
  }
  elements.unit.value = state.analytics.preferredUnit;
  elements.unit.disabled = false;
  elements.search.disabled = false;
  elements.chartEmpty.hidden = true;
  elements.rankingEmpty.textContent = "Upload a dataset to reveal the leading EV markets.";

  setMetrics();
  renderCountryRows();
  drawChart();
}

async function handleFile(file) {
  if (!file) return;
  if (!file.name.toLocaleLowerCase().endsWith(".csv")) {
    elements.error.textContent = "Please select a CSV file.";
    elements.error.hidden = false;
    return;
  }
  try {
    const data = parseCsv(await file.text());
    activateData(file, data);
  } catch (error) {
    elements.error.textContent = error instanceof Error ? error.message : "Could not read this CSV.";
    elements.error.hidden = false;
  }
}

elements.file.addEventListener("change", (event) => {
  void handleFile(event.target.files?.[0]);
  event.target.value = "";
});
elements.unit.addEventListener("change", () => {
  if (!state.data) return;
  setMetrics();
  drawChart();
});
elements.search.addEventListener("input", () => {
  if (state.analytics) renderCountryRows();
});

for (const eventName of ["dragenter", "dragover"]) {
  elements.uploadPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.uploadPanel.classList.add("drag-over");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.uploadPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.uploadPanel.classList.remove("drag-over");
  });
}
elements.uploadPanel.addEventListener("drop", (event) => {
  void handleFile(event.dataTransfer?.files?.[0]);
});

elements.chart.addEventListener("pointermove", (event) => {
  if (!state.chartPoints?.length) return;
  const rect = elements.chart.getBoundingClientRect();
  const pointerX = event.clientX - rect.left;
  let nearest = state.chartPoints[0];
  let nearestDistance = Math.abs(pointerX - nearest.x);
  for (const point of state.chartPoints.slice(1)) {
    const distance = Math.abs(pointerX - point.x);
    if (distance < nearestDistance) {
      nearest = point;
      nearestDistance = distance;
    }
  }
  const tooltip = elements.chartTooltip;
  tooltip.textContent = `${nearest.year} · ${formatMillions(nearest.value)} ${elements.unit.value}`;
  tooltip.hidden = false;
  tooltip.style.left = `${Math.min(rect.width - 170, Math.max(0, nearest.x + 10))}px`;
  tooltip.style.top = `${Math.max(0, nearest.y - 30)}px`;
});
elements.chart.addEventListener("pointerleave", () => {
  elements.chartTooltip.hidden = true;
});

if ("ResizeObserver" in window) {
  new ResizeObserver(() => {
    if (state.data) drawChart();
  }).observe(elements.chart);
} else {
  window.addEventListener("resize", () => {
    if (state.data) drawChart();
  });
}
