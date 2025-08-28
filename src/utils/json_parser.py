"""
Utilitários para extração e reparo de JSON a partir de texto livre.
"""
from typing import Optional
import json
import re

try:
    import json5 as _json5
except Exception:
    _json5 = None


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
        if _json5 is not None:
            try:
                return _json5.loads(text)
            except Exception:
                return None
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
    # Pre-processamento: remover blocos de 'thinking' produzidos pelo modelo, ex: <think>...</think>
    text = _strip_think_blocks(text)

    # 0) tentar parsear o texto inteiro (alguns modelos retornam apenas JSON)
    whole = text.strip()
    if whole:
        parsed_whole = try_parse_json(whole)
        if parsed_whole is not None:
            return parsed_whole

    # 1) candidatos por regex
    for cand in extract_json_candidates(text):
        parsed = try_parse_json(cand)
        if parsed is not None:
            return parsed
    
    # 1.5) tentar reconhecer arrays JSON no texto completo ou em blocos
    # procurar por blocos que comecem com '[' e terminem em ']' balanceado
    for idx, ch in enumerate(text):
        if ch == '[':
            end_idx = _find_matching_closing(text, idx, '[', ']')
            if end_idx != -1:
                candidate = text[idx:end_idx+1]
                parsed = try_parse_json(candidate)
                if parsed is not None:
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
        if parsed is not None:
            return parsed
        # tentar reparos básicos e reparsear
        repaired = re.sub(r',\s*}', '}', candidate)
        repaired = re.sub(r',\s*\]', ']', repaired)
        # remover comentários de linha iniciados por //
        repaired = re.sub(r'//.*?\n', '\n', repaired)
        parsed = try_parse_json(repaired)
        if parsed is not None:
            return parsed

    # 3) último recurso: tentar extrair pares simples 'key: value' e montar um dict mínimo
    simple_kv = {}
    for m in re.finditer(r'(["\']?)([a-zA-Z0-9_\- ]{3,40})\1\s*[:=]\s*(["\']?)([^\n\r]+?)\3(?:\n|$)', text):
        k = m.group(2).strip()
        v = m.group(4).strip().strip('"\'')
        if len(k) > 1 and len(v) > 0:
            simple_kv[k] = v
    if simple_kv:
        return simple_kv

    return None


def _strip_think_blocks(text: str) -> str:
    """Remove blocos que indiquem 'think' ou raciocínio do modelo.

    Exemplos a remover:
    - <think> ... </think>
    - <think/> ou <think />
    - qualquer variação com maiúsculas/minúsculas
    - blocos entre delimitadores como <<think>> ... <</think>>
    - repetições de instruções do sistema
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

    # remover repetições óbvias de instruções do sistema
    text = re.sub(r'(?is)CRITICAL:\s*You\s+must\s+respond.*?before\s+or\s+after\.', '', text)
    text = re.sub(r'(?is)Analyze\s+this\s+Git\s+diff\s+and\s+classify.*?refactoring\.', '', text)
    
    # remover blocos que começam com "You are an expert" e similares
    text = re.sub(r'(?im)^You\s+are\s+an?\s+expert.*$', '', text)
    text = re.sub(r'(?im)^Based\s+on\s+the\s+provided.*$', '', text)
    
    # remover linhas repetidas ou que parecem confusas
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # pular linhas que são apenas repetições de palavras
        if len(set(line.split())) < len(line.split()) / 3 and len(line.split()) > 5:
            continue
        # pular linhas que são muito repetitivas
        if line and len(line) > 20:
            words = line.split()
            if len(words) > 5 and len(set(words)) < len(words) / 2:
                continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)
