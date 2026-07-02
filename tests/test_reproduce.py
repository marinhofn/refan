"""refan reproduce (Fase E3) — verificação de ambiente e comparação de runs."""

import json

import pytest

from src.analyzers.reproduce import (
    compare_classifications,
    load_session_records,
    verify_environment,
)


def _record(commit_hash, classification, prompt="p" * 64, tool="v2.2.0",
            digest="sha256:aaa"):
    return {
        "hash": commit_hash,
        "llm_classification": classification,
        "prompt_sha256": prompt,
        "tool_version": tool,
        "model_digest": digest,
    }


class TestVerifyEnvironment:
    def test_identical_environment_passes(self):
        records = [_record("c1", "PURE"), _record("c2", "FLOSS")]
        ok, messages = verify_environment(records, "p" * 64, "v2.2.0", "sha256:aaa")
        assert ok is True
        assert messages == []

    def test_prompt_divergence_blocks(self):
        records = [_record("c1", "PURE")]
        ok, messages = verify_environment(records, "OUTRO" + "x" * 59, "v2.2.0", "sha256:aaa")
        assert ok is False
        assert any("prompt" in m for m in messages)

    def test_tool_version_divergence_blocks(self):
        records = [_record("c1", "PURE")]
        ok, messages = verify_environment(records, "p" * 64, "v9.9.9", "sha256:aaa")
        assert ok is False
        assert any("tool_version" in m for m in messages)

    def test_digest_divergence_blocks(self):
        records = [_record("c1", "PURE")]
        ok, messages = verify_environment(records, "p" * 64, "v2.2.0", "sha256:bbb")
        assert ok is False
        assert any("digest" in m for m in messages)

    def test_pre_e3_session_without_digest_warns_but_proceeds(self):
        records = [_record("c1", "PURE", digest=None)]
        records[0].pop("model_digest")
        ok, messages = verify_environment(records, "p" * 64, "v2.2.0", "sha256:aaa")
        assert ok is True
        assert any("pré-E3" in m for m in messages)


class TestCompareClassifications:
    def test_full_agreement(self):
        original = [_record("c1", "PURE"), _record("c2", "FLOSS")]
        reproduced = [_record("c1", "PURE"), _record("c2", "FLOSS")]
        report = compare_classifications(original, reproduced)
        assert len(report["matches"]) == 2
        assert report["mismatches"] == []
        assert report["missing"] == []

    def test_mismatch_reported_with_both_labels(self):
        original = [_record("c1", "PURE")]
        reproduced = [_record("c1", "FLOSS")]
        report = compare_classifications(original, reproduced)
        assert report["mismatches"] == [("c1", "PURE", "FLOSS")]

    def test_missing_reproduction_reported(self):
        original = [_record("c1", "PURE"), _record("c2", "FLOSS")]
        reproduced = [_record("c1", "PURE")]
        report = compare_classifications(original, reproduced)
        assert report["missing"] == ["c2"]

    def test_non_verdict_originals_are_not_comparable(self):
        original = [_record("c1", "FAILED"), _record("c2", "PURE")]
        reproduced = [_record("c2", "PURE")]
        report = compare_classifications(original, reproduced)
        assert report["total_comparable"] == 1
        assert len(report["matches"]) == 1


class TestLoadSessionRecords:
    def test_reads_jsonl_skipping_broken_lines(self, tmp_path, capsys):
        path = tmp_path / "s.jsonl"
        path.write_text(
            json.dumps({"hash": "c1"}) + "\n{broken\n" + json.dumps({"hash": "c2"}) + "\n",
            encoding="utf-8",
        )
        records = load_session_records(path)
        assert [r["hash"] for r in records] == ["c1", "c2"]
        assert "inválida" in capsys.readouterr().out
