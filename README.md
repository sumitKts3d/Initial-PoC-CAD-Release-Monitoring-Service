# CAD Release Monitoring Service (PoC)

This is a small proof of concept that monitors CAD software releases and file format support across competing exchange tools. It has two main functions:

1. **Release Monitoring**: Scrapes official product pages for version updates
2. **Format Support Gap Analysis**: Identifies when competitors support newer file format versions than HOOPS Exchange

## What It Does

### Release Monitoring
- Loads monitored sources from `config/sources.json`.
- Loads your currently used versions from `data/current_versions.json`.
- Fetches each page and extracts version strings using source-specific patterns.
- Alerts when a detected version is newer than your current version.
- Optionally saves results as JSON for downstream automation.

### Format Support Gap Analysis
- Loads format support matrix from `data/format_support_matrix.json`.
- Compares HOOPS Exchange format support against competitors (Spatial, Datakit, CAdExchanger, 3D InterOp).
- Identifies formats where competitors support **newer versions** than HOOPS Exchange.
- Helps prioritize format support implementation roadmap.

## Project Structure

- `src/cad_release_monitor/monitor.py`: scraping and version-comparison logic.
- `src/cad_release_monitor/cli.py`: command-line interface for release monitoring.
- `src/cad_release_monitor/format_analyzer.py`: format support gap analysis logic.
- `src/cad_release_monitor/format_cli.py`: command-line interface for format gap analysis.
- `config/sources.json`: monitored software/file-format sources and regex patterns.
- `data/current_versions.json`: your baseline product versions.
- `data/format_support_matrix.json`: file format support matrix by tool.

## Quick Start

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

3. Run release monitoring (all sources):

```bash
python -m cad_release_monitor --sources config/sources.json --current data/current_versions.json
```

Or monitor a single format:

```bash
python -m cad_release_monitor --format JT --current data/current_versions.json
python -m cad_release_monitor --format PDFL
python -m cad_release_monitor --format "HOOPS Exchange"
```

4. Run format support gap analysis (all formats):

```bash
python -m cad_release_monitor.format_cli --matrix data/format_support_matrix.json
```

Or analyze a single format:

```bash
python -m cad_release_monitor.format_cli --format JT
python -m cad_release_monitor.format_cli --format "STEP AP 242"
```

5. Save monitoring results as JSON (optional):

```bash
python -m cad_release_monitor --sources config/sources.json --current data/current_versions.json --output-json out/report.json
python -m cad_release_monitor --format PDFL --output-json out/pdfl_report.json
```

## Using --format for Single Format Monitoring

Both the release monitor and format analyzer support `--format` parameter to focus on a single format:

### Release Monitor
```bash
# Monitor a specific software/file format
python -m cad_release_monitor --format Creo
python -m cad_release_monitor --format "STEP AP 242"
python -m cad_release_monitor --format PDFL --timeout 30

# Available formats can be found in config/sources.json
# Formats include: Creo, NX, CATIA, JT, Solidworks, STEP AP 242, IFC, Inventor, ODA, PDFL, 
# HOOPS Exchange, Spatial, Datakit, CAdExchanger, 3D InterOp, LibreCAD
```

### Format Gap Analyzer
```bash
# Analyze format support gaps for a single format
python -m cad_release_monitor.format_cli --format JT
python -m cad_release_monitor.format_cli --format "ACIS SAT"

# Available formats in matrix can be found in data/format_support_matrix.json
# Formats include: JT, STEP AP 242, IGES, ACIS SAT, Parasolid, DWG/DXF, IFC
```

**Benefits:**
- Faster execution when monitoring a single format
- Focused output for specific needs
- Useful for CI/CD pipelines or scheduled tasks targeting specific formats
- Easier to integrate into notification workflows

## How To Customize

### Release Monitoring

- Add/remove monitored items in `config/sources.json`.
- Tune each source's `patterns` to reduce false positives.
- `data/current_versions.json` supports two formats:
	- Simple (backward compatible):

```json
{
	"Creo": "12.4.0.0"
}
```

	- Extended (optional per-format source URLs):

```json
{
	"Creo": {
		"current_version": "12.4.0.0",
		"source_urls": [
			"https://example.com/creo-release-notes",
			"https://example.com/creo-whats-new"
		]
	}
}
```

	When `source_urls` are provided, the monitor tries those URLs first, then the URLs from `config/sources.json`. If source-specific regex patterns do not find a version, it falls back to a generic version extraction near the source name.
- Add optional reliability keys per source in `config/sources.json`:
	- `fallback_urls`: alternate pages to try when primary URL fails.
	- `retries`: number of HTTP retries for transient failures (default: 2).
	- `backoff_factor`: retry wait multiplier (default: 0.8).
	- `timeout`: HTTP timeout in seconds for this source (default: from `--timeout` flag).
	- `verify_ssl`: set to `false` only when a source has certificate issues.
	- `discovery_urls`: stable index/tag pages to crawl for fresh article links.
	- `discovery_link_patterns`: regex filters applied to discovered links and anchor text.
	- `discovery_allowed_domains`: optional domain allowlist for discovered links.
	- `max_discovered_urls`: cap discovered links per run (default: 8).
	- `use_generic_fallback`: set `false` when generic extraction is too noisy for a source.
- Update `data/current_versions.json` with your current in-use versions.

Example dynamic discovery source config:

```json
{
	"name": "JT",
	"url": "https://www.digitalengineering247.com/topic/tag/3D-Interoperability",
	"discovery_urls": [
		"https://www.digitalengineering247.com/topic/tag/3D-Interoperability"
	],
	"discovery_link_patterns": [
		"spatial-releases-\\d{4}",
		"Spatial\\s+Releases\\s+\\d{4}"
	],
	"discovery_allowed_domains": [
		"digitalengineering247.com"
	],
	"max_discovered_urls": 8,
	"use_generic_fallback": false,
	"patterns": [
		"\\bJT\\s*(?:v(?:ersion)?\\s*)?(\\d+(?:\\.\\d+){1,3})\\b"
	]
}
```

### Format Support Gap Analysis

- Edit `data/format_support_matrix.json` to track format versions supported by each tool.
- Structure: `{"FormatName": {"ToolName": "SupportedVersion"}}`
- Add/remove formats and tools as needed.
- Format support matrix can be manually maintained or populated from source monitoring results.
- For production reliability, consider:
  - Source-specific parsers for higher precision
  - Automated format version extraction from documentation
  - Scheduling via Windows Task Scheduler or cron
  - Notification integrations (email, Teams, Slack)
  - Database storage for historical trends
## Notes and Limitations

- Some official sites are highly dynamic or protected by anti-bot measures.
- Regex-based extraction is intentionally lightweight for PoC speed.
- Per-source configuration keys (`timeout`, `retries`, `backoff_factor`, etc.) allow fine-tuning for slow or unstable endpoints.
- This PoC now includes retry, fallback URL, per-source timeout, and summary reporting support.
- For production reliability, consider source-specific parsers, retry/backoff, and scheduling/notification integrations (email, Teams, Slack).
