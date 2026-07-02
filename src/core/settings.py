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
    # Reset preventivo do contexto DeepSeek a cada N análises: degradação
    # progressiva de performance foi observada empiricamente no DeepSeek-R1
    # após ~8 análises consecutivas (TCC, ago/2025); o reset via keep_alive=0
    # descarrega o modelo e restaura o tempo de resposta.
    deepseek_reset_interval: int = 8

    # --- Diff handling ---
    max_diff_chars: int = 60000
    max_diff_chars_file: int = 100000
    per_file_line_limit: int = 400

    # --- Context window ---
    context_small: int = 4096
    context_medium: int = 6144
    context_large: int = 8192
    # Dimensionamento honesto de contexto (Fase E2, VAL-7): o prompt REAL
    # (template + contexto + diff) é medido e o num_ctx é planejado para
    # comportá-lo com margem; se não couber no teto, o diff é reduzido ANTES
    # do envio e o corte é registrado (diff_truncated) — nunca truncamento
    # silencioso pelo Ollama.
    # Teto padrão de contexto por VRAM disponível (16 GB no runner de refª).
    context_ceiling: int = 8192
    # Teto empírico DeepSeek-R1: janelas maiores degradam latência (TCC,
    # ago/2025); mantido como limite superior, não mais como override cego.
    context_ceiling_deepseek: int = 4096
    # Orçamento de SAÍDA: análise breve + linha FINAL + JSON de 8 campos
    # cabem folgadamente em 2048 tokens. O valor herdado num_predict=50000
    # disputava a janela com o input e mascarava o truncamento.
    max_output_tokens: int = 2048
    # chars/4 subestima tokens de código/diff; margem de segurança aplicada
    # sobre a estimativa ao planejar o contexto.
    token_estimate_margin: float = 1.25

    # --- GPU ---
    # Camadas offloaded para a GPU (env REFAN_NUM_GPU_LAYERS). Movido de
    # config.py para o settings na Fase E3 (REP-3): fora do dataclass o valor
    # ficava FORA do config_snapshot — condição de execução não registrada.
    num_gpu_layers: int | None = field(
        default_factory=lambda: (
            int(os.environ["REFAN_NUM_GPU_LAYERS"])
            if os.environ.get("REFAN_NUM_GPU_LAYERS", "").isdigit()
            else None
        )
    )

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

    # --- Runner remoto (Fase E4, ROB-5) ---
    # Pausa máxima via comando remoto: um 'pause' sem 'resume' não pode
    # congelar o runner para sempre; após o timeout há auto-resume logado.
    max_pause_s: int = 3600

    # --- Cache de repositórios clonados (Fase E4, ROB-4) ---
    # Orçamento de disco para repositorios/ — clones são cache reconstruível;
    # acima do orçamento, `refan clean-repos` remove os menos usados (LRU).
    repo_cache_max_gb: float = 20.0

    # --- Persistência ---
    # fsync após cada linha JSONL (Fase E4, ROB-3): garante que o registro
    # sobreviva a queda de energia, não só a crash de processo. O custo
    # (~ms) é irrisório perto de uma inferência LLM (segundos/minutos).
    jsonl_fsync: bool = True

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
    # Resiliência de rede (HARDENING_PLAN.md, Fase H6): timeout explícito do
    # client PostgREST e retry com backoff exponencial para operações que
    # persistem dados de pesquisa (resultados, sessões, commits). Operações
    # periódicas (heartbeat, polling) usam tentativa única — a próxima
    # iteração do loop já as repete naturalmente.
    supabase_timeout_s: int = 10
    supabase_max_retries: int = 3
    supabase_backoff_base_s: float = 1.0

    def is_deepseek(self, model_name: str | None = None) -> bool:
        """Verifica se o modelo atual ou informado é DeepSeek."""
        name = model_name or self.llm_model
        return "deepseek" in name.lower()

    def get_keep_alive(self, model_name: str | None = None) -> str:
        """Retorna keep_alive apropriado para o modelo."""
        if self.is_deepseek(model_name):
            return self.keep_alive_deepseek
        return self.keep_alive

    # Limiar (em chars de prompt) acima do qual o timeout largo é usado.
    timeout_prompt_threshold: int = 50000

    def get_timeout(self, prompt_size: int = 0) -> int:
        """Retorna timeout em segundos baseado no tamanho do prompt."""
        if prompt_size > self.timeout_prompt_threshold:
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
