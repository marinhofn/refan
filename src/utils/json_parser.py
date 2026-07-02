"""Utilitários para extração de JSON (objetos) a partir de texto livre de LLMs.

Fonte única de parsing do projeto (REFACTORING_PLAN.md Fase 1). Endurecida na
Fase E2 (EVOLUTION_PLAN.md, VAL-8) sob o princípio PRECISÃO > RECALL: em um
instrumento de pesquisa, deixar de extrair é uma falha visível e tratável;
extrair um objeto fabricado é contaminação silenciosa de dados. Por isso:

- ``extract_json_from_text`` retorna SOMENTE objetos (dict) — nunca listas nem
  dicionários montados heuristicamente a partir de texto solto;
- o antigo fallback ``key: value`` (estratégia 3) foi removido: ele fabricava
  dicts arbitrários de qualquer prosa, que viravam classificação FLOSS via
  defaults a jusante;
- ``json5`` é dependência obrigatória: com ela opcional, o mesmo texto podia
  parsear em uma máquina e falhar em outra (irreprodutibilidade silenciosa);
- a remoção de blocos <think> é estritamente delimitada por tags; as
  heurísticas destrutivas de "linhas repetitivas" foram removidas por poderem
  corromper JSON válido antes do parse;
- ``extract_classification_json`` aplica o schema mínimo do domínio
  (refactoring_type ∈ {pure, floss}) — ausência/invalidade é falha de parse,
  nunca vira default.
"""
from typing import Optional
import json
import re

# Obrigatório desde a Fase E2 (VAL-8): parsing tolerante determinístico entre
# ambientes. Pinado em pyproject.toml/requirements.txt.
import json5 as _json5

from src.utils.classification import VALID_CLASSIFICATIONS


def _find_json_end_index(text: str, start_idx: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if ch == '"' and not escape:
            in_string = not in_string
        if in_string:
            if ch == '\\' and not escape:
                escape = True
            else:
                escape = False
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _find_matching_closing(text: str, start_idx: int, open_ch: str, close_ch: str) -> int:
    """Generalized matcher para chaves/colchetes, respeitando strings e escapes."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if ch == '"' and not escape:
            in_string = not in_string
        if in_string:
            if ch == '\\' and not escape:
                escape = True
            else:
                escape = False
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def try_parse_json(text: str) -> Optional[dict]:
    """Tenta parsear JSON estrito e json5 como fallback."""
    try:
        return json.loads(text)
    except Exception:
        try:
            return _json5.loads(text)
        except Exception:
            return None


def extract_json_candidates(text: str) -> list[str]:
    """Extrai substrings candidatas que parecem JSON via regex."""
    patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',
        r'```\s*(\{[\s\S]*?\})\s*```',
        r'(\{[\s\S]*?\})'
    ]
    candidates = []
    for pat in patterns:
        for m in re.findall(pat, text, re.MULTILINE | re.DOTALL):
            candidates.append(m)
    return candidates


def extract_json_from_text(text: str) -> Optional[dict]:
    """Extrai o primeiro OBJETO JSON parseável do texto, ou None.

    Estratégias, em ordem de precisão:
    0) texto inteiro é o objeto;
    1) candidatos por regex (blocos ```json/```/inline);
    2) varredura balanceada de '{' com reparos mínimos (vírgula pendente,
       comentários //).

    Retorna exclusivamente dict — arrays e valores escalares não são objetos
    de classificação e são ignorados (VAL-8).
    """
    # Pré-processamento: remover blocos de 'thinking' delimitados por tags
    text = _strip_think_blocks(text)

    # 0) tentar parsear o texto inteiro (alguns modelos retornam apenas JSON)
    whole = text.strip()
    if whole:
        parsed_whole = try_parse_json(whole)
        if isinstance(parsed_whole, dict):
            return parsed_whole

    # 1) candidatos por regex
    for cand in extract_json_candidates(text):
        parsed = try_parse_json(cand)
        if isinstance(parsed, dict):
            return parsed

    # 2) varrer todas as posições de '{' e tentar balancear corretamente
    starts = [i for i, ch in enumerate(text) if ch == '{']
    for start in starts:
        end = _find_matching_closing(text, start, '{', '}')
        if end == -1:
            # tentar rfind de '}' após start
            end = text.find('}', start)
            if end == -1:
                continue
        candidate = text[start:end+1]
        # limpar markers de código
        candidate = candidate.strip('`\n ')
        parsed = try_parse_json(candidate)
        if isinstance(parsed, dict):
            return parsed
        # tentar reparos básicos e reparsear
        repaired = re.sub(r',\s*}', '}', candidate)
        repaired = re.sub(r',\s*\]', ']', repaired)
        # remover comentários de linha iniciados por //
        repaired = re.sub(r'//.*?\n', '\n', repaired)
        parsed = try_parse_json(repaired)
        if isinstance(parsed, dict):
            return parsed

    return None


def extract_classification_json(text: str) -> Optional[dict]:
    """Extrai o objeto de classificação validando o schema mínimo do domínio.

    Regra (VAL-8): um objeto sem ``refactoring_type`` válido é FALHA de
    extração — retorna None e o chamador registra a falha. O valor é
    normalizado para minúsculas ('PURE' -> 'pure'); nenhum default é aplicado.
    """
    result = extract_json_from_text(text)
    if not isinstance(result, dict):
        return None
    refactoring_type = str(result.get("refactoring_type", "")).strip().lower()
    if refactoring_type not in VALID_CLASSIFICATIONS:
        return None
    result["refactoring_type"] = refactoring_type
    return result


def _strip_think_blocks(text: str) -> str:
    """Remove blocos de raciocínio DELIMITADOS POR TAGS da resposta do modelo.

    Somente remoções ancoradas em delimitadores explícitos são aplicadas:
    - <think> ... </think> (case-insensitive), <think/>, <<think>> ... <</think>>
    - linhas iniciadas por [think]/(think)

    As heurísticas anteriores de "linhas repetitivas" e de instruções do
    sistema foram removidas na Fase E2 (VAL-8): operavam sobre texto arbitrário
    e podiam corromper valores de string de um JSON válido antes do parse.
    """
    if not text:
        return text

    # remover tags <think>...</think> (case-insensitive, DOTALL)
    text = re.sub(r'(?is)<think\b[^>]*>.*?</think>', '', text)

    # remover tags self-closing <think/> ou <think ... />
    text = re.sub(r'(?is)<think\b[^>]*/>', '', text)

    # remover tentativas de marcação com <<think>> ... <</think>>
    text = re.sub(r'(?is)<<think>>.*?<</think>>', '', text)

    # remover linhas que comecem com [think] ou (think)
    text = re.sub(r'(?im)^\s*\[?\(?think\)?\]?[:\-\s].*$', '', text)

    return text
