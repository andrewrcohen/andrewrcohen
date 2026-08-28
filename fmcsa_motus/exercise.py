#!/usr/bin/env python3
"""Exercise FMCSA Motus public APIs, Motus SODA datasets, and optional QCMobile.

This repo did not contain a prior Motus client. The harness calls the live public
APIs that Motus already exposes:

  * Motus REST at https://motus.dot.gov/api  (public company search and record)
  * Motus SODA datasets at https://data.transportation.gov
  * Optional QCMobile lookup API when FMCSA_WEBKEY is provided

Examples:
    python3 -m fmcsa_motus.exercise --usdot 44110 --name GREYHOUND
    python3 -m fmcsa_motus.exercise --suite soda --usdot 44110
    FMCSA_WEBKEY=... python3 -m fmcsa_motus.exercise --suite qcmobile --usdot 44110
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, Iterable, Optional

from fmcsa_motus.client import (
    MOTUS_SODA_DATASETS,
    HttpClient,
    HttpResult,
    extract_entity_id,
    motus_url,
    qcmobile_url,
    redact_sensitive,
    soda_url,
)

DEFAULT_USDOT = "44110"
DEFAULT_NAME = "GREYHOUND"
DEFAULT_LIMIT = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exercise FMCSA Motus public APIs and related open-data feeds."
    )
    parser.add_argument("--usdot", default=DEFAULT_USDOT, help="USDOT number to look up")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Legal/DBA name search term")
    parser.add_argument(
        "--suite",
        choices=("all", "motus", "soda", "qcmobile"),
        default="all",
        help="Which API family to exercise",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Search page size")
    parser.add_argument(
        "--webkey",
        default=os.environ.get("FMCSA_WEBKEY", ""),
        help="QCMobile webKey (or set FMCSA_WEBKEY)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print redacted JSON bodies for passing checks",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed check",
    )
    return parser


def motus_cases(usdot: str, name: str, limit: int) -> list[dict[str, Any]]:
    encoded_name = name.strip()
    return [
        {
            "name": "motus.auth.version",
            "url": motus_url("auth/version"),
            "expect_status": 200,
            "checks": [_require_keys("serverVersion")],
        },
        {
            "name": "motus.carriers.search.query.usdot",
            "url": motus_url("carriers/search", {"query": usdot, "limit": limit, "skip": 0}),
            "expect_status": 200,
            "checks": [_require_search_hit(usdot)],
        },
        {
            "name": "motus.carriers.search.query.name",
            "url": motus_url("carriers/search", {"query": encoded_name, "limit": limit, "skip": 0}),
            "expect_status": 200,
            "checks": [_require_list_or_data()],
        },
        {
            "name": "motus.carriers.search.path.usdot",
            "url": motus_url(f"carriers/search/{usdot}"),
            "expect_status": 200,
            "checks": [_require_list_or_data()],
        },
        {
            "name": "motus.carriers.by_usdot",
            "url": motus_url(f"carriers/{usdot}"),
            "expect_status": 200,
            "checks": [_require_keys("entityId", "entityDotNumber")],
        },
        {
            "name": "motus.carriers.search.filings",
            "url": motus_url(
                "carriers/search/filings",
                {"query": usdot, "skip": 0, "limit": limit, "includeTotal": "false"},
            ),
            "expect_status": 200,
            "checks": [_require_list_or_data()],
        },
        {
            "name": "motus.boc3.process_agents_by_usdot",
            "url": motus_url(f"boc3/processAgents/dot/{usdot}"),
            "expect_status": 200,
            "checks": [_require_keys("dotNumber")],
        },
    ]


def motus_follow_up_cases(entity_id: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "motus.carriers.by_entity_id",
            "url": motus_url(f"carriers/entityId/{entity_id}"),
            "expect_status": 200,
            "checks": [_require_keys("entityId")],
        },
        {
            "name": "motus.public_registration_matrix",
            "url": motus_url(f"public-registration-matrix/{entity_id}"),
            "expect_status": 200,
            "checks": [_require_keys("entity")],
        },
        {
            "name": "motus.entity.by_entity_id",
            "url": motus_url(f"entity/entityId/{entity_id}"),
            "expect_status": 200,
            "checks": [_require_keys("entityId")],
        },
        {
            "name": "motus.entity.registrations",
            "url": motus_url(f"entity/registrations/{entity_id}"),
            "expect_status": 200,
            "checks": [_require_list_or_data()],
        },
        {
            "name": "motus.entity.registration_history",
            "url": motus_url(f"entity/entity-registration-history/{entity_id}"),
            "expect_status": 200,
            "checks": [_allow_empty_list()],
        },
    ]


def soda_cases(usdot: str, limit: int) -> list[dict[str, Any]]:
    cases = []
    for key, meta in MOTUS_SODA_DATASETS.items():
        is_daily = key.endswith("_daily")
        params: dict[str, Any] = {"$limit": 1 if is_daily else limit}
        if not is_daily:
            params["$where"] = f"{meta['query_field']}='{usdot}'"
        cases.append(
            {
                "name": f"soda.{key}",
                "url": soda_url(meta["id"], params),
                "expect_status": 200,
                "checks": [_require_json_list()],
                "allow_empty": True,
                "label": meta["name"],
            }
        )
    return cases


def qcmobile_cases(usdot: str, name: str, web_key: str) -> list[dict[str, Any]]:
    paths = [
        f"carriers/{usdot}",
        f"carriers/name/{urllib_quote(name)}",
        f"carriers/{usdot}/basics",
        f"carriers/{usdot}/authority",
        f"carriers/{usdot}/cargo-carried",
        f"carriers/{usdot}/operation-classification",
        f"carriers/{usdot}/oos",
        f"carriers/{usdot}/docket-numbers",
    ]
    cases = []
    for path in paths:
        cases.append(
            {
                "name": f"qcmobile.{path.replace('/', '.')}",
                "url": qcmobile_url(path, web_key),
                "expect_status": 200,
                "checks": [_require_json_object_or_list()],
            }
        )
    return cases


def urllib_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


Check = Callable[[HttpResult], list[str]]


def _require_keys(*keys: str) -> Check:
    def check(result: HttpResult) -> list[str]:
        if not isinstance(result.body, dict):
            return ["expected a JSON object"]
        missing = [key for key in keys if key not in result.body]
        return [f"missing keys: {', '.join(missing)}"] if missing else []

    return check


def _require_search_hit(usdot: str) -> Check:
    def check(result: HttpResult) -> list[str]:
        body = result.body
        rows: list[Any]
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            rows = body["data"]
        elif isinstance(body, list):
            rows = body
        else:
            return ["expected search results with a data list"]
        if not rows:
            return [f"no Motus records found for USDOT {usdot}"]
        first = rows[0] if isinstance(rows[0], dict) else {}
        found = str(first.get("dotNumber") or first.get("usdot_number") or "")
        if found and found != str(usdot):
            return [f"first hit USDOT {found} did not match {usdot}"]
        return []

    return check


def _require_list_or_data() -> Check:
    def check(result: HttpResult) -> list[str]:
        if isinstance(result.body, list):
            return []
        if isinstance(result.body, dict) and "data" in result.body:
            return []
        return ["expected a JSON list or an object with a data field"]

    return check


def _allow_empty_list() -> Check:
    def check(result: HttpResult) -> list[str]:
        if isinstance(result.body, list):
            return []
        return ["expected a JSON list"]

    return check


def _require_json_list() -> Check:
    def check(result: HttpResult) -> list[str]:
        if isinstance(result.body, list):
            return []
        return ["expected a JSON list"]

    return check


def _require_json_object_or_list() -> Check:
    def check(result: HttpResult) -> list[str]:
        if isinstance(result.body, (dict, list)):
            return []
        return ["expected JSON"]

    return check


def evaluate(result: HttpResult, case: dict[str, Any]) -> HttpResult:
    expected = case.get("expect_status", 200)
    notes: list[str] = []
    if result.status != expected:
        notes.append(f"expected HTTP {expected}, got {result.status}")
    if result.ok:
        for check in case.get("checks", []):
            notes.extend(check(result))
    result.notes = notes
    result.ok = result.ok and not notes
    if case.get("label"):
        result.notes.append(case["label"])
    return result


def run_cases(
    client: HttpClient,
    cases: Iterable[dict[str, Any]],
    fail_fast: bool,
) -> list[HttpResult]:
    results: list[HttpResult] = []
    for case in cases:
        result = evaluate(client.get(case["name"], case["url"]), case)
        results.append(result)
        if fail_fast and not result.ok:
            break
    return results


def print_result(result: HttpResult, raw: bool) -> None:
    status = "PASS" if result.ok else "FAIL"
    http = result.status if result.status is not None else "ERR"
    count = result.row_count
    count_bit = f" rows={count}" if count is not None else ""
    extra = ""
    if result.notes:
        extra = " | " + "; ".join(result.notes)
    error = f" | {result.error}" if result.error else ""
    print(
        f"[{status}] {result.name:42} {http} {result.elapsed_ms:7.0f}ms{count_bit}{error}{extra}"
    )
    if raw and result.body is not None:
        print(json.dumps(redact_sensitive(result.body), indent=2)[:4000])


def summarize(results: list[HttpResult]) -> int:
    passed = sum(1 for item in results if item.ok)
    failed = len(results) - passed
    print()
    print(f"Ran {len(results)} checks: {passed} passed, {failed} failed")
    return 1 if failed else 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    usdot = str(args.usdot).strip()
    name = str(args.name).strip()
    client = HttpClient(timeout=args.timeout)

    print(f"USDOT={usdot}  name={name}  suite={args.suite}")
    print()

    results: list[HttpResult] = []

    if args.suite in {"all", "motus"}:
        motus_results = run_cases(client, motus_cases(usdot, name, args.limit), args.fail_fast)
        results.extend(motus_results)
        entity_id = None
        for item in motus_results:
            if item.name == "motus.carriers.search.query.usdot" and item.body:
                entity_id = extract_entity_id(item.body)
                break
        if entity_id and not (args.fail_fast and any(not item.ok for item in motus_results)):
            results.extend(run_cases(client, motus_follow_up_cases(entity_id), args.fail_fast))
        elif args.suite == "motus" and not entity_id:
            print("[WARN] could not resolve Motus entityId; skipping record-detail calls")

    if args.suite in {"all", "soda"}:
        if not (args.fail_fast and any(not item.ok for item in results)):
            results.extend(run_cases(client, soda_cases(usdot, args.limit), args.fail_fast))

    if args.suite in {"all", "qcmobile"}:
        if not args.webkey:
            if args.suite == "qcmobile":
                print("QCMobile suite requires --webkey or FMCSA_WEBKEY")
                return 2
            print("[SKIP] QCMobile: set FMCSA_WEBKEY or pass --webkey to exercise lookup APIs")
        elif not (args.fail_fast and any(not item.ok for item in results)):
            results.extend(
                run_cases(client, qcmobile_cases(usdot, name, args.webkey), args.fail_fast)
            )

    for result in results:
        print_result(result, args.raw)
    return summarize(results)


if __name__ == "__main__":
    sys.exit(main())
