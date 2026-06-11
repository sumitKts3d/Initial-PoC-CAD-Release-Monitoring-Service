from __future__ import annotations

import argparse
import difflib
import json
import logging
import re
from pathlib import Path

from cad_release_monitor.monitor import load_json, run_monitor

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


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


def _normalize_name(value: str) -> str:
    lowered = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _resolve_source_name(query: str, sources: list[dict]) -> tuple[str | None, list[str]]:
    names = [s.get("name", "") for s in sources if s.get("name")]
    if not names:
        return None, []

    q = query.strip()
    q_norm = _normalize_name(q)

    for name in names:
        if name.lower() == q.lower():
            return name, []

    for name in names:
        if _normalize_name(name) == q_norm:
            return name, []

    contains_matches = [
        name
        for name in names
        if q_norm and (q_norm in _normalize_name(name) or _normalize_name(name) in q_norm)
    ]
    if len(contains_matches) == 1:
        return contains_matches[0], []
    if len(contains_matches) > 1:
        return None, sorted(contains_matches)

    normalized_to_name = {_normalize_name(name): name for name in names}
    close = difflib.get_close_matches(q_norm, list(normalized_to_name.keys()), n=5, cutoff=0.55)
    if close:
        best = normalized_to_name[close[0]]
        return best, [normalized_to_name[c] for c in close[1:]]

    return None, []


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
    parser.add_argument(
        "--format",
        default="",
        help="Optional: monitor only a specific format/source (e.g., JT, Creo, PDFL). If omitted, monitors all sources.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    sources = load_json(args.sources)
    current_versions = load_json(args.current)
    logger = logging.getLogger(__name__)

    # Filter sources by format if specified
    if args.format:
        format_name = args.format.strip()
        resolved_name, related = _resolve_source_name(format_name, sources)
        if not resolved_name:
            logger.error(f"Format '{format_name}' not found in sources. Available formats: {', '.join(s.get('name', 'Unknown') for s in sources)}")
            print(f"ERROR: Format '{format_name}' not found in sources.")
            if related:
                print(f"Did you mean one of: {', '.join(related)}")
            else:
                print(f"Available formats: {', '.join(s.get('name', 'Unknown') for s in sources)}")
            return
        filtered = [s for s in sources if s.get("name", "") == resolved_name]
        sources = filtered
        if format_name.lower() != resolved_name.lower():
            logger.info(f"Resolved format '{format_name}' to '{resolved_name}'")
            print(f"Resolved format: {resolved_name}")

    logger.info(f"Starting monitoring of {len(sources)} source(s)...")
    print("\nCAD Release Monitor - Report")
    print("=" * 60)

    results = []
    for idx, source in enumerate(sources, start=1):
        source_name = source.get("name", "Unknown")
        logger.info(f"[{idx}/{len(sources)}] Looking for format - {source_name}...")

        from cad_release_monitor.monitor import check_source
        result = check_source(source=source, current_versions=current_versions, timeout=args.timeout)
        results.append(result)

        # Print result immediately after checking
        print(f"\n[{source_name}]")
        print(f"Source: {result.url}")

        if result.error:
            print(f"Status: ERROR - {result.error}")
            logger.warning(f"  {source_name}: ERROR - {result.error}")
        else:
            print(f"Current version: {result.current_version or 'Not provided'}")
            print(f"Latest detected: {result.latest_detected or 'Not found'}")

            if result.current_version and result.newer_versions:
                alert_msg = f"New version(s) available -> {', '.join(result.newer_versions)}"
                print(f"ALERT: {alert_msg}")
                logger.info(f"  {source_name}: ALERT - {alert_msg}")
            elif result.current_version:
                print("Status: No newer version found")
                logger.info(f"  {source_name}: No newer version found")
            else:
                print("Status: Current version not provided, comparison skipped")
                logger.info(f"  {source_name}: Comparison skipped (no current version)")

    print_summary(results)
    logger.info("Monitoring complete.")

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
