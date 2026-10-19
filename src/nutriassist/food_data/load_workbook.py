"""Load and validate the nutritionist workbook without changing the raw source."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_WORKBOOK = Path("data/raw/food_dataset.xlsx")
DEFAULT_INTERIM_DIR = Path("data/processed/interim")
VALIDATION_REPORT = Path("data/processed/validation_report.md")


def snake_case(value: object) -> str:
    """Convert a workbook column label to a stable snake_case name."""
    text = re.sub(r"[^0-9A-Za-z]+", "_", str(value).strip())
    text = re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unnamed_column"


def _unique_names(names: Iterable[str]) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        result.append(name if counts[name] == 1 else f"{name}_{counts[name]}")
    return result


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add normalized columns while preserving each original value in raw_* columns."""
    result = frame.copy()
    normalized = _unique_names(snake_case(column) for column in frame.columns)
    for original, normalized_name in zip(frame.columns, normalized):
        result[f"raw_{normalized_name}"] = frame[original]
    result.columns = list(frame.columns) + [f"raw_{name}" for name in normalized]
    result = result.rename(columns=dict(zip(frame.columns, normalized)))
    for column in normalized:
        if pd.api.types.is_string_dtype(result[column]):
            result[column] = result[column].str.strip()
    return result


def _check_values(sheet_name: str, frame: pd.DataFrame, warnings: list[str]) -> None:
    food_column = "food"
    if food_column not in frame:
        warnings.append(f"- `{sheet_name}`: missing required `food` column; cross-sheet checks skipped.")
        return

    duplicate_count = int(frame[food_column].duplicated(keep=False).sum())
    if duplicate_count:
        message = f"- `{sheet_name}`: {duplicate_count} rows have duplicate food names."
        warnings.append(message)
        LOGGER.warning(message)

    numeric_columns = frame.select_dtypes(include="number").columns
    for column in numeric_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        negative_count = int((values < 0).sum())
        over_100_count = int((values > 100).sum())
        if negative_count or over_100_count:
            message = (
                f"- `{sheet_name}.{column}`: {negative_count} negative value(s), "
                f"{over_100_count} value(s) over 100."
            )
            warnings.append(message)
            LOGGER.warning(message)


def _write_validation_report(warnings: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Workbook validation report",
        "",
        "Warnings are informational; loading continues after validation warnings.",
        "",
    ]
    lines.extend(warnings or ["No validation warnings were found."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_workbook(
    workbook_path: str | Path = DEFAULT_WORKBOOK,
    ignored_sheets: Iterable[str] = (),
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    validation_report: str | Path = VALIDATION_REPORT,
) -> dict[str, pd.DataFrame]:
    """Read every non-ignored workbook sheet and write traceable interim CSVs."""
    workbook = Path(workbook_path)
    if not workbook.exists():
        raise FileNotFoundError(f"Nutrition workbook not found: {workbook}")

    ignored = set(ignored_sheets)
    interim = Path(interim_dir)
    warnings: list[str] = []
    loaded: dict[str, pd.DataFrame] = {}
    excel = pd.ExcelFile(workbook, engine="openpyxl")
    sheet_foods: dict[str, set[str]] = {}

    for sheet_name in excel.sheet_names:
        if sheet_name in ignored:
            continue
        raw = pd.read_excel(excel, sheet_name=sheet_name, header=0)
        raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")
        frame = _normalise_columns(raw)
        frame.insert(0, "source_row", frame.index.to_series() + 2)
        frame.insert(0, "source_sheet", sheet_name)
        _check_values(sheet_name, frame, warnings)

        if "food" in frame:
            sheet_foods[sheet_name] = set(frame["food"].dropna().astype(str).str.strip())
        loaded[sheet_name] = frame
        interim.mkdir(parents=True, exist_ok=True)
        frame.to_csv(interim / f"{sheet_name}.csv", index=False)

    names = list(sheet_foods)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if not sheet_foods[first].intersection(sheet_foods[second]):
                message = f"- No matching food names between `{first}` and `{second}`."
                warnings.append(message)
                LOGGER.warning(message)

    _write_validation_report(warnings, Path(validation_report))
    return loaded
