"""Configuração centralizada do Refan via dataclass tipada.

Substitui os 21+ magic values espalhados como literais em llm_handler.py,
optimized_llm_handler.py, e config.py por um único objeto de configuração
documentado e versionável.

Conflitos resolvidos entre handlers:
- temperature: 0.1 (ambos concordavam)
- keep_alive: "10m" vs "5m" → "5m" (otimizado)
- keep_alive_deepseek: inexistente vs "30s" → "30s"
- num_predict: 20000 vs 50000 → 50000 (otimizado, evita truncamento)
- timeout_base: 120s vs 200s → 200s (otimizado)
- timeout_large: inexistente vs 300s → 300s
- max_retries: 3 vs 1 → 2 (compromisso)
- diff_threshold: 50000 vs 60000 → 60000 (otimizado)

Refs: REFACTORING_PLAN.md Phase 2
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RefanSettings:
    """Configuração centralizada para o sistema Refan.

    Todos os valores que antes estavam hardcoded nos handlers são agora
    atributos tipados com defaults documentados. Alterações são feitas
    via instanciação com parâmetros ou mutação direta do singleton.
    """

    # --- Conexão LLM ---
    ollama_host: str = "http://localhost:11434/api/generate"
    llm_model: str = field(
        default_factory=lambda: os.environ.get("REFAN_LLM_MODEL", "mistral")
    )

    # --- Parâmetros de geração ---
    temperature: float = 0.1
    num_predict: int = 50000
    keep_alive: str = "5m"
    keep_alive_deepseek: str = "30s"

    # --- Retry e timeout ---
    max_retries: int = 2
    timeout_base_s: int = 200
    timeout_large_s: int = 300

    # --- Diff handling ---
    max_diff_chars: int = 60000
    max_diff_chars_file: int = 100000
    per_file_line_limit: int = 400

    # --- Context window ---
    context_small: int = 4096
    context_medium: int = 6144
    context_large: int = 8192

    # --- Debug ---
    show_prompt: bool = True
    max_prompt_display_length: int = 2000
    reset_model_context: bool = True

    # --- Reprodutibilidade ---
    # Seed fixo passado em options.seed da API do Ollama. Com temperature
    # baixa + seed fixo, a geração torna-se determinística por modelo/versão.
    # use_random_seed=True replica o regime do baseline TCC (sem seed);
    # o default False define o regime da série experimental do mestrado
    # (v2.1+). Decisão registrada em HARDENING_PLAN.md e docs/REPRODUCIBILITY.md.
    llm_seed: int = 42
    use_random_seed: bool = False

    # --- Failure tracking ---
    failures_file: str = "json_failures.json"

    # --- Supabase (cloud persistence) ---
    supabase_url: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_URL", "")
    )
    supabase_service_key: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", "")
    )
    runner_id: str = field(
        default_factory=lambda: os.environ.get("REFAN_RUNNER_ID", socket.gethostname())
    )
    prompt_version_tag: str = field(
        default_factory=lambda: os.environ.get("REFAN_PROMPT_VERSION", "v2.0-mestrado")
    )

    def is_deepseek(self, model_name: str | None = None) -> bool:
        """Verifica se o modelo atual ou informado é DeepSeek."""
        name = model_name or self.llm_model
        return "deepseek" in name.lower()

    def get_keep_alive(self, model_name: str | None = None) -> str:
        """Retorna keep_alive apropriado para o modelo."""
        if self.is_deepseek(model_name):
            return self.keep_alive_deepseek
        return self.keep_alive

    def get_timeout(self, prompt_size: int = 0) -> int:
        """Retorna timeout em segundos baseado no tamanho do prompt."""
        if prompt_size > 50000:
            return self.timeout_large_s
        return self.timeout_base_s

    @property
    def supabase_enabled(self) -> bool:
        """Verifica se Supabase está configurado (URL e key presentes)."""
        return bool(self.supabase_url and self.supabase_service_key)

    def to_dict(self) -> dict:
        """Serializa configuração para logging e reprodutibilidade.

        Exclui a service key do snapshot por segurança.
        """
        from dataclasses import asdict
        d = asdict(self)
        d.pop("supabase_service_key", None)
        return d


# Singleton global — importado por todos os módulos
settings = RefanSettings()
