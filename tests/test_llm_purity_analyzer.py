"""Fluxo de sessão do LLMPurityAnalyzer (Fase E2, VAL-2/VAL-6 + dry-run).

Primeiro conjunto de testes do orquestrador central (antes: zero cobertura —
QUA-2). Handlers são substituídos por stubs; nenhum teste toca rede, Ollama
ou os CSVs reais do projeto.

Regressões cobertas:
- falha do LLM era gravada como 'floss' (rótulo fabricado com confidence
  'low'); agora é FAILED com error_type e success=False;
- dry-run mutava o CSV master rastreado (gravou 'DRY_RUN' em jul/2026);
  agora o master é intocado e o registro simulado vai só para o JSONL;
- FAILED/ERROR ficavam em limbo permanente (nem pendentes, nem completos,
  nunca reanalisados); agora contam no summary e voltam via retry_failed.
"""

import json
import os
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
from src.models.commit import CommitPair

MASTER_CSV = (
    "hash,purity_analysis,llm_analysis\n"
    "c1,FALSE,\n"
    "c2,TRUE,\n"
    "c3,FALSE,FAILED\n"
)


def _read_jsonl_records(analyzer) -> list[dict]:
    sessions_dir = os.path.join(analyzer.backup_dir, "sessions")
    records = []
    if os.path.isdir(sessions_dir):
        for name in sorted(os.listdir(sessions_dir)):
            with open(os.path.join(sessions_dir, name), encoding="utf-8") as f:
                records.extend(json.loads(line) for line in f if line.strip())
    return records


def _make_analyzer(tmp_path, monkeypatch, dry_run=False):
    csv_path = tmp_path / "master.csv"
    csv_path.write_text(MASTER_CSV, encoding="utf-8")

    analyzer = LLMPurityAnalyzer(csv_file_path=str(csv_path), dry_run=dry_run)
    # Isolar TODA a persistência da sessão em tmp_path
    analyzer.backup_dir = str(tmp_path / "backup")
    os.makedirs(analyzer.backup_dir, exist_ok=True)
    analyzer.session_log_file = None
    analyzer.supabase = None
    analyzer.command_handler = None

    # Stubs dos colaboradores (sem git, sem LLM, sem CSVs reais)
    monkeypatch.setattr(
        analyzer,
        "_get_commit_data_from_refactoring_csv",
        lambda h: CommitPair(
            repository="https://github.com/org/repo",
            commit_hash_before=f"before_{h}",
            commit_hash_current=h,
            project_name="proj",
        ),
    )
    monkeypatch.setattr(
        analyzer, "_get_diff_for_commit", lambda c: ("diff --git a b\n+x\n", "/fake")
    )
    analyzer.git_handler = MagicMock()
    analyzer.git_handler.get_commit_message.return_value = "commit msg"
    analyzer.llm_handler = MagicMock()
    # Identidade do modelo (REP-1): sessões reais exigem digest resolvível
    analyzer.llm_handler.get_model_info.return_value = {
        "model": "stub:latest",
        "digest": "sha256:stubdigest",
        "modified_at": "2026-01-01T00:00:00Z",
        "ollama_version": "0.0-test",
    }

    # O loop dorme 1s por commit — irrelevante para os testes
    monkeypatch.setattr("src.analyzers.llm_purity_analyzer.time.sleep", lambda s: None)

    return analyzer, csv_path


VERDICT_RESPONSE = {
    "success": True,
    "refactoring_type": "floss",
    "justification": "adds null check",
    "confidence_level": "high",
    "technical_evidence": "line 3",
    "extraction_method": "final_pattern+json",
    "llm_raw_response": "FINAL: FLOSS ...",
}


class TestVerdictPath:
    def test_verdict_written_counted_and_traced(self, tmp_path, monkeypatch):
        analyzer, csv_path = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.analyze_commit_refactoring.return_value = dict(VERDICT_RESPONSE)

        stats = analyzer.analyze_commits(max_commits=1)

        assert stats["successful_analyses"] == 1
        assert stats["failed_analyses"] == 0
        df = pd.read_csv(csv_path)
        assert df.loc[df["hash"] == "c1", "llm_analysis"].iloc[0] == "FLOSS"

        records = _read_jsonl_records(analyzer)
        assert len(records) == 1
        record = records[0]
        assert record["llm_classification"] == "FLOSS"
        assert record["extraction_method"] == "final_pattern+json"
        assert record["success"] is True
        assert record["prompt_sha256"] and record["tool_version"]


