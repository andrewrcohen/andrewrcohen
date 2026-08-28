"""Unit tests for the FMCSA Motus exercise harness (no live network)."""

from __future__ import annotations

import unittest

from fmcsa_motus.client import (
    MOTUS_SODA_DATASETS,
    extract_entity_id,
    motus_url,
    qcmobile_url,
    redact_sensitive,
    soda_url,
)
from fmcsa_motus.exercise import build_parser, motus_cases, soda_cases


class ClientHelpersTest(unittest.TestCase):
    def test_motus_url_includes_query(self) -> None:
        url = motus_url("carriers/search", {"query": "44110", "limit": 5, "skip": 0})
        self.assertTrue(url.startswith("https://motus.dot.gov/api/carriers/search?"))
        self.assertIn("query=44110", url)
        self.assertIn("limit=5", url)

    def test_soda_url_uses_dataset_id(self) -> None:
        url = soda_url("inys-ebih", {"$where": "usdot_number='44110'", "$limit": 5})
        self.assertEqual(
            url,
            "https://data.transportation.gov/resource/inys-ebih.json?$where=usdot_number='44110'&$limit=5",
        )

    def test_qcmobile_url_appends_webkey(self) -> None:
        url = qcmobile_url("carriers/44110", "test-key")
        self.assertEqual(
            url,
            "https://mobile.fmcsa.dot.gov/qc/services/carriers/44110?webKey=test-key",
        )

    def test_redact_sensitive_tax_ids(self) -> None:
        payload = {
            "entityName": "GREYHOUND LINES INC",
            "ein": "860572343",
            "ssn": "",
            "nested": {"ssn": "111-22-3333"},
        }
        redacted = redact_sensitive(payload)
        self.assertEqual(redacted["ein"], "[redacted]")
        self.assertEqual(redacted["ssn"], "")
        self.assertEqual(redacted["nested"]["ssn"], "[redacted]")
        self.assertEqual(redacted["entityName"], "GREYHOUND LINES INC")

    def test_extract_entity_id_from_search(self) -> None:
        body = {"data": [{"entityId": "abc-123", "dotNumber": "44110"}]}
        self.assertEqual(extract_entity_id(body), "abc-123")

    def test_known_motus_soda_datasets(self) -> None:
        self.assertEqual(len(MOTUS_SODA_DATASETS), 12)
        self.assertEqual(MOTUS_SODA_DATASETS["carrier_history"]["id"], "inys-ebih")
        self.assertEqual(MOTUS_SODA_DATASETS["insur_history"]["id"], "c5y8-a4uz")


class ExerciseCatalogTest(unittest.TestCase):
    def test_parser_defaults(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.usdot, "44110")
        self.assertEqual(args.suite, "all")

    def test_motus_cases_cover_public_search(self) -> None:
        names = [case["name"] for case in motus_cases("44110", "GREYHOUND", 5)]
        self.assertIn("motus.carriers.search.query.usdot", names)
        self.assertIn("motus.carriers.by_usdot", names)
        self.assertIn("motus.boc3.process_agents_by_usdot", names)

    def test_soda_cases_cover_history_and_daily(self) -> None:
        cases = soda_cases("44110", 5)
        self.assertEqual(len(cases), 12)
        history = next(case for case in cases if case["name"] == "soda.carrier_history")
        self.assertIn("usdot_number='44110'", history["url"])
        daily = next(case for case in cases if case["name"] == "soda.carrier_daily")
        self.assertNotIn("$where", daily["url"])


if __name__ == "__main__":
    unittest.main()
