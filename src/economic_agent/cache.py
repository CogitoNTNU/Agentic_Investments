"""One completed analysis per ticker, stored locally as JSON."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from src.economic_agent.schemas import EconomicAnalysis

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "economic_analysis"
# Increment when changing analysis prompts or logic to invalidate old results.
ANALYSIS_VERSION = 1


def load_analysis(report: dict) -> dict | None:
    path = CACHE_DIR / f"{report['ticker']}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict):
            return None
        if cached.get("analysis_version") != ANALYSIS_VERSION:
            return None
        if any(cached.get(key) != value for key, value in report.items()):
            return None
        datetime.fromisoformat(cached["analyzed_at"])
        EconomicAnalysis.model_validate(cached)
        return cached
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        # Missing, old or damaged cache files are regenerated.
        return None


def save_analysis(result: dict) -> dict:
    EconomicAnalysis.model_validate(result)
    result = {
        **result,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "analysis_version": ANALYSIS_VERSION,
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{result['ticker']}.json"
    # Replace only after the complete JSON is written. Each call gets its own temp file.
    with NamedTemporaryFile(dir=CACHE_DIR, suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return result
