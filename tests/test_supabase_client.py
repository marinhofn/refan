"""Testes unitários para SupabaseClient (src/persistence/supabase_client.py).

Primeira cobertura da camada de persistência cloud da Fase 11 (Fase H4
do HARDENING_PLAN.md). A API supabase-py é integralmente mockada via
create_client — nenhuma chamada de rede; valida contratos: cache de
UUIDs, falha silenciosa documentada (None/False/[]), normalização de
classificação e cálculo de SHA256 do prompt.
"""

import hashlib
import json
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

supabase_module = pytest.importorskip(
    "supabase", reason="extra [supabase] não instalado"
)

from src.persistence.supabase_client import (
    PromptVersionConflictError,
    SupabaseClient,
)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """Zera o backoff do retry para os testes não dormirem de verdade."""
    from src.core.settings import settings
    monkeypatch.setattr(settings, "supabase_backoff_base_s", 0.0)


def make_client(execute_data=None, select_data=None):
    """SupabaseClient com API mockada.

    Retorna (cliente, mock_api). O resultado de upsert/insert .execute() é um
    objeto com .data igual a execute_data (default: um registro com id); o
    resultado de select().eq().execute() usa select_data (default: vazio —
    registro inexistente).
    """
    if execute_data is None:
        execute_data = [{"id": "uuid-1"}]
    mock_api = mock.MagicMock()
    mock_api.table.return_value.upsert.return_value.execute.return_value = (
        SimpleNamespace(data=execute_data)
    )
    mock_api.table.return_value.insert.return_value.execute.return_value = (
        SimpleNamespace(data=execute_data)
    )
    mock_api.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=select_data or [])
    )
    with mock.patch(
        "src.persistence.supabase_client.create_client", return_value=mock_api
    ):
        client = SupabaseClient("https://x.supabase.co", "service-key")
    return client, mock_api


class TestInit:
    def test_rejects_missing_credentials(self):
        with mock.patch("src.persistence.supabase_client.create_client"):
            with pytest.raises(ValueError):
                SupabaseClient("", "key")
            with pytest.raises(ValueError):
                SupabaseClient("https://x.supabase.co", "")


class TestUpsertCommit:
    def test_none_purity_is_omitted_from_payload(self):
        """Fase E2 (VAL-5): 'purity_analysis': None no payload sobrescrevia
        para NULL o baseline de commits já registrados a cada sync."""
        client, api = make_client()

        client.upsert_commit("hash-a", "hash-b", "https://r", "proj")

        payload = api.table.return_value.upsert.call_args.args[0]
        assert "purity_analysis" not in payload

    def test_provided_purity_is_sent(self):
        client, api = make_client()

        client.upsert_commit(
            "hash-a", "hash-b", "https://r", "proj", purity_analysis="FALSE"
        )

        payload = api.table.return_value.upsert.call_args.args[0]
        assert payload["purity_analysis"] == "FALSE"

    def test_returns_uuid_and_caches(self):
        client, api = make_client()

        uid1 = client.upsert_commit("hash-a", "hash-b", "https://r", "proj")
        uid2 = client.upsert_commit("hash-a", "hash-b", "https://r", "proj")

        assert uid1 == uid2 == "uuid-1"
        # Segunda chamada servida pelo cache — uma única ida à API.
        assert api.table.return_value.upsert.call_count == 1

    def test_api_failure_returns_none_without_raising(self):
        client, api = make_client()
        api.table.return_value.upsert.return_value.execute.side_effect = (
            ConnectionError("rede caiu")
        )
        assert client.upsert_commit("hash-a", "hash-b", "url", "proj") is None

    def test_uses_conflict_on_commit_hash(self):
        client, api = make_client()
        client.upsert_commit("hash-a", "hash-b", "url", "proj")
        kwargs = api.table.return_value.upsert.call_args.kwargs
        assert kwargs["on_conflict"] == "commit_hash_current"


