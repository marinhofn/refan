"""Escrita atômica, locks e durabilidade (Fase E4, ROB-1/2/3)."""

import fcntl
import json
import os
from unittest import mock

import pytest

from src.utils.atomic_io import atomic_write_json, atomic_write_text, file_lock


class TestAtomicWrite:
    def test_writes_content_and_leaves_no_temp(self, tmp_path):
        target = tmp_path / "data.csv"
        atomic_write_text(target, "a,b\n1,2\n")
        assert target.read_text() == "a,b\n1,2\n"
        leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftovers == []

    def test_overwrites_atomically(self, tmp_path):
        target = tmp_path / "data.txt"
        target.write_text("velho")
        atomic_write_text(target, "novo")
        assert target.read_text() == "novo"

    def test_failure_preserves_original_and_cleans_temp(self, tmp_path):
        target = tmp_path / "data.txt"
        target.write_text("original intacto")
        with mock.patch("src.utils.atomic_io.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                atomic_write_text(target, "não publica")
        assert target.read_text() == "original intacto"
        assert [p for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []

    def test_json_roundtrip(self, tmp_path):
        target = tmp_path / "obj.json"
        atomic_write_json(target, {"chave": "valor", "n": 1})
        assert json.loads(target.read_text()) == {"chave": "valor", "n": 1}

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "f.txt"
        atomic_write_text(target, "x")
        assert target.read_text() == "x"


class TestFileLock:
    def test_lock_is_exclusive_while_held(self, tmp_path):
        target = tmp_path / "master.csv"
        with file_lock(target):
            lock_path = str(target) + ".lock"
            with open(lock_path, "w") as second:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(second.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_lock_released_after_context(self, tmp_path):
        target = tmp_path / "master.csv"
        with file_lock(target):
            pass
        with open(str(target) + ".lock", "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # não levanta


class TestCorruptTrackingQuarantine:
    """ROB-2: tracking corrompido é quarentenado com erro alto, não zerado
    em silêncio."""

    def test_corrupt_json_is_quarantined(self, tmp_path, monkeypatch, capsys):
        from src.handlers import data_handler as dh_module

        log_path = tmp_path / "analyzed_commits.json"
        log_path.write_text("{corrompido!!!", encoding="utf-8")

        handler = dh_module.DataHandler.__new__(dh_module.DataHandler)
        handler.analyzed_commits_log = str(log_path)
        result = handler._load_analyzed_commits()

        assert result == set()
        assert not log_path.exists()
        quarantined = list(tmp_path.glob("analyzed_commits.json.corrupt-*"))
        assert len(quarantined) == 1
        assert "corrompido" in capsys.readouterr().out


class TestSessionWriterFsync:
    def test_fsync_called_per_line_when_enabled(self, tmp_path, monkeypatch):
        from src.core.settings import settings
        from src.utils.persistence import SessionWriter

        monkeypatch.setattr(settings, "jsonl_fsync", True)
        writer = SessionWriter(str(tmp_path), session_name="s")
        with mock.patch("src.utils.persistence.os.fsync") as fsync:
            writer.append({"a": 1})
            fsync.assert_called_once()

    def test_truncated_line_logged_not_swallowed(self, tmp_path, caplog):
        from src.utils.persistence import SessionWriter

        writer = SessionWriter(str(tmp_path), session_name="s")
        writer.append({"ok": 1})
        with open(writer.path, "a", encoding="utf-8") as f:
            f.write('{"truncado": ')  # crash simulado no meio da linha
        import logging
        with caplog.at_level(logging.WARNING):
            records = writer.read_all()
        assert records == [{"ok": 1}]
        assert any("inválida" in m for m in caplog.messages)
