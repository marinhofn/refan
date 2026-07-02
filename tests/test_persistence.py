"""Testes unitários para SessionWriter e merge_jsonl_to_csv (src/utils/persistence.py).

Primeira cobertura da camada de persistência incremental JSONL (Fase H4
do HARDENING_PLAN.md) — o mecanismo crash-safe que serve de fallback
quando o Supabase está indisponível. Tudo executa em tmp_path.
"""

import json
import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

import pandas as pd

from src.utils.persistence import SessionWriter, merge_jsonl_to_csv


class TestSessionWriter:
    def test_append_creates_file_and_increments_count(self, tmp_path):
        writer = SessionWriter(str(tmp_path), session_name="s1")
        assert writer.count == 0

        writer.append({"hash": "aaa", "llm_classification": "PURE"})
        writer.append({"hash": "bbb", "llm_classification": "FLOSS"})

        assert writer.count == 2
        assert (tmp_path / "s1.jsonl").exists()

    def test_auto_session_name_when_omitted(self, tmp_path):
        writer = SessionWriter(str(tmp_path))
        writer.append({"hash": "aaa"})
        assert writer.file_path.name.startswith("session_")
        assert writer.file_path.suffix == ".jsonl"

    def test_creates_nested_sessions_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "sessions"
        SessionWriter(str(nested), session_name="s1")
        assert nested.is_dir()

    def test_read_all_roundtrip(self, tmp_path):
        writer = SessionWriter(str(tmp_path), session_name="s1")
        records = [
            {"hash": "aaa", "llm_classification": "PURE"},
            {"hash": "bbb", "llm_classification": "FLOSS", "justificativa": "ação"},
        ]
        for r in records:
            writer.append(r)

        assert writer.read_all() == records

    def test_read_all_skips_corrupted_lines(self, tmp_path):
        """Linha truncada (ex.: CTRL+C no meio da escrita) não invalida a sessão."""
        writer = SessionWriter(str(tmp_path), session_name="s1")
        writer.append({"hash": "aaa"})
        with open(writer.file_path, "a", encoding="utf-8") as f:
            f.write('{"hash": "bbb", "trunc\n')
        writer.append({"hash": "ccc"})

        hashes = [r["hash"] for r in writer.read_all()]
        assert hashes == ["aaa", "ccc"]

    def test_read_all_missing_file_returns_empty(self, tmp_path):
        writer = SessionWriter(str(tmp_path), session_name="nunca-escrito")
        assert writer.read_all() == []


class TestMergeJsonlToCsv:
    @pytest.fixture
    def master_csv(self, tmp_path):
        path = tmp_path / "master.csv"
        pd.DataFrame({
            "hash": ["aaa", "bbb", "ccc"],
            "llm_analysis": ["", "", ""],
        }).to_csv(path, index=False)
        return path

    @pytest.fixture
    def session_jsonl(self, tmp_path):
        path = tmp_path / "session.jsonl"
        records = [
            {"hash": "aaa", "llm_classification": "PURE"},
            {"hash": "ccc", "llm_classification": "FLOSS"},
            {"hash": "zzz", "llm_classification": "PURE"},  # ausente do CSV
        ]
        path.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
        )
        return path

    def test_updates_only_matching_hashes(self, master_csv, session_jsonl):
        updated = merge_jsonl_to_csv(str(session_jsonl), str(master_csv))

        assert updated == 2
        df = pd.read_csv(master_csv)
        assert df.loc[df["hash"] == "aaa", "llm_analysis"].iloc[0] == "PURE"
        assert df.loc[df["hash"] == "ccc", "llm_analysis"].iloc[0] == "FLOSS"
        assert pd.isna(df.loc[df["hash"] == "bbb", "llm_analysis"].iloc[0]) or \
            df.loc[df["hash"] == "bbb", "llm_analysis"].iloc[0] == ""

    def test_remerge_is_idempotent(self, master_csv, session_jsonl):
        merge_jsonl_to_csv(str(session_jsonl), str(master_csv))
        updated_again = merge_jsonl_to_csv(str(session_jsonl), str(master_csv))

        df = pd.read_csv(master_csv)
        assert updated_again == 2          # mesmas linhas tocadas
        assert len(df) == 3                # nenhuma linha duplicada
        assert df.loc[df["hash"] == "aaa", "llm_analysis"].iloc[0] == "PURE"

    def test_empty_jsonl_returns_zero(self, master_csv, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        assert merge_jsonl_to_csv(str(empty), str(master_csv)) == 0

    def test_corrupted_lines_are_skipped(self, master_csv, tmp_path):
        path = tmp_path / "mixed.jsonl"
        path.write_text(
            '{"hash": "aaa", "llm_classification": "PURE"}\n'
            "linha corrompida\n",
            encoding="utf-8",
        )
        assert merge_jsonl_to_csv(str(path), str(master_csv)) == 1