class TestGetOrCreateModel:
    def test_safe_name_replaces_colon(self):
        client, api = make_client()
        client.get_or_create_model("deepseek-r1:8b")
        payload = api.table.return_value.upsert.call_args.args[0]
        assert payload["safe_name"] == "deepseek-r1_8b"

    def test_caches_by_name(self):
        client, api = make_client()
        client.get_or_create_model("mistral")
        client.get_or_create_model("mistral")
        assert api.table.return_value.upsert.call_count == 1


class TestGetPromptVersion:
    def test_returns_id_and_hash_when_found(self):
        client, api = make_client()
        api.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            SimpleNamespace(data=[{"id": "p-uuid", "sha256_hash": "abc"}])
        )
        assert client.get_prompt_version("v2.0-mestrado") == {
            "id": "p-uuid", "sha256_hash": "abc",
        }

    def test_returns_none_when_absent_or_failing(self):
        client, api = make_client()
        api.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            SimpleNamespace(data=[])
        )
        assert client.get_prompt_version("inexistente") is None

        api.table.return_value.select.side_effect = ConnectionError("rede caiu")
        assert client.get_prompt_version("v2.0-mestrado") is None


class TestGetOrCreatePromptVersion:
    """Fase E2 (VAL-4): versões de prompt são imutáveis — get-then-insert.

    O upsert anterior sobrescrevia system_prompt/sha256_hash de uma tag já
    registrada, corrompendo a proveniência de todos os resultados que a
    referenciavam.
    """

    def test_new_tag_inserts_with_sha256(self):
        client, api = make_client()  # select vazio: tag inexistente
        prompt = "You are a software engineering expert."

        uid = client.get_or_create_prompt_version("v-test", prompt)

        assert uid == "uuid-1"
        payload = api.table.return_value.insert.call_args.args[0]
        assert payload["sha256_hash"] == hashlib.sha256(prompt.encode()).hexdigest()
        assert payload["version_tag"] == "v-test"
        api.table.return_value.upsert.assert_not_called()

    def test_existing_tag_same_hash_returns_registered_id(self):
        prompt = "Same prompt."
        sha = hashlib.sha256(prompt.encode()).hexdigest()
        client, api = make_client(
            select_data=[{"id": "uuid-registrado", "sha256_hash": sha}]
        )

        uid = client.get_or_create_prompt_version("v-test", prompt)

        assert uid == "uuid-registrado"
        api.table.return_value.insert.assert_not_called()
        api.table.return_value.upsert.assert_not_called()

    def test_existing_tag_different_hash_raises_and_never_writes(self):
        client, api = make_client(
            select_data=[{"id": "uuid-registrado", "sha256_hash": "outrohash"}]
        )

        with pytest.raises(PromptVersionConflictError, match="imutáveis"):
            client.get_or_create_prompt_version("v-test", "Edited prompt.")

        api.table.return_value.insert.assert_not_called()
        api.table.return_value.upsert.assert_not_called()


class TestRecordResult:
    def test_classification_is_uppercased(self):
        client, api = make_client()
        ok = client.record_result(
            session_id="s", commit_id="c", model_id="m",
            prompt_version_id="p", classification="pure",
        )
        assert ok is True
        payload = api.table.return_value.upsert.call_args.args[0]
        assert payload["classification"] == "PURE"

    def test_uses_session_commit_conflict_key(self):
        client, api = make_client()
        client.record_result(
            session_id="s", commit_id="c", model_id="m",
            prompt_version_id="p", classification="floss",
        )
        kwargs = api.table.return_value.upsert.call_args.kwargs
        assert kwargs["on_conflict"] == "session_id,commit_id"

    def test_api_failure_returns_false(self):
        client, api = make_client()
        api.table.return_value.upsert.return_value.execute.side_effect = (
            TimeoutError("lento")
        )
        ok = client.record_result(
            session_id="s", commit_id="c", model_id="m",
            prompt_version_id="p", classification="pure",
        )
        assert ok is False


