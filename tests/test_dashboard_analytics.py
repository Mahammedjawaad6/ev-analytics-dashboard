from io import BytesIO

import pytest

from src.dashboard_analytics import build_dashboard_analytics, load_uploaded_csv


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
