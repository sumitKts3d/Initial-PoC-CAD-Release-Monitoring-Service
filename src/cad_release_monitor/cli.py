from __future__ import annotations

import argparse
import json
from pathlib import Path

from cad_release_monitor.monitor import load_json, run_monitor


def print_summary(results: list) -> None:
    total = len(results)
    errors = sum(1 for r in results if r.error)
    success = total - errors
    alerts = sum(1 for r in results if r.newer_versions)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total sources:     {total}")
    print(f"Successful:        {success}")
    print(f"Errors:            {errors}")
    print(f"Updates available: {alerts}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor official pages for CAD software/file-format version updates "
            "and compare against your current versions."
        )
    )
    parser.add_argument(
        "--sources",
        default="config/sources.json",
        help="Path to source definitions JSON file",
    )
    parser.add_argument(
        "--current",
        default="data/current_versions.json",
        help="Path to current versions JSON file",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds for each source",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional file path to save machine-readable results",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    sources = load_json(args.sources)
    current_versions = load_json(args.current)

    results = run_monitor(sources=sources, current_versions=current_versions, timeout=args.timeout)

    print("CAD Release Monitor - Report")
    print("=" * 60)

    for result in results:
        print(f"\n[{result.name}]")
        print(f"Source: {result.url}")

        if result.error:
            print(f"Status: ERROR - {result.error}")
            continue

        print(f"Current version: {result.current_version or 'Not provided'}")
        print(f"Latest detected: {result.latest_detected or 'Not found'}")

        if result.current_version and result.newer_versions:
            print("ALERT: New version(s) available -> " + ", ".join(result.newer_versions))
        elif result.current_version:
            print("Status: No newer version found")
        else:
            print("Status: Current version not provided, comparison skipped")

    print_summary(results)

    if args.output_json:
        payload = [
            {
                "name": r.name,
                "url": r.url,
                "current_version": r.current_version,
                "detected_versions": r.detected_versions,
                "newer_versions": r.newer_versions,
                "latest_detected": r.latest_detected,
                "error": r.error,
            }
            for r in results
        ]
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to: {output_path}")


if __name__ == "__main__":
    main()
