"""Batch analytics for the EV country dataset."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Tuple

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

LOGGER = logging.getLogger("ev_analytics")

INPUT_COLUMNS = [
    "region_country",
    "category",
    "parameter",
    "mode",
    "powertrain",
    "year",
    "unit",
    "value",
    "aggregate_group",
]

def load_data(spark: SparkSession, data_file: str) -> DataFrame:
    """Load CSV data with a stable schema and reject invalid numeric records."""
    raw = (
        spark.read.option("header", True)
        .csv(data_file)
        .withColumnRenamed("Aggregate group", "aggregate_group")
    )

    missing_columns = set(INPUT_COLUMNS) - set(raw.columns)
    if missing_columns:
        raise ValueError(
            "Input is missing required columns: " + ", ".join(sorted(missing_columns))
        )

    data = raw.withColumn("year", F.col("year").cast("integer")).withColumn(
        "value", F.col("value").cast("double")
    )
    invalid_rows = data.filter(F.col("year").isNull() | F.col("value").isNull()).count()
    if invalid_rows:
        raise ValueError(
            f"Input contains {invalid_rows} rows with an invalid year or value"
        )
    return data


def create_analytics(data: DataFrame) -> Tuple[DataFrame, DataFrame, int]:
    """Build global growth and latest-year country ranking datasets."""
    historical = data.filter(F.col("category") == "Historical")

    global_stock = (
        historical.filter(
            (F.col("parameter") == "EV stock")
            & (F.col("mode") == "Cars")
            & (F.col("powertrain") == "EV")
            & (F.col("aggregate_group") == "_World")
        )
        .groupBy("year")
        .agg(F.sum("value").alias("value"))
    )
    if global_stock.limit(1).count() == 0:
        raise ValueError("No historical global EV car-stock records were found")

    stock_window = Window.orderBy("year")
    global_growth = (
        global_stock.withColumn(
            "previous_year_stock", F.lag("value").over(stock_window)
        )
        .withColumn(
            "year_over_year_growth_pct",
            F.round(
                (F.col("value") - F.col("previous_year_stock"))
                / F.col("previous_year_stock")
                * 100,
                1,
            ),
        )
        .select(
            "year",
            F.round(F.col("value") / 1_000_000, 2).alias("ev_stock_millions"),
            "year_over_year_growth_pct",
        )
    )

    country_stock = historical.filter(
        (F.col("parameter") == "EV stock")
        & (F.col("mode") == "Cars")
        & (F.col("powertrain") == "EV")
        & (F.col("aggregate_group") == "Other")
        & F.col("region_country").isNotNull()
        & (F.trim(F.col("region_country")) != "")
    )
    latest_year_value = country_stock.agg(F.max("year").alias("latest_year")).first()[
        "latest_year"
    ]
    if latest_year_value is None:
        raise ValueError("No historical country-level EV car-stock records were found")

    top_countries = (
        country_stock.filter(F.col("year") == latest_year_value)
        .groupBy("region_country")
        .agg(F.sum("value").alias("ev_stock"))
        .orderBy(F.desc("ev_stock"), F.asc("region_country"))
        .limit(10)
        .select(
            F.col("region_country").alias("country"),
            F.round(F.col("ev_stock") / 1_000_000, 2).alias("ev_stock_millions"),
        )
    )
    return global_growth, top_countries, latest_year_value


def run(spark: SparkSession, data_file: str, output_dir: str) -> None:
    data = load_data(spark, data_file)
    row_count = data.count()
    global_growth, top_countries, latest_year = create_analytics(data)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    global_growth.write.mode("overwrite").parquet(
        str(output_path / "global_ev_stock_growth")
    )
    top_countries.write.mode("overwrite").parquet(
        str(output_path / "top_countries_latest_year")
    )

    summary = {
        "input_file": Path(data_file).name,
        "input_rows": row_count,
        "latest_country_stock_year": latest_year,
        "outputs": [
            "global_ev_stock_growth/",
            "top_countries_latest_year/",
        ],
    }
    with (output_path / "run_summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
        file.write("\n")
    LOGGER.info(
        "Processed %s input rows; country ranking year is %s",
        row_count,
        latest_year,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=os.environ.get("EV_DATA_FILE", "/data/ev-data.csv"),
        help="Path to the source CSV file",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("EV_OUTPUT_DIR", "/output"),
        help="Directory for Parquet datasets and the run summary",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    spark = SparkSession.builder.appName("EV Country Analytics").getOrCreate()
    try:
        run(spark, args.input, args.output)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
