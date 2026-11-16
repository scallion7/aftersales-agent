"""Record the existing controlled browser scenario at a presentation-friendly pace.

Run from the repository root with python -m docs.showcase.record_demo.
The output directory must be new. No application configuration is changed.
"""

from __future__ import annotations

import argparse
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import Browser, BrowserType


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--step-ms", type=int, default=900)
    args = parser.parse_args()
    if not 0 <= args.step_ms <= 5000:
        parser.error("--step-ms must be between 0 and 5000")
    output = args.output.resolve()
    if output.exists():
        parser.error("Output exists; choose a new recording directory")
    output.mkdir(parents=True, exist_ok=False)

    original_launch = BrowserType.launch
    original_context = Browser.new_context

    def paced_launch(self, *positional, **keywords):
        return original_launch(
            self, *positional, **(keywords | {"slow_mo": args.step_ms})
        )

    def full_size_context(self, *positional, **keywords):
        return original_context(
            self,
            *positional,
            **(
                keywords
                | {
                    "viewport": {"width": 1366, "height": 1000},
                    "record_video_size": {"width": 1366, "height": 1000},
                }
            ),
        )

    selector = (
        "tests.test_platform_http.BrowserTests.test_customer_and_operator_real_api"
    )
    # Import the test after enabling the browser, before its skip decorator runs.
    with (
        patch.dict(
            os.environ,
            {"RUN_BROWSER_E2E": "1", "BROWSER_SCREENSHOT_DIR": str(output)},
        ),
        patch.object(BrowserType, "launch", paced_launch),
        patch.object(Browser, "new_context", full_size_context),
    ):
        suite = unittest.defaultTestLoader.loadTestsFromName(selector)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped or result.testsRun != 1:
        raise SystemExit("Recording failed; retain the output for diagnosis")
    for name in (
        "customer-demo.webm",
        "operator-demo.webm",
        "workspace.png",
        "workbench.png",
    ):
        if not (output / name).is_file() or (output / name).stat().st_size == 0:
            raise SystemExit("Missing recording artifact: " + name)
    (output / "recording.json").write_text(
        json.dumps(
            {
                "test": selector,
                "passed": True,
                "step_ms": args.step_ms,
                "video_size": {"width": 1366, "height": 1000},
                "model": "controlled loopback only",
                "data": "synthetic",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
