"""Testes unitários para o seed do Supabase (scripts/seed_supabase.py).

Cobre idempotência (delegada a upserts do client) e o tratamento de
falhas parciais introduzido na Fase H6: falha em um registro não aborta
o lote e é reportada ao final.
"""

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

pytest.importorskip("supabase", reason="extra [supabase] não instalado")

_SCRIPT = Path(__file__).parent.parent / "scripts" / "seed_supabase.py"
_spec = importlib.util.spec_from_file_location("seed_supabase", _SCRIPT)
seed_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_mod)


@pytest.fixture
def commits_csv(tmp_path):
    path = tmp_path / "commits.csv"
    path.write_text(
        "commit1,commit2,project,project_name\n"
        "aaa,bbb,https://r/a,proj-a\n"
        "ccc,ddd,https://r/b,proj-b\n"
        "eee,fff,https://r/c,proj-c\n",
        encoding="utf-8",
    )
    return str(path)


class TestSeedCommits:
    def test_all_success(self, commits_csv):
        client = mock.Mock()
        client.upsert_commit.return_value = "uuid"

        count, failed = seed_mod.seed_commits(client, csv_path=commits_csv)

        assert count == 3
        assert failed == []
        assert client.upsert_commit.call_count == 3

    def test_partial_failure_does_not_abort_batch(self, commits_csv):
        client = mock.Mock()
        # Segundo commit falha (rede); os demais seguem.
        client.upsert_commit.side_effect = ["uuid", None, "uuid"]

        count, failed = seed_mod.seed_commits(client, csv_path=commits_csv)

        assert count == 2
        assert failed == ["ddd"]
        assert client.upsert_commit.call_count == 3

    def test_rerun_is_idempotent_via_upsert(self, commits_csv):
        """Reexecução não duplica: a unicidade vem do upsert por hash."""
        client = mock.Mock()
        client.upsert_commit.return_value = "uuid"

        seed_mod.seed_commits(client, csv_path=commits_csv)
        count, failed = seed_mod.seed_commits(client, csv_path=commits_csv)

        assert count == 3
        assert failed == []
        # Cada execução faz os mesmos 3 upserts idempotentes.
        assert client.upsert_commit.call_count == 6

    def test_missing_csv_returns_zero(self, tmp_path):
        client = mock.Mock()
        count, failed = seed_mod.seed_commits(
            client, csv_path=str(tmp_path / "nada.csv")
        )
        assert (count, failed) == (0, [])
        client.upsert_commit.assert_not_called()


class TestSeedModelsAndPrompts:
    def test_seed_models_reports_failures(self):
        client = mock.Mock()
        client.get_or_create_model.side_effect = (
            lambda **kw: None if kw["name"] == "gemma2:2b" else "uuid"
        )

        count, failed = seed_mod.seed_models(client)

        assert failed == ["gemma2:2b"]
        assert count == client.get_or_create_model.call_count - 1

    def test_seed_prompt_versions_reports_failures(self):
        client = mock.Mock()
        client.get_or_create_prompt_version.return_value = None

        count, failed = seed_mod.seed_prompt_versions(client)

        assert count == 0
        assert failed == ["v1.0-tcc", "v2.0-mestrado"]
