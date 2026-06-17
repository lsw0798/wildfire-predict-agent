from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ingest_wildfire_public_data.py"


spec = importlib.util.spec_from_file_location("ingest_wildfire_public_data", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _write_minimal_xlsx(path: Path) -> None:
    shared_strings = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"4\" uniqueCount=\"4\">"
        "<si><t>field</t></si>"
        "<si><t>description</t></si>"
        "<si><t>year</t></si>"
        "<si><t>발생 연도</t></si>"
        "</sst>"
    )
    workbook = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets><sheet name=\"Schema\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>"
    )
    workbook_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" "
        "Target=\"worksheets/sheet1.xml\"/>"
        "<Relationship Id=\"rId2\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" "
        "Target=\"sharedStrings.xml\"/>"
        "</Relationships>"
    )
    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
        "Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )
    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/sharedStrings.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>"
        "</Types>"
    )
    sheet = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<sheetData>"
        "<row r=\"1\"><c r=\"A1\" t=\"s\"><v>0</v></c><c r=\"B1\" t=\"s\"><v>1</v></c></row>"
        "<row r=\"2\"><c r=\"A2\" t=\"s\"><v>2</v></c><c r=\"B2\" t=\"s\"><v>3</v></c></row>"
        "</sheetData></worksheet>"
    )

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/sharedStrings.xml", shared_strings)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def test_preview_table_reports_headers_row_count_and_sample(tmp_path: Path):
    csv_path = tmp_path / "trend.csv"
    csv_path.write_text("year,incidents,area\n2023,10,12.5\n2024,20,30.0\n", encoding="utf-8")

    preview = module.preview_table(csv_path, sample_size=1)

    assert preview["row_count"] == 2
    assert preview["headers"] == ["year", "incidents", "area"]
    assert preview["sample_rows"] == [{"year": "2023", "incidents": "10", "area": "12.5"}]


def test_load_trend_csv_normalizes_numeric_values_and_builds_summary(tmp_path: Path):
    csv_path = tmp_path / "trend.csv"
    csv_path.write_text(
        "year,incidents,area_ha,notes\n2023,10,12.5,alpha\n2024,20,30,beta\n",
        encoding="utf-8",
    )

    rows = module.load_trend_csv(csv_path)
    summary = module.build_processed_summary_preview(rows, preview_size=2)

    assert rows == [
        {"year": 2023, "incidents": 10, "area_ha": 12.5, "notes": "alpha"},
        {"year": 2024, "incidents": 20, "area_ha": 30, "notes": "beta"},
    ]
    assert summary["row_count"] == 2
    assert summary["columns"] == ["year", "incidents", "area_ha", "notes"]
    assert summary["numeric_columns"] == ["year", "incidents", "area_ha"]
    assert summary["preview_rows"][1]["area_ha"] == 30


def test_read_schema_xlsx_extracts_sheet_names_headers_and_preview_rows(tmp_path: Path):
    xlsx_path = tmp_path / "schema.xlsx"
    _write_minimal_xlsx(xlsx_path)

    schema = module.read_schema_xlsx(xlsx_path, preview_rows=2)

    assert schema["sheet_names"] == ["Schema"]
    assert schema["sheets"][0]["headers"] == ["field", "description"]
    assert schema["sheets"][0]["preview_rows"] == [{"field": "year", "description": "발생 연도"}]
