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
