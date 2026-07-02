"""Utilitários para dimensionamento de context window e redução de diffs.

Consolida estimate_token_count() e dynamic_num_ctx() de:
- llm_handler.py:49-66 (versão simples, sem model_name)
- optimized_llm_handler.py:146-210 (versão com DeepSeek branching)

A versão unificada usa a lógica do optimized_llm_handler (superset)
com o parâmetro model_name opcional.

Refs: REFACTORING_PLAN.md Phase 1.4
"""

from src.core.settings import settings as _settings


def estimate_token_count(text: str) -> int:
    """Estima contagem de tokens via heurística simples (chars / 4).

    Idêntica em ambos os handlers. Não é precisa, mas suficiente para
    decidir o tamanho do context window.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def dynamic_num_ctx(diff_text: str, model_name: str = "") -> int:
    """Calcula o tamanho do context window baseado no tamanho do diff.

    Usa a lógica do optimized_llm_handler.py (superset):
    - DeepSeek: valores menores (capped em 4096)
    - Outros modelos: escala até 8192

    A versão do llm_handler.py original usava valores menores
    (2048/4096/6144) sem branching por modelo.

    Args:
        diff_text: Conteúdo do diff para estimar tokens.
        model_name: Nome do modelo (usado para branching DeepSeek).
    """
    tokens = estimate_token_count(diff_text)
    # Fonte única de verdade para detecção DeepSeek (settings.is_deepseek).
    # model_name vazio mantém a semântica original (sem fallback ao modelo
    # global): este utilitário dimensiona para o modelo explicitamente pedido.
    is_deepseek = _settings.is_deepseek(model_name) if model_name else False

    if is_deepseek:
        if tokens < 2000:
            return 3072
        elif tokens < 4000:
            return 4096
        else:
            return 4096  # DeepSeek capped
    else:
        if tokens < 3000:
            return 4096
        if tokens < 6000:
            return 6144
        if tokens < 9000:
            return 8192
        return 8192


def reduce_diff_simple(diff_text: str, max_chars: int = 50000) -> tuple:
    """Redução simples por truncamento (llm_handler.py original).

    Returns:
        tuple(diff_text, metadata_dict)
    """
    if len(diff_text) <= max_chars:
        return diff_text, {"reduced": False}
    truncated = diff_text[:max_chars]
    return truncated + "\n... (truncado)", {
        "reduced": True,
        "original_chars": len(diff_text),
        "new_chars": len(truncated),
    }
