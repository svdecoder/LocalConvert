from pathlib import Path

from app.utils.fs import human_size, safe_stem, temp_workspace, unique_output_path


def test_unique_output_path_no_collision(tmp_path):
    p = unique_output_path(tmp_path, "report", ".pdf")
    assert p == tmp_path / "report.pdf"


def test_unique_output_path_avoids_overwrite(tmp_path):
    (tmp_path / "report.pdf").write_text("x")
    p = unique_output_path(tmp_path, "report", ".pdf")
    assert p == tmp_path / "report (1).pdf"
    assert not p.exists()


def test_unique_output_path_increments(tmp_path):
    (tmp_path / "report.pdf").write_text("x")
    (tmp_path / "report (1).pdf").write_text("x")
    p = unique_output_path(tmp_path, "report", ".pdf")
    assert p == tmp_path / "report (2).pdf"


def test_safe_stem_strips_illegal_chars():
    assert safe_stem(Path('weird:name*?.txt')) == "weirdname"


def test_safe_stem_preserves_unicode():
    assert safe_stem(Path("café_日本語.txt")) == "café_日本語"


def test_safe_stem_never_empty():
    assert safe_stem(Path("???.txt")) == "output"


def test_temp_workspace_cleans_up():
    captured = []
    with temp_workspace() as ws:
        assert ws.exists()
        (ws / "scratch.txt").write_text("data")
        captured.append(ws)
    assert not captured[0].exists()


def test_human_size():
    assert human_size(500) == "500 B"
    assert human_size(2048).endswith("KB")
    assert human_size(5 * 1024 * 1024).endswith("MB")
