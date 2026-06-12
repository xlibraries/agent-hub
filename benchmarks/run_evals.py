#!/usr/bin/env python3
"""Golden eval suite runner — deterministic task replay, no LLM required.

Exits non-zero when any case fails, so CI doubles as regression testing.
"""

from __future__ import annotations

import argparse
import json
import sys

from slm.evals import GOLDEN_CASES, run_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="SLM golden eval suite")
    parser.add_argument("--json", action="store_true", help="Emit full JSON report")
    args = parser.parse_args()

    report = run_cases(GOLDEN_CASES)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        for result in report.results:
            mark = "PASS" if result.passed else "FAIL"
            print(
                f"[{mark}] {result.name:40} steps={result.steps_taken} "
                f"calls={result.model_calls} {result.latency_ms:.0f}ms — {result.detail}"
            )
        print(f"\n{report.passed}/{report.total} passed")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
