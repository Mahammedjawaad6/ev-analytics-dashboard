export const REQUIRED_COLUMNS = [
  "region_country",
  "category",
  "parameter",
  "mode",
  "powertrain",
  "year",
  "unit",
  "value",
  "aggregate_group",
];

export function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        value += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        value += char;
      }
    } else if (char === '"' && value.length === 0) {
      quoted = true;
    } else if (char === ",") {
      row.push(value);
      value = "";
    } else if (char === "\n" || char === "\r") {
      row.push(value);
      value = "";
      if (row.some((cell) => cell.trim() !== "")) rows.push(row);
      row = [];
      if (char === "\r" && text[i + 1] === "\n") i += 1;
    } else {
      value += char;
    }
  }

  if (quoted) throw new Error("The CSV has an unclosed quoted field.");
  if (value.length > 0 || row.length > 0) {
    row.push(value);
    if (row.some((cell) => cell.trim() !== "")) rows.push(row);
  }
  if (rows.length < 2) throw new Error("The CSV has a header but no data rows.");

  const headers = rows[0].map((header) => header.trim().replace(/^\uFEFF/, ""));
  const normalizedHeaders = headers.map((header) =>
    header === "Aggregate group" ? "aggregate_group" : header,
  );
  const missing = REQUIRED_COLUMNS.filter((column) => !normalizedHeaders.includes(column));
  if (missing.length) {
    throw new Error(`Missing required columns: ${missing.join(", ")}.`);
  }

  const indexes = Object.fromEntries(
    REQUIRED_COLUMNS.map((column) => [column, normalizedHeaders.indexOf(column)]),
  );
  return rows.slice(1).map((cells, rowIndex) => {
    if (cells.length !== headers.length) {
      throw new Error(`Row ${rowIndex + 2} has ${cells.length} cells; expected ${headers.length}.`);
    }
    const record = {};
    for (const column of REQUIRED_COLUMNS) {
      record[column] = (cells[indexes[column]] ?? "").trim();
    }
    const year = Number(record.year);
    const amount = Number(record.value);
    if (
      !record.year ||
      !Number.isInteger(year) ||
      !record.value ||
      !Number.isFinite(amount)
    ) {
      throw new Error(`Row ${rowIndex + 2} has an invalid year or value.`);
    }
    record.year = year;
    record.value = amount;
    return record;
  });
}

export function getAnalytics(data) {
  const historical = data.filter((row) => row.category === "Historical");
  const isEvCarStock = (row) =>
    row.parameter === "EV stock" && row.mode === "Cars" && row.powertrain === "EV";
  const globalRows = historical.filter(
    (row) => isEvCarStock(row) && row.aggregate_group === "_World",
  );
  const countryRows = historical.filter(
    (row) =>
      isEvCarStock(row) &&
      row.aggregate_group === "Other" &&
      row.region_country.length > 0,
  );
  if (!globalRows.length) {
    throw new Error("No historical global EV car-stock records were found.");
  }
  if (!countryRows.length) {
    throw new Error("No historical country-level EV car-stock records were found.");
  }

  const globalByYearUnit = new Map();
  for (const record of globalRows) {
    const key = `${record.unit}\u0000${record.year}`;
    globalByYearUnit.set(key, (globalByYearUnit.get(key) || 0) + record.value);
  }
  const units = [...new Set(globalRows.map((row) => row.unit))].sort();
  const preferredUnit = units.includes("Vehicles") ? "Vehicles" : units[0];
  const countriesByYear = new Map();
  for (const record of countryRows) {
    const year = record.year;
    if (!countriesByYear.has(year)) countriesByYear.set(year, new Map());
    const countries = countriesByYear.get(year);
    countries.set(
      record.region_country,
      (countries.get(record.region_country) || 0) + record.value,
    );
  }
  const latestYear = Math.max(...countriesByYear.keys());

  return { globalByYearUnit, units, preferredUnit, countriesByYear, latestYear };
}

const FORECAST_HISTORY = 4;
const MIN_FORECAST_HISTORY = 4;

