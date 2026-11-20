import unittest

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from src.ev_analytics import create_analytics


class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder.master("local[1]")
            .appName("EV analytics tests")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_growth_and_latest_country_ranking_ignore_projections(self):
        schema = StructType(
            [
                StructField("region_country", StringType(), True),
                StructField("category", StringType(), True),
                StructField("parameter", StringType(), True),
                StructField("mode", StringType(), True),
                StructField("powertrain", StringType(), True),
                StructField("year", IntegerType(), True),
                StructField("value", DoubleType(), True),
                StructField("aggregate_group", StringType(), True),
            ]
        )
        records = [
            (
                "_World",
                "Historical",
                "EV stock",
                "Cars",
                "EV",
                2021,
                100_000_000.0,
                "_World",
            ),
            (
                "_World",
                "Historical",
                "EV stock",
                "Cars",
                "EV",
                2022,
                150_000_000.0,
                "_World",
            ),
            (
                "_World",
                "Projection-STEPS",
                "EV stock",
                "Cars",
                "EV",
                2024,
                500_000_000.0,
                "_World",
            ),
            ("Alpha", "Historical", "EV stock", "Cars", "EV", 2021, 10_000_000.0, "Other"),
            ("Alpha", "Historical", "EV stock", "Cars", "EV", 2022, 20_000_000.0, "Other"),
            ("Beta", "Historical", "EV stock", "Cars", "EV", 2022, 40_000_000.0, "Other"),
        ]
        data = self.spark.createDataFrame(records, schema)

        growth, countries, latest_year = create_analytics(data)

        self.assertEqual(latest_year, 2022)
        growth_rows = {row["year"]: row.asDict() for row in growth.collect()}
        self.assertEqual(growth_rows[2021]["ev_stock_millions"], 100.0)
        self.assertEqual(growth_rows[2022]["year_over_year_growth_pct"], 50.0)
        self.assertEqual(
            [(row["country"], row["ev_stock_millions"]) for row in countries.collect()],
            [("Beta", 40.0), ("Alpha", 20.0)],
        )


if __name__ == "__main__":
    unittest.main()
