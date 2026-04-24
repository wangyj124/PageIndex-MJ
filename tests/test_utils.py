from types import SimpleNamespace

import pytest

import pageindex.utils as utils


class DummyLogger:
    def __init__(self, file_path, base_dir="artifacts/logs"):
        self.file_path = file_path
        self.base_dir = base_dir
        self.events = []

    def info(self, message, *args, **kwargs):
        self.events.append(("info", message))

    def error(self, message, *args, **kwargs):
        self.events.append(("error", message))

    def exception(self, message, *args, **kwargs):
        self.events.append(("exception", message))


def test_convert_word_to_pdf_uses_libreoffice_on_linux(monkeypatch, tmp_path):
    word_path = tmp_path / "contract.docx"
    word_path.write_bytes(b"word-content")
    output_dir = tmp_path / "output"
    captured = {}

    def fake_run(command, check, capture_output, text):
        captured["command"] = command
        captured["check"] = check
        captured["capture_output"] = capture_output
        captured["text"] = text
        generated_pdf = output_dir / "contract.pdf"
        generated_pdf.parent.mkdir(parents=True, exist_ok=True)
        generated_pdf.write_bytes(b"%PDF-1.4\nlinux\n")
        return SimpleNamespace(stdout="convert ok", stderr="")

    monkeypatch.setattr(utils, "JsonLogger", DummyLogger)
    monkeypatch.setattr(utils.platform, "system", lambda: "Linux")
    monkeypatch.setattr(utils.shutil, "which", lambda name: "/usr/bin/libreoffice" if name == "libreoffice" else None)
    monkeypatch.setattr(utils.subprocess, "run", fake_run)

    result = utils.convert_word_to_pdf(str(word_path), str(output_dir))

    assert result == str((output_dir / "contract.pdf").resolve())
    assert captured["command"] == [
        "/usr/bin/libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir.resolve()),
        str(word_path.resolve()),
    ]
    assert captured["check"] is True
    assert captured["capture_output"] is True
    assert captured["text"] is True


def test_convert_word_to_pdf_raises_friendly_error_when_libreoffice_missing(monkeypatch, tmp_path):
    word_path = tmp_path / "contract.doc"
    word_path.write_bytes(b"word-content")

    monkeypatch.setattr(utils, "JsonLogger", DummyLogger)
    monkeypatch.setattr(utils.platform, "system", lambda: "Linux")
    monkeypatch.setattr(utils.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="LibreOffice"):
        utils.convert_word_to_pdf(str(word_path), str(tmp_path / "output"))


def test_convert_word_to_pdf_raises_friendly_error_when_pywin32_missing(monkeypatch, tmp_path):
    word_path = tmp_path / "contract.docx"
    word_path.write_bytes(b"word-content")

    def fake_import_module(module_name):
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(utils, "JsonLogger", DummyLogger)
    monkeypatch.setattr(utils.platform, "system", lambda: "Windows")
    monkeypatch.setattr(utils.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="pywin32"):
        utils.convert_word_to_pdf(str(word_path), str(tmp_path / "output"))
