from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import load_settings
from pipeline.models import PaperRecord
from pipeline.render import write_site_payload
from pipeline.score import passes_display_gate, passes_rule_gate, score_records
from pipeline.summarize import enrich_records_with_summaries


class DatasetPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = replace(load_settings(), deepseek_api_key=None)

    def test_dataset_gate_keeps_power_data_and_rejects_unrelated_data(self) -> None:
        records = [
            self._record(
                "Electricity load profiles and smart meter dataset for power system forecasting",
                "A public time series collection of electricity consumption measurements for load forecasting.",
            ),
            self._record(
                "Global climate observations dataset",
                "A database of temperature and precipitation observations.",
            ),
            self._record(
                "Battery cathode microscopy dataset",
                "Images for electrode synthesis and materials characterization.",
            ),
        ]

        score_records(records, self.settings)

        self.assertTrue(passes_rule_gate(records[0]))
        self.assertTrue(passes_display_gate(records[0], llm_enabled=False))
        self.assertIn("电力数据", records[0].matched_keyword_groups)
        self.assertFalse(passes_rule_gate(records[1]))
        self.assertFalse(passes_rule_gate(records[2]))

    def test_dataset_summary_and_render_use_the_dedicated_section(self) -> None:
        record = self._record(
            "Open smart meter dataset for electricity consumption forecasting",
            "This dataset provides smart meter time series for electricity consumption and load forecasting.",
        )
        score_records([record], self.settings)
        enrich_records_with_summaries([record], self.settings)

        self.assertIn("数据集内容和研究目的", record.ai_summary)

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            site_dir = Path(temp_dir)
            write_site_payload(
                site_dir=site_dir,
                settings=self.settings,
                target_date=datetime.now(timezone.utc).date(),
                generated_at=datetime.now(timezone.utc),
                records=[record],
                source_errors=[],
            )
            payload = json.loads((site_dir / "latest.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["sections"]["datasets"]["count"], 1)
        self.assertEqual(payload["sections"]["discovery"]["count"], 0)
        self.assertEqual(payload["meta"]["dataset_lookback_days"], 14)

    @staticmethod
    def _record(title: str, abstract: str) -> PaperRecord:
        return PaperRecord(
            id=title,
            source="dataset",
            journal="Scientific Data",
            title=title,
            authors=["Test Author"],
            abstract_raw=abstract,
            url="https://example.com/data-paper",
            published_at=datetime.now(timezone.utc),
            metadata={
                "group_key": "datasets",
                "journal_weight": 0.65,
            },
        )


if __name__ == "__main__":
    unittest.main()
