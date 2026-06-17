from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NUMBER_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


def _coerce_value(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    if not NUMBER_PATTERN.match(stripped):
        return stripped
    if "." in stripped:
        number = float(stripped)
        return int(number) if number.is_integer() else number
    return int(stripped)


def load_trend_csv(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv_dict_rows(path):
        rows.append({key: _coerce_value(value or "") for key, value in row.items()})
    return rows


def _read_csv_dict_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def preview_table(path: str | Path, sample_size: int = 5) -> dict[str, Any]:
    raw_rows = _read_csv_dict_rows(path)
    headers = list(raw_rows[0].keys()) if raw_rows else _read_csv_headers(path)
    return {
        "path": str(Path(path)),
        "row_count": len(raw_rows),
        "headers": headers,
        "sample_rows": raw_rows[:sample_size],
    }


def _read_csv_headers(path: str | Path) -> list[str]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def build_processed_summary_preview(rows: list[dict[str, Any]], preview_size: int = 5) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    numeric_columns = [
        column
        for column in columns
        if any(isinstance(row.get(column), (int, float)) and not isinstance(row.get(column), bool) for row in rows)
    ]
    return {
        "row_count": len(rows),
        "columns": columns,
        "numeric_columns": numeric_columns,
        "preview_rows": rows[:preview_size],
    }


def read_schema_xlsx(path: str | Path, preview_rows: int = 5) -> dict[str, Any]:
    workbook_path = Path(path)
    with ZipFile(workbook_path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_names, sheet_targets = _read_workbook_structure(archive)
        sheets = []
        for name, target in zip(sheet_names, sheet_targets, strict=True):
            raw_rows = _read_sheet_rows(archive, target, shared_strings)
            headers = raw_rows[0] if raw_rows else []
            preview = [dict(zip(headers, row)) for row in raw_rows[1 : 1 + preview_rows]] if headers else []
            sheets.append({
                "name": name,
                "headers": headers,
                "preview_rows": preview,
                "row_count": max(len(raw_rows) - 1, 0),
            })
    return {"path": str(workbook_path), "sheet_names": sheet_names, "sheets": sheets}


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("main:si", MAIN_NS):
        text = "".join(node.text or "" for node in item.findall(".//main:t", MAIN_NS))
        values.append(text)
    return values


def _read_workbook_structure(archive: ZipFile) -> tuple[list[str], list[str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_root.findall("rel:Relationship", REL_NS)
        if rel.attrib.get("Type") == f"{DOC_REL_NS}/worksheet"
    }
    sheet_names: list[str] = []
    sheet_targets: list[str] = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", MAIN_NS):
        rel_id = sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
        target = relationship_map.get(rel_id or "")
        if not target:
            continue
        sheet_names.append(sheet.attrib.get("name", Path(target).stem))
        sheet_targets.append(f"xl/{target}")
    return sheet_names, sheet_targets


def _read_sheet_rows(archive: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall("main:sheetData/main:row", MAIN_NS):
        values: list[str] = []
        for cell in row.findall("main:c", MAIN_NS):
            values.append(_read_cell_value(cell, shared_strings))
        rows.append(values)
    return rows


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.findtext("main:v", default="", namespaces=MAIN_NS)
    if cell.attrib.get("t") == "s" and value.isdigit():
        index = int(value)
        return shared_strings[index] if index < len(shared_strings) else ""
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="산불 공공데이터 적재 기초 프리뷰 도구")
    parser.add_argument("--trend-csv", type=Path, help="추세 CSV 파일 경로")
    parser.add_argument("--schema-xlsx", type=Path, help="스키마 XLSX 파일 경로")
    parser.add_argument("--sample-size", type=int, default=5, help="미리보기 행 수")
    args = parser.parse_args()

    result: dict[str, Any] = {}
    if args.trend_csv:
        trend_rows = load_trend_csv(args.trend_csv)
        result["trend_preview"] = preview_table(args.trend_csv, sample_size=args.sample_size)
        result["processed_summary"] = build_processed_summary_preview(trend_rows, preview_size=args.sample_size)
    if args.schema_xlsx:
        result["schema_preview"] = read_schema_xlsx(args.schema_xlsx, preview_rows=args.sample_size)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
