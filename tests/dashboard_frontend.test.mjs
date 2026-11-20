import assert from "node:assert/strict";
import test from "node:test";

import { buildForecast, getAnalytics, parseCsv } from "../web/data.mjs";

const HEADER =
  "\uFEFFregion_country,category,parameter,mode,powertrain,year,unit,value,Aggregate group";

test("parses quoted CSV fields, escaped quotes, and CRLF rows", () => {
  const csv = [
    HEADER,
    '"Alpha, North",Historical,EV stock,Cars,EV,2022,Vehicles,10000000,Other',
    '"Say ""EV""",Historical,EV stock,Cars,EV,2022,Vehicles,20000000,Other',
    "",
  ].join("\r\n");

  const data = parseCsv(csv);

  assert.equal(data[0].region_country, "Alpha, North");
  assert.equal(data[1].region_country, 'Say "EV"');
  assert.equal(data[0].aggregate_group, "Other");
  assert.equal(data[0].year, 2022);
});

test("rejects malformed rows, invalid numbers, and unclosed quotes", () => {
  assert.throws(
    () => parseCsv(`${HEADER}\nAlpha,Historical,EV stock,Cars,EV,2022,Vehicles,1`),
    /expected 9/,
  );
  assert.throws(
    () =>
      parseCsv(
        `${HEADER}\nAlpha,Historical,EV stock,Cars,EV,not-a-year,Vehicles,1,Other`,
      ),
    /invalid year or value/,
  );
  assert.throws(() => parseCsv(`${HEADER}\n"Alpha,Historical`), /unclosed quoted field/);
});

test("aggregates historical global stock and ranks latest-year countries", () => {
  const data = parseCsv(
    [
      HEADER,
      "_World,Historical,EV stock,Cars,EV,2022,Vehicles,100000000,_World",
      "_World,Historical,EV stock,Cars,EV,2023,Vehicles,150000000,_World",
      "_World,Projection-STEPS,EV stock,Cars,EV,2025,Vehicles,500000000,_World",
      "Alpha,Historical,EV stock,Cars,EV,2023,Vehicles,20000000,Other",
      "Beta,Historical,EV stock,Cars,EV,2023,Vehicles,40000000,Other",
      "Older,Historical,EV stock,Cars,EV,2022,Vehicles,90000000,Other",
      ",Historical,EV stock,Cars,EV,2023,Vehicles,90000000,Other",
    ].join("\n"),
  );
  const analytics = getAnalytics(data);

  assert.equal(analytics.preferredUnit, "Vehicles");
  assert.equal(analytics.latestYear, 2023);
  assert.equal(analytics.globalByYearUnit.get("Vehicles\u00002023"), 150000000);
  assert.deepEqual(
    [...analytics.countriesByYear.get(2023).entries()].sort((a, b) => b[1] - a[1]),
    [
      ["Beta", 40000000],
      ["Alpha", 20000000],
    ],
  );
});

test("trains a country trend, validates it against persistence, and excludes projections", () => {
  const data = Array.from({ length: 6 }, (_, index) => ({
    region_country: "Alpha",
    category: "Historical",
    parameter: "EV stock",
    mode: "Cars",
    powertrain: "EV",
    year: 2020 + index,
    unit: "Vehicles",
    value: 10 + index * 10,
    aggregate_group: "Other",
  }));
  data.push({
    ...data[5],
    category: "Projection-STEPS",
    year: 2030,
    value: 10000,
  });
  data.push({
    ...data[5],
    unit: "vehicles",
    year: 2025,
    value: 50000,
  });

  const result = buildForecast(data, "Vehicles", 3);

  assert.equal(result.modelName, "4-point linear regression");
  assert.equal(result.validationSamples, 3);
  assert.equal(result.validationCountries, 1);
  assert.equal(result.modelWape, 0);
  assert.ok(result.baselineWape > result.modelWape);
  assert.equal(result.targetYear, 2028);
  assert.deepEqual(result.forecasts[0], {
    country: "Alpha",
    currentYear: 2025,
    currentValue: 60,
    forecastYear: 2028,
    forecastValue: 90,
    changePct: 50,
  });
});

test("uses the last-value baseline when regression loses its rolling backtest", () => {
  const values = [601, 847, 245, 991, 871, 337];
  const data = values.map((value, index) => ({
    region_country: "Beta",
    category: "Historical",
    parameter: "EV stock",
    mode: "Cars",
    powertrain: "EV",
    year: 2020 + index,
    unit: "Vehicles",
    value,
    aggregate_group: "Other",
  }));

  const result = buildForecast(data, "Vehicles", 2);

  assert.equal(result.modelName, "Last-value baseline");
  assert.ok(result.modelWape > result.baselineWape);
  assert.equal(result.forecasts[0].forecastValue, 337);
  assert.equal(result.forecasts[0].forecastYear, 2027);
});

test("does not forecast short country series and rejects unsupported horizons", () => {
  const data = Array.from({ length: 3 }, (_, index) => ({
    region_country: "Gamma",
    category: "Historical",
    parameter: "EV stock",
    mode: "Cars",
    powertrain: "EV",
    year: 2020 + index,
    unit: "Vehicles",
    value: 5 + index,
    aggregate_group: "Other",
  }));

  assert.deepEqual(buildForecast(data, "Vehicles").forecasts, []);
  assert.throws(
    () => buildForecast(data, "Vehicles", 4),
    /between 1 and 3 years/,
  );
});