class TestSessionLifecycle:
    def test_start_session_returns_uuid(self):
        client, _ = make_client(execute_data=[{"id": "session-uuid"}])
        sid = client.start_session("m", "p", config_snapshot={"temperature": 0.1})
        assert sid == "session-uuid"

    def test_update_status_failure_returns_false(self):
        client, api = make_client()
        api.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
            ConnectionError("rede caiu")
        )
        assert client.update_session_status("s", "completed") is False


class TestPollCommands:
    def test_api_failure_returns_empty_list(self):
        client, api = make_client()
        api.table.return_value.select.side_effect = ConnectionError("rede caiu")
        assert client.poll_commands("runner-1") == []


class TestRetryAndTimeout:
    """Resiliência de rede (HARDENING_PLAN.md, Fase H6)."""

    def test_client_created_with_explicit_timeout(self):
        with mock.patch(
            "src.persistence.supabase_client.create_client"
        ) as create, mock.patch(
            "src.persistence.supabase_client.ClientOptions"
        ) as options:
            SupabaseClient("https://x.supabase.co", "service-key")
        options.assert_called_once()
        assert "postgrest_client_timeout" in options.call_args.kwargs
        assert create.call_args.kwargs["options"] is options.return_value

    def test_transient_failure_is_retried_until_success(self):
        client, api = make_client()
        ok = SimpleNamespace(data=[{"id": "uuid-1"}])
        api.table.return_value.upsert.return_value.execute.side_effect = [
            ConnectionError("queda 1"),
            ConnectionError("queda 2"),
            ok,
        ]

        uid = client.upsert_commit("hash-a", "hash-b", "url", "proj")

        assert uid == "uuid-1"
        assert api.table.return_value.upsert.return_value.execute.call_count == 3

    def test_persistent_failure_gives_up_after_max_retries(self):
        client, api = make_client()
        api.table.return_value.upsert.return_value.execute.side_effect = (
            ConnectionError("rede caiu")
        )

        uid = client.upsert_commit("hash-a", "hash-b", "url", "proj")

        assert uid is None
        from src.core.settings import settings
        assert (
            api.table.return_value.upsert.return_value.execute.call_count
            == settings.supabase_max_retries
        )

    def test_backoff_grows_exponentially(self):
        client, api = make_client()
        api.table.return_value.upsert.return_value.execute.side_effect = (
            ConnectionError("rede caiu")
        )
        from src.core.settings import settings
        with mock.patch.object(settings, "supabase_backoff_base_s", 1.0), \
             mock.patch("src.persistence.supabase_client.time.sleep") as sleep:
            client.upsert_commit("hash-a", "hash-b", "url", "proj")

        # 3 tentativas -> 2 esperas: base*2^0 e base*2^1
        assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0]

    def test_heartbeat_uses_single_attempt(self):
        client, api = make_client()
        api.table.return_value.upsert.return_value.execute.side_effect = (
            ConnectionError("rede caiu")
        )

        ok = client.update_heartbeat(runner_id="r1")

        assert ok is False
        # Operação periódica: sem retry — a próxima iteração repete.
        assert api.table.return_value.upsert.return_value.execute.call_count == 1


class TestSyncLocalJsonl:
    def test_syncs_valid_lines_and_skips_corrupted(self, tmp_path):
        client, _ = make_client()
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text(
            json.dumps({"hash": "aaa", "llm_classification": "PURE"}) + "\n"
            + "linha corrompida\n"
            + json.dumps({"sem_hash": True}) + "\n",
            encoding="utf-8",
        )

        with mock.patch.object(client, "upsert_commit", return_value="c-uuid") as up, \
             mock.patch.object(client, "record_result", return_value=True) as rec:
            synced = client.sync_local_jsonl(str(jsonl), "s", "m", "p")

        assert synced == 1                  # só a linha válida com hash
        up.assert_called_once()
        assert rec.call_args.kwargs["classification"] == "PURE"

    def test_missing_file_returns_zero(self, tmp_path):
        client, _ = make_client()
        assert client.sync_local_jsonl(str(tmp_path / "x.jsonl"), "s", "m", "p") == 0
