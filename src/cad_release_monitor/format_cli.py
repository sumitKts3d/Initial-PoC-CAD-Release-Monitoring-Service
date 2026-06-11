from __future__ import annotations

import argparse
import difflib
import logging
import re
from pathlib import Path

from cad_release_monitor.format_analyzer import (
    analyze_format_gaps,
    load_matrix,
    print_gap_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _normalize_name(value: str) -> str:
    lowered = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _resolve_matrix_format(query: str, matrix_keys: list[str]) -> tuple[str | None, list[str]]:
    if not matrix_keys:
        return None, []

    q = query.strip()
    q_norm = _normalize_name(q)

    for key in matrix_keys:
        if key.lower() == q.lower():
            return key, []

    for key in matrix_keys:
        if _normalize_name(key) == q_norm:
            return key, []

    contains_matches = [
        key
        for key in matrix_keys
        if q_norm and (q_norm in _normalize_name(key) or _normalize_name(key) in q_norm)
    ]
    if len(contains_matches) == 1:
        return contains_matches[0], []
    if len(contains_matches) > 1:
        return None, sorted(contains_matches)

    normalized_to_key = {_normalize_name(key): key for key in matrix_keys}
    close = difflib.get_close_matches(q_norm, list(normalized_to_key.keys()), n=5, cutoff=0.55)
    if close:
        best = normalized_to_key[close[0]]
        return best, [normalized_to_key[c] for c in close[1:]]

    return None, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze file format support across CAD exchange tools. "
            "Identifies gaps where competitors support newer format versions than HOOPS Exchange."
        )
    )
    parser.add_argument(
        "--matrix",
        default="data/format_support_matrix.json",
        help="Path to format support matrix JSON file",
    )
    parser.add_argument(
        "--format",
        default="",
        help="Optional: analyze only a specific format (e.g., JT, STEP AP 242, ACIS SAT). If omitted, analyzes all formats.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    logger.info("Loading format support matrix...")
    matrix = load_matrix(args.matrix)
    logger.info(f"Loaded {len(matrix)} formats")

    # Filter matrix by format if specified
    if args.format:
        format_name = args.format.strip()
        resolved_name, related = _resolve_matrix_format(format_name, list(matrix.keys()))
        if not resolved_name:
            logger.error(f"Format '{format_name}' not found in matrix. Available formats: {', '.join(matrix.keys())}")
            print(f"ERROR: Format '{format_name}' not found in matrix.")
            if related:
                print(f"Did you mean one of: {', '.join(related)}")
            else:
                print(f"Available formats: {', '.join(matrix.keys())}")
            return
        matrix = {resolved_name: matrix[resolved_name]}
        if format_name.lower() != resolved_name.lower():
            logger.info(f"Resolved format '{format_name}' to '{resolved_name}'")
            print(f"Resolved format: {resolved_name}")

    logger.info("Analyzing format support gaps...")
    gaps = analyze_format_gaps(matrix)

    print_gap_report(gaps)
    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
