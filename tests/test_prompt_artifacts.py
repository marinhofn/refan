"""Sincronização entre constantes de prompt e seus artefatos verbatim.

Contexto (HARDENING_PLAN.md Fase H9; EVOLUTION_PLAN.md achado REP-5): os prompts
são artefatos experimentais — o texto citável vive em ``configs/prompts/<tag>.txt``
e o SHA-256 de cada versão é registrado em ``docs/PROMPTS.md`` e na tabela
``prompt_versions`` do Supabase. Estes testes garantem que a constante executada
pelo código nunca diverge silenciosamente do artefato registrado: qualquer edição
em um dos lados quebra a suíte e força a criação de uma nova versão de prompt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.analyzers.optimized_prompt import OPTIMIZED_LLM_PROMPT
from src.core.config import LLM_PROMPT

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "prompts"

# Hashes publicados em docs/PROMPTS.md — a tríade constante/arquivo/hash deve
# permanecer idêntica. Mudou o prompt? Nova tag, novo arquivo, novo registro.
REGISTERED_SHA256 = {
    "v1.0-tcc": "5cf305d1e4f0bbf91908a37a68538efcb53022c9e396eb493bafe690f2b6f468",
    "v2.0-mestrado": "2c24d204ecf09e53e2b3ebff745aed5b5e1442436cdd84727323721a89e32ccd",
}

CONSTANTS = {
    "v1.0-tcc": LLM_PROMPT,
    "v2.0-mestrado": OPTIMIZED_LLM_PROMPT,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestPromptArtifacts:
    def test_artifact_files_exist(self):
        for tag in REGISTERED_SHA256:
            assert (PROMPTS_DIR / f"{tag}.txt").is_file(), (
                f"artefato verbatim ausente para a versão de prompt '{tag}'"
            )

    def test_constant_matches_artifact_verbatim(self):
        for tag, constant in CONSTANTS.items():
            artifact = (PROMPTS_DIR / f"{tag}.txt").read_text(encoding="utf-8")
            assert artifact == constant, (
                f"configs/prompts/{tag}.txt divergiu da constante no código — "
                "prompts publicados são imutáveis; crie uma nova versão"
            )

    def test_constant_matches_registered_hash(self):
        for tag, constant in CONSTANTS.items():
            assert _sha256(constant.encode()) == REGISTERED_SHA256[tag], (
                f"SHA-256 da constante '{tag}' difere do registrado em docs/PROMPTS.md"
            )

    def test_artifact_matches_registered_hash(self):
        for tag, expected in REGISTERED_SHA256.items():
            actual = _sha256((PROMPTS_DIR / f"{tag}.txt").read_bytes())
            assert actual == expected, (
                f"SHA-256 do arquivo configs/prompts/{tag}.txt difere do registrado"
            )

    def test_session_hash_uses_v2_prompt(self):
        """O prompt_sha256 gravado nas sessões (H5) corresponde à tag v2.0-mestrado."""
        session_hash = hashlib.sha256(OPTIMIZED_LLM_PROMPT.encode()).hexdigest()
        assert session_hash == REGISTERED_SHA256["v2.0-mestrado"]
