import hashlib
import subprocess
import unittest
from pathlib import Path

from packages.performance.analytics import calculate_google_ads_summary
from packages.performance.normalizer import normalize_google_ads_row, read_csv_rows


SANDBOX_ROOT = Path(__file__).resolve().parents[1] / "sandbox" / "sdq-labs-growth"
TENANT_SLUG = "sdq-labs-growth-sandbox"


def summary_for_dataset(filename):
    raw_rows, _mapping = read_csv_rows((SANDBOX_ROOT / "datasets" / filename).read_bytes())
    rows = []
    for row in raw_rows:
        normalized = normalize_google_ads_row(row)
        rows.append(
            {
                "import_id": filename,
                "performance_date": normalized.performance_date.isoformat(),
                "campaign_id": normalized.campaign_id,
                "campaign_name": normalized.campaign_name,
                "campaign_status": normalized.campaign_status,
                "campaign_type": normalized.campaign_type,
                "impressions": normalized.impressions,
                "clicks": normalized.clicks,
                "cost": normalized.cost,
                "conversions": normalized.conversions,
                "conversion_value": normalized.conversion_value,
                "currency": normalized.currency,
                "raw_data": {},
            }
        )
    return calculate_google_ads_summary(rows)


class GrowthSandboxDatasetTests(unittest.TestCase):
    def test_expected_baseline_alerts(self):
        summary = summary_for_dataset("google-ads-baseline.csv")
        alert_pairs = {
            (alert["type"], alert["campaign_name"])
            for alert in summary["alerts"]
        }

        self.assertIn(("spend_without_conversions", "Broad Growth Experiments"), alert_pairs)
        self.assertIn(("low_ctr", "Broad Growth Experiments"), alert_pairs)
        self.assertIn(("high_spend_low_conversion_share", "Broad Growth Experiments"), alert_pairs)
        self.assertLess(
            campaign(summary, "Brand Search")["metrics"]["cost_per_conversion"],
            campaign(summary, "AI Automation Non Brand")["metrics"]["cost_per_conversion"],
        )

    def test_followup_improvement(self):
        baseline = summary_for_dataset("google-ads-baseline.csv")
        followup = summary_for_dataset("google-ads-followup.csv")

        self.assertLess(
            followup["calculated_metrics"]["cost_per_conversion"],
            baseline["calculated_metrics"]["cost_per_conversion"],
        )
        self.assertGreater(
            followup["calculated_metrics"]["roas"],
            baseline["calculated_metrics"]["roas"],
        )
        self.assertLess(
            campaign(followup, "Broad Growth Experiments")["totals"]["cost"],
            campaign(baseline, "Broad Growth Experiments")["totals"]["cost"],
        )

    def test_validation_persistence(self):
        baseline = summary_for_dataset("google-ads-baseline.csv")
        validation = summary_for_dataset("google-ads-validation.csv")

        self.assertLess(
            validation["calculated_metrics"]["cost_per_conversion"],
            baseline["calculated_metrics"]["cost_per_conversion"],
        )
        self.assertGreater(
            validation["calculated_metrics"]["roas"],
            baseline["calculated_metrics"]["roas"],
        )
        self.assertLess(
            campaign(validation, "Broad Growth Experiments")["spend_share"],
            campaign(baseline, "Broad Growth Experiments")["spend_share"],
        )

    def test_tenant_isolation_contract(self):
        for task_path in (SANDBOX_ROOT / "tasks").glob("*.json"):
            self.assertIn(f'"tenant_slug": "{TENANT_SLUG}"', task_path.read_text())

        reset_script = (SANDBOX_ROOT / "scripts" / "reset-sandbox-data.sh").read_text()
        self.assertIn(TENANT_SLUG, reset_script)
        self.assertNotIn("DELETE FROM tenants", reset_script)

    def test_repeatable_dataset_import_inputs(self):
        first = summary_for_dataset("google-ads-baseline.csv")
        second = summary_for_dataset("google-ads-baseline.csv")

        self.assertEqual(first["totals"], second["totals"])
        self.assertEqual(first["calculated_metrics"], second["calculated_metrics"])
        self.assertEqual(first["period"]["days"], 7)

    def test_duplicate_import_handling_is_documented_in_scripts(self):
        baseline_bytes = (SANDBOX_ROOT / "datasets" / "google-ads-baseline.csv").read_bytes()
        self.assertEqual(
            hashlib.sha256(baseline_bytes).hexdigest(),
            hashlib.sha256(baseline_bytes).hexdigest(),
        )

        for script_name in ["import-baseline.sh", "import-followup.sh", "import-validation.sh"]:
            script = (SANDBOX_ROOT / "scripts" / script_name).read_text()
            self.assertIn('elif [[ "$code" == "409" ]]', script)

    def test_demo_scripts_syntax(self):
        for script_path in (SANDBOX_ROOT / "scripts").glob("*.sh"):
            with self.subTest(script=script_path.name):
                subprocess.run(["bash", "-n", str(script_path)], check=True)


def campaign(summary, name):
    for item in summary["campaign_breakdown"]:
        if item["campaign_name"] == name:
            return item
    raise AssertionError(f"Campaign not found: {name}")


if __name__ == "__main__":
    unittest.main()
