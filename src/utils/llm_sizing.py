"""Planejamento de janela de contexto e orçamento de geração.

Reescrito na Fase E2 (EVOLUTION_PLAN.md, VAL-7). O desenho anterior tinha três
defeitos que produziam truncamento SILENCIOSO de entrada pelo Ollama:

1. o ``num_ctx`` era dimensionado só pelo tamanho do DIFF, ignorando template
   (~1,6k tokens) e contexto do commit;
2. ``num_predict=50000`` disputava a janela com o input;
3. um diff podia ter até 60.000 chars (~15k tokens) com janela máxima de 8192
   — o Ollama descartava o excedente sem qualquer registro, e o modelo
   classificava sem ver o diff inteiro.

O contrato novo: ``plan_generation`` mede o PROMPT REAL, aplica margem sobre a
estimativa de tokens, reserva o orçamento de saída e devolve um plano com o
``num_ctx`` efetivo e, quando o prompt não cabe no teto do modelo, o orçamento
de chars ao qual o chamador deve reduzir o diff ANTES do envio — registrando o
corte (``diff_truncated``) no resultado. Nada é truncado silenciosamente.

Tetos e margens vivem em RefanSettings (context_ceiling*,
max_output_tokens, token_estimate_margin) com justificativa documentada.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.settings import settings as _settings


def estimate_token_count(text: str) -> int:
    """Estima contagem de tokens via heurística simples (chars / 4).

    Não é precisa (código/diff tende a mais tokens por char do que prosa);
    por isso o planejamento aplica ``settings.token_estimate_margin`` sobre
    esta estimativa.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _round_up(value: int, step: int = 512) -> int:
    return ((value + step - 1) // step) * step


@dataclass(frozen=True)
class GenerationPlan:
    """Plano de geração para um prompt concreto em um modelo concreto.

    Attributes:
        num_ctx: janela de contexto a enviar em options.num_ctx.
        num_predict: orçamento de tokens de saída (options.num_predict).
        prompt_tokens_estimated: estimativa de tokens do prompt medido.
        required_ctx: tokens necessários (estimativa com margem + saída).
        fits: True se required_ctx cabe no teto do modelo. Quando False, o
            chamador DEVE reduzir o input para até ``max_prompt_chars`` e
            replanejar — enviar assim mesmo causaria truncamento silencioso.
        max_prompt_chars: orçamento de chars de prompt que cabe no teto.
    """

    num_ctx: int
    num_predict: int
    prompt_tokens_estimated: int
    required_ctx: int
    fits: bool
    max_prompt_chars: int


def context_ceiling_for(model_name: str = "") -> int:
    """Teto de contexto do modelo (DeepSeek tem teto empírico próprio)."""
    if model_name and _settings.is_deepseek(model_name):
        return _settings.context_ceiling_deepseek
    return _settings.context_ceiling


def plan_generation(prompt_text: str, model_name: str = "") -> GenerationPlan:
    """Planeja num_ctx/num_predict para o PROMPT REAL (template+contexto+diff).

    Regras:
    - required = tokens_estimados * margem + max_output_tokens;
    - num_ctx = min(teto do modelo, max(context_small, required arredondado
      a 512)) — nunca abaixo do mínimo operacional, nunca acima do teto;
    - fits=False sinaliza que o prompt excede o teto: o chamador reduz o
      diff para caber em max_prompt_chars e replaneja.
    """
    tokens = estimate_token_count(prompt_text)
    margin = _settings.token_estimate_margin
    output_budget = _settings.max_output_tokens
    ceiling = context_ceiling_for(model_name)

    required = int(tokens * margin) + output_budget
    num_ctx = min(ceiling, max(_settings.context_small, _round_up(required)))
    fits = required <= ceiling

    max_prompt_tokens = max(0, int((ceiling - output_budget) / margin))
    max_prompt_chars = max_prompt_tokens * 4

    return GenerationPlan(
        num_ctx=num_ctx,
        num_predict=output_budget,
        prompt_tokens_estimated=tokens,
        required_ctx=required,
        fits=fits,
        max_prompt_chars=max_prompt_chars,
    )
