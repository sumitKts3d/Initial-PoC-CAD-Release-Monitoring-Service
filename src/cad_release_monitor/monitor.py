from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


@dataclass
class SourceCheckResult:
    name: str
    url: str
    current_version: str | None
    detected_versions: list[str]
    newer_versions: list[str]
    latest_detected: str | None
    error: str | None = None


_VERSION_TOKEN_RE = re.compile(r"\d+(?:\.\d+){0,5}")


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def build_session(retries: int = 2, backoff_factor: float = 0.8) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_page_text(
    url: str,
    timeout: float = 20.0,
    verify_ssl: bool = True,
    retries: int = 2,
    backoff_factor: float = 0.8,
) -> str:
    if not verify_ssl:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    session = build_session(retries=retries, backoff_factor=backoff_factor)
    response = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout, verify=verify_ssl)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text(" ", strip=True)


def version_key(version: str) -> tuple[int, ...]:
    tokens = _VERSION_TOKEN_RE.findall(version)
    if not tokens:
        return tuple()
    # Use the first numeric chain found in a match candidate.
    return tuple(int(part) for part in tokens[0].split("."))


def dedupe_and_sort_versions(values: set[str]) -> list[str]:
    return sorted(values, key=version_key)


def dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if not isinstance(url, str):
            continue
        value = url.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def extract_versions(text: str, patterns: list[str]) -> list[str]:
    matches: set[str] = set()
    for pattern in patterns:
        regex = re.compile(pattern, flags=re.IGNORECASE)
        for match in regex.finditer(text):
            if match.groups():
                value = match.group(1).strip()
            else:
                value = match.group(0).strip()
            if _VERSION_TOKEN_RE.search(value):
                matches.add(value)
    return dedupe_and_sort_versions(matches)


def extract_versions_generic(text: str, name: str) -> list[str]:
    matches: set[str] = set()

    # Prefer versions that appear close to the source name.
    escaped_name = re.escape(name)
    named_regex = re.compile(
        rf"{escaped_name}[^\n\r]{{0,80}}?(\d+(?:\.\d+){{0,5}})",
        flags=re.IGNORECASE,
    )
    for match in named_regex.finditer(text):
        value = match.group(1).strip()
        if _VERSION_TOKEN_RE.search(value):
            matches.add(value)

    # Fallback: pick numeric version tokens in a tight window around name mentions.
    lowered_text = text.lower()
    lowered_name = name.lower()
    start = 0
    while True:
        idx = lowered_text.find(lowered_name, start)
        if idx == -1:
            break
        window_start = max(0, idx - 30)
        window_end = min(len(text), idx + len(name) + 100)
        window = text[window_start:window_end]
        for token in _VERSION_TOKEN_RE.findall(window):
            matches.add(token)
        start = idx + len(lowered_name)

    return dedupe_and_sort_versions(matches)


def parse_current_entry(entry: Any) -> tuple[str | None, list[str]]:
    if isinstance(entry, str):
        value = entry.strip()
        return (value or None), []

    if isinstance(entry, dict):
        version_candidate = entry.get("current_version", entry.get("version", ""))
        current_version = version_candidate.strip() if isinstance(version_candidate, str) else None

        source_urls_raw = entry.get("source_urls", entry.get("urls", []))
        source_urls: list[str] = []
        if isinstance(source_urls_raw, list):
            source_urls = [u for u in source_urls_raw if isinstance(u, str)]

        return (current_version or None), dedupe_urls(source_urls)

    return None, []


def filter_newer_versions(current_version: str, detected_versions: list[str]) -> list[str]:
    current_key = version_key(current_version)
    if not current_key:
        return []
    newer = [v for v in detected_versions if version_key(v) > current_key]
    return dedupe_and_sort_versions(set(newer))


def check_source(
    source: dict[str, Any],
    current_versions: dict[str, Any],
    timeout: float = 20.0,
) -> SourceCheckResult:
    name = source["name"]
    url = source["url"]
    fallback_urls = source.get("fallback_urls", [])
    patterns = source.get("patterns", [])
    verify_ssl = source.get("verify_ssl", True)
    retries = int(source.get("retries", 2))
    backoff_factor = float(source.get("backoff_factor", 0.8))
    source_timeout = float(source.get("timeout", timeout))
    current_entry = current_versions.get(name)
    current_version, custom_urls = parse_current_entry(current_entry)

    if not patterns:
        return SourceCheckResult(
            name=name,
            url=url,
            current_version=current_version,
            detected_versions=[],
            newer_versions=[],
            latest_detected=None,
            error="No regex patterns defined for this source",
        )

    configured_urls = [url] + [u for u in fallback_urls if isinstance(u, str) and u]
    candidate_urls = dedupe_urls(custom_urls + configured_urls)
    text: str | None = None
    used_url = url
    last_error: str | None = None
    detected_versions: list[str] = []

    for candidate_url in candidate_urls:
        try:
            text = fetch_page_text(
                url=candidate_url,
                timeout=source_timeout,
                verify_ssl=verify_ssl,
                retries=retries,
                backoff_factor=backoff_factor,
            )
            used_url = candidate_url
            detected_versions = extract_versions(text=text, patterns=patterns)
            if not detected_versions:
                detected_versions = extract_versions_generic(text=text, name=name)
            if detected_versions:
                break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    if text is None and not detected_versions:
        return SourceCheckResult(
            name=name,
            url=used_url,
            current_version=current_version,
            detected_versions=[],
            newer_versions=[],
            latest_detected=None,
            error=last_error or "Unable to fetch source",
        )

    latest_detected = detected_versions[-1] if detected_versions else None

    if current_version:
        newer_versions = filter_newer_versions(current_version, detected_versions)
    else:
        newer_versions = []

    return SourceCheckResult(
        name=name,
        url=used_url,
        current_version=current_version,
        detected_versions=detected_versions,
        newer_versions=newer_versions,
        latest_detected=latest_detected,
        error=None,
    )


def run_monitor(
    sources: list[dict[str, Any]],
    current_versions: dict[str, Any],
    timeout: float = 20.0,
) -> list[SourceCheckResult]:
    return [
        check_source(source=source, current_versions=current_versions, timeout=timeout)
        for source in sources
    ]
