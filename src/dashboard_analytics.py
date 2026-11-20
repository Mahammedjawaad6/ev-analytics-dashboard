"""CSV validation and analytics used by the interactive dashboard."""

from typing import BinaryIO, Tuple

import pandas as pd

REQUIRED_COLUMNS = {
    "region_country",
    "category",
    "parameter",
    "mode",
    "powertrain",
    "year",
    "unit",
    "value",
    "aggregate_group",
}


def load_uploaded_csv(file: BinaryIO) -> pd.DataFrame:
    """Read and validate the uploaded EV CSV without persisting it."""
    data = pd.read_csv(file)
    data.columns = [str(column).strip() for column in data.columns]
    data = data.rename(columns={"Aggregate group": "aggregate_group"})

    missing_columns = REQUIRED_COLUMNS - set(data.columns)
    if missing_columns:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing_columns))
        )

    for column in REQUIRED_COLUMNS - {"year", "value"}:
        data[column] = data[column].astype("string").str.strip()
        data[column] = data[column].replace("", pd.NA)

    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    invalid_numeric = data["year"].isna() | data["value"].isna()
    if invalid_numeric.any():
        raise ValueError(
            f"{int(invalid_numeric.sum())} row(s) have an invalid year or value."
        )

    required_values = (
        "category",
        "parameter",
        "mode",
        "powertrain",
        "aggregate_group",
    )
    missing_required = data[list(required_values)].isna().any(axis=1)
    if missing_required.any():
        raise ValueError(
            f"{int(missing_required.sum())} row(s) are missing required dimensions."
        )

    if data.empty:
        raise ValueError("The uploaded CSV has no data rows.")
    data["year"] = data["year"].astype("int64")
    return data


def build_dashboard_analytics(
    data: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """Return global stock growth and top countries for the latest historical year."""
    historical = data.loc[data["category"] == "Historical"]
    stock_filter = (
        (historical["parameter"] == "EV stock")
        & (historical["mode"] == "Cars")
        & (historical["powertrain"] == "EV")
    )

    global_stock = historical.loc[
        stock_filter & (historical["aggregate_group"] == "_World")
    ]
    if global_stock.empty:
        raise ValueError("No historical global EV car-stock records were found.")

    growth = (
        global_stock.groupby(["year", "unit"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "ev_stock"})
        .sort_values(["unit", "year"])
    )
    growth["previous_year_stock"] = growth.groupby("unit")["ev_stock"].shift(1)
    growth["year_over_year_growth_pct"] = (
        (growth["ev_stock"] - growth["previous_year_stock"])
        / growth["previous_year_stock"]
        * 100
    ).round(1)
    growth["ev_stock_millions"] = (growth["ev_stock"] / 1_000_000).round(2)

    country_stock = historical.loc[
        stock_filter
        & (historical["aggregate_group"] == "Other")
        & historical["region_country"].notna()
    ]
    if country_stock.empty:
        raise ValueError("No historical country-level EV car-stock records were found.")

    latest_year = int(country_stock["year"].max())
    top_countries = (
        country_stock.loc[country_stock["year"] == latest_year]
        .groupby("region_country", as_index=False)["value"]
        .sum()
        .rename(
            columns={
                "region_country": "country",
                "value": "ev_stock",
            }
        )
        .sort_values(["ev_stock", "country"], ascending=[False, True])
        .head(10)
        .reset_index(drop=True)
    )
    top_countries["ev_stock_millions"] = (
        top_countries["ev_stock"] / 1_000_000
    ).round(2)
    return growth.reset_index(drop=True), top_countries, latest_year
