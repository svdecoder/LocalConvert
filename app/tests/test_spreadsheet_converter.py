import csv
from pathlib import Path

import pytest

from app.converters.documents import SpreadsheetConverter
from app.models import ConversionJob


@pytest.fixture()
def sample_csv(tmp_path) -> Path:
    path = tmp_path / "data.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "age"])
        writer.writerow(["Ada", "36"])
        writer.writerow(["Grace", "85"])
    return path


def test_csv_to_xlsx(sample_csv, tmp_path):
    out_dir = tmp_path / "out"
    job = ConversionJob(input_path=sample_csv, output_format="xlsx", output_dir=out_dir)
    converter = SpreadsheetConverter()
    result = converter.convert(job)
    assert result.success
    assert result.output_path.suffix == ".xlsx"

    import openpyxl

    wb = openpyxl.load_workbook(result.output_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("name", "age")
    assert rows[1] == ("Ada", "36")


def test_xlsx_to_csv_roundtrip(sample_csv, tmp_path):
    out_dir = tmp_path / "out"
    converter = SpreadsheetConverter()

    to_xlsx_job = ConversionJob(input_path=sample_csv, output_format="xlsx", output_dir=out_dir)
    xlsx_result = converter.convert(to_xlsx_job)
    assert xlsx_result.success

    to_csv_job = ConversionJob(input_path=xlsx_result.output_path, output_format="csv", output_dir=out_dir)
    csv_result = converter.convert(to_csv_job)
    assert csv_result.success

    with open(csv_result.output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["name", "age"]
    assert rows[1] == ["Ada", "36"]


def test_unsupported_pair_fails_gracefully(sample_csv, tmp_path):
    out_dir = tmp_path / "out"
    job = ConversionJob(input_path=sample_csv, output_format="docx", output_dir=out_dir)
    converter = SpreadsheetConverter()
    result = converter.convert(job)
    assert result.success is False
    assert result.error_message