function fitLinearTrend(points) {
  const history = points.slice(-FORECAST_HISTORY);
  const meanYear =
    history.reduce((total, point) => total + point.year, 0) / history.length;
  const meanValue =
    history.reduce((total, point) => total + point.value, 0) / history.length;
  const yearVariance = history.reduce(
    (total, point) => total + (point.year - meanYear) ** 2,
    0,
  );
  const slope =
    yearVariance === 0
      ? 0
      : history.reduce(
          (total, point) =>
            total + (point.year - meanYear) * (point.value - meanValue),
          0,
        ) / yearVariance;

  return (year) => Math.max(0, meanValue + slope * (year - meanYear));
}

function scoreForecast(errors, actualTotal) {
  if (!errors.length || actualTotal <= 0) return null;
  const absoluteError = errors.reduce((total, error) => total + error, 0);
  return absoluteError / actualTotal;
}

export function buildForecast(data, unit, horizon = 3) {
  if (!Number.isInteger(horizon) || horizon < 1 || horizon > 3) {
    throw new Error("Forecast horizon must be between 1 and 3 years.");
  }

  const stockByCountry = new Map();
  for (const row of data) {
    if (
      row.category !== "Historical" ||
      row.parameter !== "EV stock" ||
      row.mode !== "Cars" ||
      row.powertrain !== "EV" ||
      row.aggregate_group !== "Other" ||
      row.unit !== unit ||
      !row.region_country
    ) {
      continue;
    }

    if (!stockByCountry.has(row.region_country)) {
      stockByCountry.set(row.region_country, new Map());
    }
    const stockByYear = stockByCountry.get(row.region_country);
    stockByYear.set(
      row.year,
      (stockByYear.get(row.year) || 0) + row.value,
    );
  }

  const seriesByCountry = [...stockByCountry.entries()]
    .map(([country, stockByYear]) => ({
      country,
      points: [...stockByYear.entries()]
        .map(([year, value]) => ({ year, value }))
        .sort((left, right) => left.year - right.year),
    }))
    .filter(({ points }) => points.length >= MIN_FORECAST_HISTORY);

  if (!seriesByCountry.length) {
    return {
      modelName: "Not enough data",
      modelWape: null,
      baselineWape: null,
      validationSamples: 0,
      validationCountries: 0,
      latestYear: null,
      targetYear: null,
      forecasts: [],
    };
  }

  const latestYear = Math.max(
    ...seriesByCountry.map(({ points }) => points[points.length - 1].year),
  );
  const currentSeries = seriesByCountry.filter(
    ({ points }) => points[points.length - 1].year === latestYear,
  );
  const regressionErrors = [];
  const baselineErrors = [];
  let actualTotal = 0;
  let validationCountries = 0;

  for (const { points } of currentSeries) {
    let hasValidation = false;
    const firstValidationIndex = Math.max(3, points.length - 3);
    for (
      let targetIndex = firstValidationIndex;
      targetIndex < points.length;
      targetIndex += 1
    ) {
      const training = points.slice(0, targetIndex);
      const actual = points[targetIndex];
      const predict = fitLinearTrend(training);
      regressionErrors.push(Math.abs(predict(actual.year) - actual.value));
      baselineErrors.push(
        Math.abs(training[training.length - 1].value - actual.value),
      );
      actualTotal += actual.value;
      hasValidation = true;
    }
    if (hasValidation) validationCountries += 1;
  }

  const modelWape = scoreForecast(regressionErrors, actualTotal);
  const baselineWape = scoreForecast(baselineErrors, actualTotal);
  const useRegression =
    modelWape !== null &&
    (baselineWape === null || modelWape < baselineWape);
  const forecasts = currentSeries.map(({ country, points }) => {
    const current = points[points.length - 1];
    const predict = fitLinearTrend(points);
    const forecastValue = useRegression
      ? predict(current.year + horizon)
      : current.value;
    return {
      country,
      currentYear: current.year,
      currentValue: current.value,
      forecastYear: current.year + horizon,
      forecastValue,
      changePct:
        current.value > 0
          ? ((forecastValue - current.value) / current.value) * 100
          : null,
    };
  }).sort(
    (left, right) =>
      right.forecastValue - left.forecastValue ||
      left.country.localeCompare(right.country),
  );

  return {
    modelName: useRegression
      ? "4-point linear regression"
      : "Last-value baseline",
    modelWape,
    baselineWape,
    validationSamples: regressionErrors.length,
    validationCountries,
    latestYear,
    targetYear: latestYear + horizon,
    forecasts,
  };
}
