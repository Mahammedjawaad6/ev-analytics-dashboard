"""CSV validation and analytics used by the interactive dashboard."""

from pathlib import Path
from typing import BinaryIO, Dict, Tuple

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


def load_data_file(path: Path) -> pd.DataFrame:
    """Load and validate the current contents of a local CSV file."""
    with path.open("rb") as source:
        return load_uploaded_csv(source)


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


def build_country_forecast(
    data: pd.DataFrame, unit: str, horizon: int = 3
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Train and validate the country-stock forecast on the supplied data."""
    if not isinstance(horizon, int) or not 1 <= horizon <= 3:
        raise ValueError("Forecast horizon must be between 1 and 3 years.")

    eligible = data.loc[
        (data["category"] == "Historical")
        & (data["parameter"] == "EV stock")
        & (data["mode"] == "Cars")
        & (data["powertrain"] == "EV")
        & (data["aggregate_group"] == "Other")
        & (data["unit"] == unit)
        & data["region_country"].notna()
        & (data["region_country"] != "")
    ]
    stock = (
        eligible.groupby(["region_country", "year"], as_index=False)["value"]
        .sum()
        .sort_values(["region_country", "year"])
    )
    series_by_country = {
        country: list(zip(group["year"].astype(int), group["value"].astype(float)))
        for country, group in stock.groupby("region_country")
        if len(group) >= 4
    }

    empty_forecasts = pd.DataFrame(
        columns=[
            "country",
            "current_year",
            "current_stock",
            "forecast_year",
            "forecast_stock",
            "change_pct",
        ]
    )
    if not series_by_country:
        return empty_forecasts, {
            "model_name": "Not enough data",
            "model_wape": None,
            "baseline_wape": None,
            "validation_samples": 0,
            "validation_countries": 0,
            "target_year": None,
        }

    latest_year = max(points[-1][0] for points in series_by_country.values())
    current_series = {
        country: points
        for country, points in series_by_country.items()
        if points[-1][0] == latest_year
    }

    def fit_linear_trend(points: list) -> Tuple[float, float]:
        history = points[-4:]
        mean_year = sum(year for year, _ in history) / len(history)
        mean_value = sum(value for _, value in history) / len(history)
        variance = sum((year - mean_year) ** 2 for year, _ in history)
        slope = (
            sum((year - mean_year) * (value - mean_value) for year, value in history)
            / variance
            if variance
            else 0.0
        )
        return slope, mean_value - slope * mean_year

    regression_errors = []
    baseline_errors = []
    actual_total = 0.0
    validation_countries = 0
    for points in current_series.values():
        has_validation = False
        first_validation = max(3, len(points) - 3)
        for target_index in range(first_validation, len(points)):
            training = points[:target_index]
            year, actual = points[target_index]
            slope, intercept = fit_linear_trend(training)
            prediction = max(0.0, slope * year + intercept)
            regression_errors.append(abs(prediction - actual))
            baseline_errors.append(abs(training[-1][1] - actual))
            actual_total += actual
            has_validation = True
        validation_countries += int(has_validation)

    model_wape = (
        sum(regression_errors) / actual_total
        if regression_errors and actual_total > 0
        else None
    )
    baseline_wape = (
        sum(baseline_errors) / actual_total
        if baseline_errors and actual_total > 0
        else None
    )
    use_regression = model_wape is not None and (
        baseline_wape is None or model_wape < baseline_wape
    )

    forecasts = []
    for country, points in current_series.items():
        current_year, current_stock = points[-1]
        slope, intercept = fit_linear_trend(points)
        forecast_year = current_year + horizon
        forecast_stock = (
            max(0.0, slope * forecast_year + intercept)
            if use_regression
            else current_stock
        )
        forecasts.append(
            {
                "country": country,
                "current_year": current_year,
                "current_stock": current_stock,
                "forecast_year": forecast_year,
                "forecast_stock": forecast_stock,
                "change_pct": (
                    (forecast_stock - current_stock) / current_stock * 100
                    if current_stock > 0
                    else None
                ),
            }
        )
    forecast_data = (
        pd.DataFrame(forecasts)
        .sort_values(["forecast_stock", "country"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return forecast_data, {
        "model_name": (
            "4-point linear regression" if use_regression else "Last-value baseline"
        ),
        "model_wape": model_wape,
        "baseline_wape": baseline_wape,
        "validation_samples": len(regression_errors),
        "validation_countries": validation_countries,
        "target_year": latest_year + horizon,
    }
