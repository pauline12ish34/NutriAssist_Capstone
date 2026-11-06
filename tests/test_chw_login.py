"""Demo CHW sign-in: which IDs and codes are accepted."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from chw_login import DemoChwDirectory, code_is_valid, login_required, sign_in  # noqa: E402


def test_demo_file_has_only_made_up_ids():
    directory = DemoChwDirectory()
    assert len(directory) == 5
    assert directory.find("CHW-DEMO-001").district == "Gasabo"


def test_id_is_matched_whatever_the_case_and_spaces():
    assert DemoChwDirectory().find("  chw-demo-003 ").chw_id == "CHW-DEMO-003"


def test_inactive_and_unknown_ids_cannot_sign_in():
    directory = DemoChwDirectory()
    assert directory.find("CHW-DEMO-006") is None   # in the file, but no longer active
    assert directory.find("CHW-0001") is None


def test_default_code_and_a_secret_one(monkeypatch):
    monkeypatch.delenv("NUTRIASSIST_DEMO_CODE", raising=False)
    assert code_is_valid("123456") and code_is_valid(" 123456 ") and not code_is_valid("12345")
    monkeypatch.setenv("NUTRIASSIST_DEMO_CODE", "804512")
    assert code_is_valid("804512") and not code_is_valid("123456")


def test_sign_in_needs_both_the_id_and_the_code(monkeypatch):
    monkeypatch.delenv("NUTRIASSIST_DEMO_CODE", raising=False)
    directory = DemoChwDirectory()
    assert sign_in(directory, "CHW-DEMO-004", "123456").chw_id == "CHW-DEMO-004"
    assert sign_in(directory, "CHW-DEMO-004", "654321") is None
    assert sign_in(directory, "CHW-DEMO-999", "123456") is None


def test_login_can_be_turned_off(monkeypatch):
    monkeypatch.delenv("NUTRIASSIST_LOGIN", raising=False)
    assert login_required()
    for value in ("off", "OFF", "0", "false"):
        monkeypatch.setenv("NUTRIASSIST_LOGIN", value)
        assert not login_required()
