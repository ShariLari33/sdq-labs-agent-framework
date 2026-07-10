import unittest

from packages.performance.analytics import (
    NoPerformanceDataError,
    calculate_google_ads_summary,
)
from packages.performance.normalizer import (
    CsvValidationError,
    normalize_google_ads_row,
    read_csv_rows,
)


class PerformanceNormalizerTests(unittest.TestCase):
    def test_alias_mapping(self):
        rows, mapping = read_csv_rows(
            b"Day,Campaign,Impr.,Clicks,Cost (EUR),Conversions,Conv. value,Currency\n"
            b"2026-06-01,Brand Search,1000,100,50,5,500,EUR\n"
        )

        self.assertEqual(mapping["Day"], "date")
        self.assertEqual(rows[0]["campaign_name"], "Brand Search")
        self.assertEqual(rows[0]["impressions"], "1000")

    def test_clicks_greater_than_impressions_rejected(self):
        with self.assertRaises(CsvValidationError):
            normalize_google_ads_row(
                {
                    "date": "2026-06-01",
                    "campaign_name": "Bad Campaign",
                    "impressions": "10",
                    "clicks": "11",
                    "cost": "1",
                    "conversions": "0",
                    "conversion_value": "0",
                }
            )

    def test_negative_values_rejected(self):
        with self.assertRaises(CsvValidationError):
            normalize_google_ads_row(
                {
                    "date": "2026-06-01",
                    "campaign_name": "Bad Campaign",
                    "impressions": "10",
                    "clicks": "1",
                    "cost": "-1",
                    "conversions": "0",
                    "conversion_value": "0",
                }
            )

    def test_empty_csv_rejected(self):
        with self.assertRaises(CsvValidationError):
            read_csv_rows(b"")


class PerformanceAnalyticsTests(unittest.TestCase):
    def test_summary_calculations_and_alerts(self):
        summary = calculate_google_ads_summary(
            [
                row(
                    "camp-1",
                    "Strong Campaign",
                    impressions=1000,
                    clicks=100,
                    cost=100,
                    conversions=10,
                    conversion_value=500,
                ),
                row(
                    "camp-2",
                    "Waste Campaign",
                    impressions=2000,
                    clicks=10,
                    cost=200,
                    conversions=0,
                    conversion_value=0,
                ),
            ]
        )

        self.assertEqual(summary["totals"]["impressions"], 3000)
        self.assertEqual(summary["calculated_metrics"]["ctr"], 0.036667)
        self.assertTrue(
            any(alert["type"] == "spend_without_conversions" for alert in summary["alerts"])
        )

    def test_division_by_zero_returns_null(self):
        summary = calculate_google_ads_summary(
            [
                row(
                    "camp-1",
                    "No Clicks",
                    impressions=0,
                    clicks=0,
                    cost=0,
                    conversions=0,
                    conversion_value=0,
                )
            ]
        )

        self.assertIsNone(summary["calculated_metrics"]["ctr"])

    def test_no_rows_raises(self):
        with self.assertRaises(NoPerformanceDataError):
            calculate_google_ads_summary([])

    def test_summary_excludes_raw_data(self):
        source = row("camp-1", "Brand", raw_data={"secret": "raw"})

        summary = calculate_google_ads_summary([source])

        self.assertNotIn("raw_data", str(summary))


def row(
    campaign_id,
    campaign_name,
    impressions=100,
    clicks=10,
    cost=20,
    conversions=1,
    conversion_value=100,
    raw_data=None,
):
    return {
        "import_id": "import-1",
        "performance_date": "2026-06-01",
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "campaign_status": "enabled",
        "campaign_type": "Search",
        "impressions": impressions,
        "clicks": clicks,
        "cost": cost,
        "conversions": conversions,
        "conversion_value": conversion_value,
        "currency": "EUR",
        "raw_data": raw_data or {},
    }


if __name__ == "__main__":
    unittest.main()
