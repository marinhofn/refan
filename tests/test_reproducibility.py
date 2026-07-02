"""Testes unitários da infraestrutura de reprodutibilidade (Fase H5).

Cobre src/utils/timeutils.py (timestamps UTC timezone-aware) e
src/utils/version_info.py (rastreamento da versão da ferramenta).
"""

import re
import subprocess
import sys
from datetime import timezone
from unittest import mock

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.utils import version_info
from src.utils.timeutils import utc_now, utc_now_iso, utc_now_stamp


class TestTimeutils:
    def test_utc_now_is_timezone_aware_utc(self):
        now = utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset().total_seconds() == 0

    def test_utc_now_iso_carries_utc_offset(self):
        iso = utc_now_iso()
        assert iso.endswith("+00:00")

    def test_utc_now_stamp_matches_filename_format(self):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", utc_now_stamp())

    def test_analysis_result_timestamp_is_utc(self):
        """O modelo canônico de resultado herda o timestamp UTC."""
        from src.models.commit import AnalysisResult

        result = AnalysisResult(
            repository="r", commit_hash_before="a", commit_hash_current="b",
            refactoring_type="pure", justification="j",
        )
        assert result.timestamp.endswith("+00:00")


class TestVersionInfo:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        version_info._cached_version = None
        yield
        version_info._cached_version = None

    def test_returns_git_describe_output(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="v2.1.0-hardening-4-3-gabc1234\n", stderr=""
        )
        with mock.patch.object(subprocess, "run", return_value=fake):
            assert version_info.get_tool_version() == "v2.1.0-hardening-4-3-gabc1234"

    def test_fallback_unknown_when_git_unavailable(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            assert version_info.get_tool_version() == "unknown"

    def test_fallback_unknown_on_nonzero_exit(self):
        fake = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="x")
        with mock.patch.object(subprocess, "run", return_value=fake):
            assert version_info.get_tool_version() == "unknown"

    def test_result_is_cached_per_process(self):
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="v1\n", stderr="")
        with mock.patch.object(subprocess, "run", return_value=fake) as run:
            version_info.get_tool_version()
            version_info.get_tool_version()
        assert run.call_count == 1

    def test_real_repository_resolves_version(self):
        """Neste repositório, a versão real deve ser resolvida (não unknown)."""
        assert version_info.get_tool_version() != "unknown"
