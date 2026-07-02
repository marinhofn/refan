"""Testes unitários para o script de reconciliação JSONL ↔ Supabase.

Cobre a leitura dos JSONL locais (estrutura output/models/<modelo>/
analises/sessions) e a lógica pura de comparação (Fase H6).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

_SCRIPT = Path(__file__).parent.parent / "scripts" / "data" / "reconcile_supabase.py"
_spec = importlib.util.spec_from_file_location("reconcile_supabase", _SCRIPT)
reconcile_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reconcile_mod)


def _write_session(tmp_path, model, session_name, records):
    sessions = tmp_path / model / "analises" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    path = sessions / f"{session_name}.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


class TestLoadLocalRecords:
    def test_loads_records_per_model(self, tmp_path):
        _write_session(tmp_path, "mistral", "s1", [
            {"hash": "aaa", "llm_classification": "PURE"},
            {"hash": "bbb", "llm_classification": "floss"},
        ])
        records = reconcile_mod.load_local_records(str(tmp_path))
        assert records == {
            ("mistral", "aaa"): "PURE",
            ("mistral", "bbb"): "FLOSS",
        }

    def test_dry_run_and_failed_are_excluded(self, tmp_path):
        _write_session(tmp_path, "mistral", "s1", [
            {"hash": "aaa", "llm_classification": "DRY_RUN"},
            {"hash": "bbb", "llm_classification": "FAILED"},
            {"hash": "ccc", "llm_classification": "PURE"},
        ])
        records = reconcile_mod.load_local_records(str(tmp_path))
        assert set(records) == {("mistral", "ccc")}

    def test_latest_session_wins_on_duplicate_hash(self, tmp_path):
        _write_session(tmp_path, "mistral", "session_2025-01-01_00-00-00",
                       [{"hash": "aaa", "llm_classification": "PURE"}])
        _write_session(tmp_path, "mistral", "session_2025-06-01_00-00-00",
                       [{"hash": "aaa", "llm_classification": "FLOSS"}])
        records = reconcile_mod.load_local_records(str(tmp_path))
        assert records[("mistral", "aaa")] == "FLOSS"

    def test_model_filter(self, tmp_path):
        _write_session(tmp_path, "mistral", "s1",
                       [{"hash": "aaa", "llm_classification": "PURE"}])
        _write_session(tmp_path, "gemma2_2b", "s1",
                       [{"hash": "bbb", "llm_classification": "FLOSS"}])
        records = reconcile_mod.load_local_records(str(tmp_path), model="mistral")
        assert set(records) == {("mistral", "aaa")}

    def test_missing_root_returns_empty(self, tmp_path):
        assert reconcile_mod.load_local_records(str(tmp_path / "nada")) == {}


class TestReconcile:
    def test_full_agreement_yields_empty_report(self):
        local = {("mistral", "aaa"): "PURE"}
        cloud = {("mistral", "aaa"): "PURE"}
        report = reconcile_mod.reconcile(local, cloud)
        assert report == {"local_only": [], "cloud_only": [], "divergent": []}

    def test_categorizes_differences(self):
        local = {
            ("mistral", "aaa"): "PURE",     # divergente
            ("mistral", "bbb"): "FLOSS",    # só local
            ("mistral", "ccc"): "PURE",     # acordo
        }
        cloud = {
            ("mistral", "aaa"): "FLOSS",
            ("mistral", "ccc"): "PURE",
            ("mistral", "ddd"): "PURE",     # só cloud
        }
        report = reconcile_mod.reconcile(local, cloud)
        assert report["local_only"] == [("mistral", "bbb")]
        assert report["cloud_only"] == [("mistral", "ddd")]
        assert report["divergent"] == [
            {"model": "mistral", "hash": "aaa", "local": "PURE", "cloud": "FLOSS"},
        ]
