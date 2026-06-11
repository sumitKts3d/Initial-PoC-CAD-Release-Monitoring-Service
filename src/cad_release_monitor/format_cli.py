from __future__ import annotations

import argparse
import logging
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
        if format_name not in matrix:
            logger.error(f"Format '{format_name}' not found in matrix. Available formats: {', '.join(matrix.keys())}")
            print(f"ERROR: Format '{format_name}' not found in matrix.")
            print(f"Available formats: {', '.join(matrix.keys())}")
            return
        matrix = {format_name: matrix[format_name]}

    logger.info("Analyzing format support gaps...")
    gaps = analyze_format_gaps(matrix)

    print_gap_report(gaps)
    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
