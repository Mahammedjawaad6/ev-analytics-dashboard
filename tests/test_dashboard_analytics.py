from io import BytesIO
from pathlib import Path

import pytest

from src.dashboard_analytics import (
    build_country_forecast,
    build_dashboard_analytics,
    load_data_file,
    load_uploaded_csv,
)


CSV_HEADER = (
    "region_country,category,parameter,mode,powertrain,year,unit,value,"
    "Aggregate group\n"
)


def test_upload_validation_and_latest_year_analytics():
    csv = CSV_HEADER + (
        "_World,Historical,EV stock,Cars,EV,2022,Vehicles,100000000,_World\n"
        "_World,Historical,EV stock,Cars,EV,2023,Vehicles,150000000,_World\n"
        "_World,Projection-STEPS,EV stock,Cars,EV,2025,Vehicles,500000000,_World\n"
        "Alpha,Historical,EV stock,Cars,EV,2023,Vehicles,20000000,Other\n"
        "Beta,Historical,EV stock,Cars,EV,2023,Vehicles,40000000,Other\n"
        ",Historical,EV stock,Cars,EV,2023,Vehicles,90000000,Other\n"
    )

    data = load_uploaded_csv(BytesIO(csv.encode("utf-8")))
    growth, countries, latest_year = build_dashboard_analytics(data)

    assert latest_year == 2023
    assert growth["ev_stock_millions"].tolist() == [100.0, 150.0]
    assert growth.iloc[1]["year_over_year_growth_pct"] == 50.0
    assert countries[["country", "ev_stock_millions"]].values.tolist() == [
        ["Beta", 40.0],
        ["Alpha", 20.0],
    ]


def test_upload_rejects_invalid_numeric_values():
    csv = CSV_HEADER + "_World,Historical,EV stock,Cars,EV,not-a-year,Vehicles,10,_World\n"

    with pytest.raises(ValueError, match="invalid year or value"):
        load_uploaded_csv(BytesIO(csv.encode("utf-8")))


def test_upload_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing required columns"):
        load_uploaded_csv(BytesIO(b"region_country,year\nA,2023\n"))


def test_reloading_appended_csv_updates_analytics_and_forecast(tmp_path: Path):
    source = tmp_path / "ev-data.csv"
    rows = []
    for year_index in range(4):
        year = 2020 + year_index
        rows.extend(
            [
                f"_World,Historical,EV stock,Cars,EV,{year},Vehicles,"
                f"{100_000_000 + year_index * 10_000_000},_World",
                f"Alpha,Historical,EV stock,Cars,EV,{year},Vehicles,"
                f"{20_000_000 + year_index * 10_000_000},Other",
            ]
        )
    source.write_text(CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")

    before = load_data_file(source)
    _, _, initial_latest_year = build_dashboard_analytics(before)
    _, initial_forecast = build_country_forecast(before, "Vehicles")

    with source.open("a", encoding="utf-8") as csv_file:
        csv_file.write(
            "_World,Historical,EV stock,Cars,EV,2024,Vehicles,140000000,_World\n"
            "Alpha,Historical,EV stock,Cars,EV,2024,Vehicles,60000000,Other\n"
        )

    after = load_data_file(source)
    growth, _, latest_year = build_dashboard_analytics(after)
    forecasts, forecast = build_country_forecast(after, "Vehicles")

    assert len(after) == len(before) + 2
    assert initial_latest_year == 2023
    assert latest_year == 2024
    assert growth.iloc[-1]["ev_stock_millions"] == 140.0
    assert initial_forecast["target_year"] == 2026
    assert forecast["target_year"] == 2027
    assert forecasts.iloc[0]["current_stock"] == 60_000_000
