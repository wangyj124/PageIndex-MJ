from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from pathlib import Path

from .config import *
from .llm import *
from .logging_utils import *
from .pdf import *
from .tree_utils import *


WORD_FILE_SUFFIXES = {".doc", ".docx"}
WORD_TO_PDF_FORMAT = 17


def _convert_word_to_pdf_windows(word_file: Path, output_pdf_path: Path) -> Path:
    try:
        win32_client = importlib.import_module("win32com.client")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "当前为 Windows 环境，但未安装 pywin32，无法调用 Microsoft Word 转换 DOC/DOCX。"
        ) from exc

    word_app = None
    document = None

    try:
        word_app = win32_client.DispatchEx("Word.Application")
        word_app.Visible = False
        if hasattr(word_app, "DisplayAlerts"):
            word_app.DisplayAlerts = 0

        document = word_app.Documents.Open(str(word_file))
        if output_pdf_path.exists():
            output_pdf_path.unlink()
        document.SaveAs(str(output_pdf_path), FileFormat=WORD_TO_PDF_FORMAT)
    except Exception as exc:
        raise RuntimeError(f"使用 Microsoft Word 转换 PDF 失败: {exc}") from exc
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word_app is not None:
            try:
                word_app.Quit()
            except Exception:
                pass

    if not output_pdf_path.is_file():
        raise RuntimeError(f"Microsoft Word 未生成预期的 PDF 文件: {output_pdf_path}")

    return output_pdf_path.resolve()


def _convert_word_to_pdf_linux(word_file: Path, output_dir_path: Path, output_pdf_path: Path) -> Path:
    libreoffice_binary = shutil.which("libreoffice") or shutil.which("soffice")
    if not libreoffice_binary:
        raise RuntimeError(
            "当前为 Linux 环境，但未找到 LibreOffice。请先安装 LibreOffice，并确保 `libreoffice --headless` 可用。"
        )

    command = [
        libreoffice_binary,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir_path),
        str(word_file),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "当前为 Linux 环境，但无法执行 LibreOffice。请确认已正确安装并加入 PATH。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "使用 LibreOffice 转换 PDF 失败"
        if details:
            message = f"{message}: {details}"
        raise RuntimeError(message) from exc

    if not output_pdf_path.is_file():
        output_message = " ".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if isinstance(part, str) and part.strip()
        )
        message = f"LibreOffice 已执行，但未生成预期的 PDF 文件: {output_pdf_path}"
        if output_message:
            message = f"{message}。命令输出: {output_message}"
        raise RuntimeError(message)

    return output_pdf_path.resolve()


def convert_word_to_pdf(word_path: str, output_dir: str) -> str:
    """将 DOC/DOCX 文件转换为 PDF，并返回生成后的 PDF 绝对路径。"""
    word_file = Path(word_path).expanduser().resolve()
    output_dir_path = Path(output_dir).expanduser().resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)

    logger = JsonLogger(str(word_file), base_dir=str(output_dir_path / "logs"))
    system_name = platform.system()
    file_suffix = word_file.suffix.lower()

    if not word_file.is_file():
        raise FileNotFoundError(f"Word 文件不存在: {word_file}")
    if file_suffix not in WORD_FILE_SUFFIXES:
        raise ValueError(f"仅支持转换 .doc 或 .docx 文件，当前文件为: {word_file.name}")

    output_pdf_path = (output_dir_path / f"{word_file.stem}.pdf").resolve()

    logger.info(
        {
            "event": "word_to_pdf_started",
            "source_file": str(word_file),
            "target_file": str(output_pdf_path),
            "platform": system_name,
        }
    )

    try:
        if system_name == "Windows":
            converted_path = _convert_word_to_pdf_windows(word_file, output_pdf_path)
            backend = "microsoft_word"
        elif system_name == "Linux":
            converted_path = _convert_word_to_pdf_linux(word_file, output_dir_path, output_pdf_path)
            backend = "libreoffice"
        else:
            raise RuntimeError(
                f"当前操作系统 {system_name} 暂不支持 Word 转 PDF，仅支持 Windows 和 Linux。"
            )
    except Exception as exc:
        logger.exception(
            {
                "event": "word_to_pdf_failed",
                "source_file": str(word_file),
                "target_file": str(output_pdf_path),
                "platform": system_name,
                "error": str(exc),
            }
        )
        raise

    logger.info(
        {
            "event": "word_to_pdf_completed",
            "source_file": str(word_file),
            "target_file": str(converted_path),
            "platform": system_name,
            "backend": backend,
        }
    )
    return str(converted_path)
