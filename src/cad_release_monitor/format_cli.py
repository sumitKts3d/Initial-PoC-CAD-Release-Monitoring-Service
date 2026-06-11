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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    logger.info("Loading format support matrix...")
    matrix = load_matrix(args.matrix)
    logger.info(f"Loaded {len(matrix)} formats")

    logger.info("Analyzing format support gaps...")
    gaps = analyze_format_gaps(matrix)

    print_gap_report(gaps)
    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
