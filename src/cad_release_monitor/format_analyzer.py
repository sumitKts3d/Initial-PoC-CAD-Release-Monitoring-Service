from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FormatGap:
    format_name: str
    hoops_version: str | None
    competitor_name: str
    competitor_version: str | None
    gap_type: str  # "newer", "missing", "downgrade"


def load_matrix(path: str | Path) -> dict[str, dict[str, str]]:
    """Load format support matrix."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def version_key(version: str) -> tuple[int, ...]:
    """Parse version string into comparable tuple."""
    import re
    tokens = re.findall(r"\d+", version)
    if not tokens:
        return tuple()
    return tuple(int(part) for part in tokens)


def compare_versions(v1: str | None, v2: str | None) -> int:
    """
    Compare two version strings.
    Returns: -1 if v1 < v2, 0 if equal, 1 if v1 > v2, None if incomparable.
    """
    if not v1 or not v2:
        return None
    
    # Special cases for non-numeric versions
    if v1.lower() == v2.lower():
        return 0
    
    # Try numeric comparison
    k1 = version_key(v1)
    k2 = version_key(v2)
    
    if not k1 or not k2:
        return None  # Can't compare
    
    if k1 < k2:
        return -1
    elif k1 > k2:
        return 1
    else:
        return 0


def analyze_format_gaps(matrix: dict[str, dict[str, str]]) -> list[FormatGap]:
    """
    Analyze format support matrix and identify gaps where competitors support
    newer versions than HOOPS Exchange.
    """
    gaps: list[FormatGap] = []
    
    for format_name, support_map in matrix.items():
        hoops_version = support_map.get("HOOPS Exchange")
        
        for competitor_name, competitor_version in support_map.items():
            if competitor_name == "HOOPS Exchange":
                continue
            
            if not hoops_version:
                gaps.append(FormatGap(
                    format_name=format_name,
                    hoops_version=None,
                    competitor_name=competitor_name,
                    competitor_version=competitor_version,
                    gap_type="missing"
                ))
            else:
                cmp = compare_versions(hoops_version, competitor_version)
                if cmp == -1:  # Competitor has newer version
                    gaps.append(FormatGap(
                        format_name=format_name,
                        hoops_version=hoops_version,
                        competitor_name=competitor_name,
                        competitor_version=competitor_version,
                        gap_type="newer"
                    ))
                elif cmp == 1:  # HOOPS Exchange is ahead (good!)
                    pass
    
    return gaps


def print_gap_report(gaps: list[FormatGap]) -> None:
    """Print formatted report of format support gaps."""
    if not gaps:
        print("\n✓ HOOPS Exchange leads or matches all monitored format support levels.")
        return
    
    print("\n" + "=" * 80)
    print("Format Support Gap Analysis")
    print("=" * 80)
    
    # Group gaps by format
    by_format = {}
    for gap in gaps:
        if gap.format_name not in by_format:
            by_format[gap.format_name] = []
        by_format[gap.format_name].append(gap)
    
    for format_name in sorted(by_format.keys()):
        format_gaps = by_format[format_name]
        print(f"\n[{format_name}]")
        print(f"HOOPS Exchange: {format_gaps[0].hoops_version or 'Not supported'}")
        
        for gap in format_gaps:
            if gap.gap_type == "newer":
                status = "⚠ NEWER"
                print(f"  {status} - {gap.competitor_name}: {gap.competitor_version}")
            elif gap.gap_type == "missing":
                print(f"  ℹ  {gap.competitor_name}: {gap.competitor_version} (HOOPS doesn't support)")
    
    print("\n" + "=" * 80)
    print(f"Total gaps found: {len(gaps)}")
    newer_count = sum(1 for g in gaps if g.gap_type == "newer")
    if newer_count > 0:
        print(f"⚠ Formats where competitors support NEWER versions: {newer_count}")
