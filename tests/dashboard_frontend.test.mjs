import assert from "node:assert/strict";
import test from "node:test";

import { getAnalytics, parseCsv } from "../web/data.mjs";

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
