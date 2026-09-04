from app.utils.dependencies import check_executable, check_python_package, clear_cache, missing_from


def test_check_python_package_available():
    clear_cache()
    status = check_python_package("PIL")
    assert status.available is True
    assert status.kind == "python_package"


def test_check_python_package_missing():
    clear_cache()
    status = check_python_package("definitely_not_a_real_package_xyz")
    assert status.available is False
    assert status.hint


def test_check_executable_missing():
    clear_cache()
    status = check_executable("definitely_not_a_real_binary_xyz")
    assert status.available is False


def test_missing_from_mixed_list():
    clear_cache()
    missing = missing_from(["py:PIL", "py:definitely_not_a_real_package_xyz", "definitely_not_a_real_binary_xyz"])
    names = {m.name for m in missing}
    assert "definitely_not_a_real_package_xyz" in names
    assert "definitely_not_a_real_binary_xyz" in names
    assert "PIL" not in names
