"""
Tests for the text extraction module.
"""

import os
import tempfile
import pytest
from pathlib import Path

from core.extractor import extract_text_from_txt, extract_text


class TestTxtExtraction:
    def test_read_utf8_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("Ich lerne Deutsch.\nDas Haus ist groß.", encoding="utf-8")
        result = extract_text_from_txt(str(f))
        assert "Deutsch" in result
        assert "Haus" in result

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_text_from_txt("nonexistent_file.txt")


class TestExtractDispatch:
    def test_txt_dispatch(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hallo Welt", encoding="utf-8")
        assert "Hallo" in extract_text(str(f))

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("a,b,c", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            extract_text(str(f))