class TestFailurePath:
    def test_llm_failure_is_failed_not_fabricated_floss(self, tmp_path, monkeypatch):
        """Regressão VAL-2/VAL-6: o fallback antigo gravava 'floss'."""
        analyzer, csv_path = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.analyze_commit_refactoring.return_value = {
            "success": False,
            "error": "Falha na análise do LLM",
        }

        stats = analyzer.analyze_commits(max_commits=1)

        assert stats["failed_analyses"] == 1
        assert stats["successful_analyses"] == 0
        df = pd.read_csv(csv_path)
        cell = df.loc[df["hash"] == "c1", "llm_analysis"].iloc[0]
        assert cell == "FAILED"
        assert cell != "FLOSS"

        records = _read_jsonl_records(analyzer)
        assert len(records) == 1
        record = records[0]
        assert record["llm_classification"] == "FAILED"
        assert record["success"] is False
        assert record["error_type"] == "llm_no_verdict"
        assert record["llm_confidence"] is None  # nada de 'low' fabricado


class TestDryRun:
    def test_dry_run_never_mutates_master_csv(self, tmp_path, monkeypatch):
        analyzer, csv_path = _make_analyzer(tmp_path, monkeypatch, dry_run=True)
        before = csv_path.read_text(encoding="utf-8")

        stats = analyzer.analyze_commits(max_commits=2)

        assert csv_path.read_text(encoding="utf-8") == before
        assert "DRY_RUN" not in csv_path.read_text(encoding="utf-8")
        # O registro simulado existe no JSONL (rastro da sessão)
        records = _read_jsonl_records(analyzer)
        assert len(records) == 2
        assert all(r["llm_classification"] == "DRY_RUN" for r in records)
        # e o LLM nunca foi chamado
        analyzer.llm_handler.analyze_commit_refactoring.assert_not_called()


class TestRetryFailed:
    def test_failed_rows_are_skipped_by_default(self, tmp_path, monkeypatch):
        analyzer, _ = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.analyze_commit_refactoring.return_value = dict(VERDICT_RESPONSE)

        stats = analyzer.analyze_commits()  # sem retry_failed

        # c3 (FAILED) fica fora; só c1 e c2 processam
        assert stats["total_processed"] == 2

    def test_retry_failed_reincludes_failed_rows(self, tmp_path, monkeypatch):
        analyzer, csv_path = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.analyze_commit_refactoring.return_value = dict(VERDICT_RESPONSE)

        stats = analyzer.analyze_commits(retry_failed=True)

        assert stats["total_processed"] == 3
        df = pd.read_csv(csv_path)
        assert df.loc[df["hash"] == "c3", "llm_analysis"].iloc[0] == "FLOSS"


class TestSummary:
    def test_summary_counts_failed(self, tmp_path, monkeypatch):
        analyzer, _ = _make_analyzer(tmp_path, monkeypatch)
        summary = analyzer.get_analysis_summary()
        assert summary["failed_analyses"] == 1  # c3
        assert summary["pending_analyses"] == 2  # c1, c2


class TestModelDigest:
    """Fase E3 (REP-1): sessão real sem digest resolvível é abortada; com
    digest, a identidade acompanha cada registro."""

    def test_session_aborts_without_digest(self, tmp_path, monkeypatch):
        analyzer, _ = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.get_model_info.return_value = None
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="digest"):
            analyzer.analyze_commits(max_commits=1)

    def test_digest_recorded_on_every_record(self, tmp_path, monkeypatch):
        analyzer, _ = _make_analyzer(tmp_path, monkeypatch)
        analyzer.llm_handler.analyze_commit_refactoring.return_value = dict(VERDICT_RESPONSE)
        analyzer.analyze_commits(max_commits=1)
        records = _read_jsonl_records(analyzer)
        assert records[0]["model_digest"] == "sha256:stubdigest"
        assert records[0]["ollama_version"] == "0.0-test"

    def test_dry_run_exempt_from_digest(self, tmp_path, monkeypatch):
        analyzer, _ = _make_analyzer(tmp_path, monkeypatch, dry_run=True)
        analyzer.llm_handler.get_model_info.return_value = None
        stats = analyzer.analyze_commits(max_commits=1)  # não levanta
        assert stats["total_processed"] == 1
