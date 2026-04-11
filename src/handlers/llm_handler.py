"""
Módulo dedicado a se comunicar com LLMs (via adaptadores) e processar a resposta.
Garante isolamento por commit e facilidade para trocar o provedor (Ollama, etc.).
"""

from __future__ import annotations

import json
import re
try:
    import json5 as _json5
except Exception:
    _json5 = None
import os
import datetime
from typing import Optional, Protocol

import requests

from src.core.config import (
    LLM_HOST,
    LLM_MODEL,
    LLM_PROMPT,
    DEBUG_SHOW_PROMPT,
    DEBUG_MAX_PROMPT_LENGTH,
    RESET_MODEL_CONTEXT,
    USE_RANDOM_SEED,
    JSON_STRUCTURE,
    check_llm_model_status,
    get_generation_base_options
)
from src.utils.colors import *
from src.utils.json_parser import extract_json_from_text, _find_json_end_index
from src.utils.classification import extract_final_classification
from src.utils.failure_logger import save_json_failure as _save_json_failure
from src.utils.llm_sizing import estimate_token_count, dynamic_num_ctx, reduce_diff_simple
from src.core.settings import settings as _settings

# -----------------------------
# Adaptadores de LLM
# -----------------------------

class LLMAdapter(Protocol):
    def complete(self, prompt: str) -> Optional[str]:
        ...


class OllamaAdapter:
    """Adaptador para a API local do Ollama (/api/generate)."""

    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model

    def complete(self, prompt: str, attempts: int | None = None, keep_alive: str | int | None = None, num_ctx: int | None = None) -> Optional[str]:
        if attempts is None:
            attempts = _settings.max_retries
        base_opts = get_generation_base_options()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive if keep_alive is not None else _settings.get_keep_alive(self.model),
            "options": {
                "num_ctx": num_ctx or _settings.context_small,
                "temperature": _settings.temperature,
                "num_predict": _settings.num_predict,
                **base_opts,
            },
            "think": False,
        }
        last_error = None
        timeout = _settings.get_timeout(len(prompt))
        for i in range(1, attempts + 1):
            try:
                resp = requests.post(self.host, json=payload, timeout=timeout)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code} - {resp.text[:200]}"
                else:
                    data = resp.json()
                    return data.get("response")
            except requests.exceptions.Timeout:
                last_error = "timeout"
            except Exception as e:
                last_error = str(e)
            print(warning(f"Tentativa {i}/{attempts} falhou: {last_error}"))
        print(error(f"Falha após {attempts} tentativas: {last_error}"))
        return None


# -----------------------------
# Utilidades de prompt
# -----------------------------

def build_commit_prompt(commit_data: dict, system_prompt: str) -> str:
    """Monta o prompt completo com definições e contexto do commit."""
    repository = commit_data.get("repository", "")
    commit1 = commit_data.get("commit_hash_before", "")
    commit2 = commit_data.get("commit_hash_current", "")
    diff = commit_data.get("diff", "")

    context = f"""
Repository: {repository}
Commit Hash (Before): {commit1}
Commit Hash (Current): {commit2}

Code Diff:
{diff}

Based solely on the code diff, classify this commit as either "pure" or "floss" refactoring.

IMPORTANT: You MUST classify the commit as either "pure" or "floss" - you cannot leave the refactoring_type field empty.

CRITICAL GUIDELINES FOR CLASSIFICATION:

1. IGNORE THE COMMIT MESSAGE ENTIRELY. Base your classification ONLY on the code changes in the diff.

2. Analyze the diff carefully for:
   - Changes to behavior or functionality (indicates "floss")
   - Bug fixes alongside code reorganization (indicates "floss")
   - Addition of new features while restructuring code (indicates "floss")
   - Only structural changes with no functional changes (indicates "pure")

3. Examples of "pure" refactoring in the diff:
   - Renaming variables, methods, or classes without changing their behavior
   - Extracting methods without altering functionality
   - Reorganizing code structure while maintaining the same behavior
   - Simplifying conditional logic without changing the outcomes
   
4. Examples of "floss" refactoring in the diff:
   - Adding new functionality while restructuring code
   - Fixing bugs in existing code while refactoring
   - Changing behavior or outputs of methods
   - Adding new parameters or changing method signatures in ways that affect behavior

5. Focus on concrete evidence in the code changes. If you see any changes that could affect behavior or functionality, classify as "floss".

Provide your analysis in the following JSON format:
{{
    "repository": "{repository}",
    "commit_hash_before": "{commit1}",
    "commit_hash_current": "{commit2}",
    "refactoring_type": "pure|floss", 
    "justification": "Your detailed reasoning here"
}}
"""
    return f"{system_prompt}\n\n{context}"


# -----------------------------
# Handler principal
# -----------------------------

class LLMHandler:
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, llm_type: str = "ollama"):
        self.model = model or LLM_MODEL
        self.host = host or LLM_HOST
        self.llm_prompt = LLM_PROMPT
        self.failures_file = "json_failures.json"
        if llm_type == "ollama":
            self.adapter: LLMAdapter = OllamaAdapter(self.host, self.model)
        else:
            raise NotImplementedError(f"LLM type '{llm_type}' não suportado ainda.")
    
    def save_json_failure(self, commit_hash: str, repository: str, commit_message: str, raw_response: str, error_msg: str, prompt_excerpt: str | None = None):
        """Delega para src.utils.failure_logger.save_json_failure."""
        _save_json_failure(
            failures_file=self.failures_file,
            commit_hash=commit_hash,
            repository=repository,
            commit_message=commit_message,
            raw_response=raw_response,
            error_msg=error_msg,
            prompt_excerpt=prompt_excerpt,
            extra_fields={"parse_attempts": 1, "notes": "Saved by save_json_failure"},
        )

    def _attempt_multiple_extractions(self, llm_response: str, commit_data: dict, max_attempts: int = 3) -> Optional[dict]:
        """Tenta extrair JSON várias vezes aplicando limpezas incrementais na resposta."""
        attempts = 0
        last_exception = None
        for i in range(max_attempts):
            attempts += 1
            try:
                # tentativa direta
                res = extract_json_from_text(llm_response)
                if res and self._validate_basic_structure(res):
                    return res

                # tentativa: remover linhas com 'Resposta recebida' ou marcadores de salvamento
                cleaned = re.sub(r'\bResposta recebida\b.*', '', llm_response, flags=re.IGNORECASE | re.DOTALL)
                cleaned = re.sub(r'💾.*$', '', cleaned, flags=re.MULTILINE)
                res = extract_json_from_text(cleaned)
                if res and self._validate_basic_structure(res):
                    return res

                # tentativa: buscar trecho entre primeiros '{' e último '}'
                s = llm_response.find('{')
                e = llm_response.rfind('}')
                if s != -1 and e != -1 and e > s:
                    candidate = llm_response[s:e+1]
                    res = extract_json_from_text(candidate)
                    if res and self._validate_basic_structure(res):
                        return res

            except Exception as ex:
                last_exception = ex
                print(dim(f"_attempt_multiple_extractions tentativa {i+1} falhou: {ex}"))
                continue

        # se chegar aqui, salvar contexto para investigação
        err_msg = f"Failed to parse JSON after {attempts} attempts"
        # incluir prompt excerpt if available (commit_data não contém prompt aqui)
        self.save_json_failure(
            commit_hash=commit_data.get('commit_hash_current', ''),
            repository=commit_data.get('repository', ''),
            commit_message=commit_data.get('commit_message', ''),
            raw_response=llm_response,
            error_msg=err_msg,
            prompt_excerpt=None
        )
        if last_exception:
            print(dim(f"Last exception during JSON extraction: {last_exception}"))
        return None

    def analyze_commit(self, repository: str, commit1: str, commit2: str, commit_message: str, diff: str, show_prompt: bool = False, previous_hash: str | None = None):
        # previous_hash é um alias opcional (por exemplo vindo do CSV: commit1) que
        # pode ser passado explicitamente por chamadores que já consultaram a base.
        # Se fornecido, ele deve ter precedência ao preencher commit_hash_before.
        commit_data = {
            "repository": repository,
            "commit_hash_before": previous_hash or commit1,
            "commit_hash_current": commit2,
            "commit_message": commit_message,
            "diff": diff,
        }
        prompt = build_commit_prompt(commit_data, self.llm_prompt)
        if show_prompt and DEBUG_SHOW_PROMPT:
            self.print_prompt(prompt)
        # Health check leve se primeira vez usando este handler
        if not hasattr(self, "_checked"):
            hc = check_llm_model_status(self.model, verbose=False)
            self._checked = True
            if not hc.get("available"):
                print(warning(f"Modelo '{self.model}' pode não estar pronto (health check falhou: {hc.get('error')}). Prosseguindo mesmo assim..."))
        # Possível redução para commits muito grandes
        reduced_meta = {}
        if len(diff) > _settings.max_diff_chars:
            diff, reduced_meta = reduce_diff_simple(diff)
            prompt = build_commit_prompt({**commit_data, "diff": diff}, self.llm_prompt)
            if reduced_meta.get("reduced"):
                print(warning(f"Diff reduzido de {reduced_meta['original_chars']} para {reduced_meta['new_chars']} chars"))
        ctx = dynamic_num_ctx(diff)
        llm_response = self.adapter.complete(prompt, num_ctx=ctx)
        if not llm_response:
            print(error("Falha ao obter resposta do LLM."))
            return None

        # Extrair JSON da resposta com múltiplas estratégias robustas
        json_result = self._extract_json_from_response(llm_response, commit_data)

        # Se falhar, tentar múltiplas extrações com limpezas incrementais
        if not json_result:
            json_result = self._attempt_multiple_extractions(llm_response, commit_data, max_attempts=3)
        
        if not json_result:
            error_msg = "Não foi possível extrair JSON válido da resposta"
            print(error(error_msg))
            print(dim(f"Resposta recebida (primeiros 1000 chars): {llm_response[:1000]}"))
            
            # Salvar falha completa
            prompt_excerpt = prompt[:2000] if prompt else None
            self.save_json_failure(
                commit_hash=commit2, 
                repository=repository, 
                commit_message=commit_message, 
                raw_response=llm_response, 
                error_msg=error_msg,
                prompt_excerpt=prompt_excerpt
            )
            
            # Tentar estratégia de recuperação de dados
            json_result = self._create_fallback_result(llm_response, commit_data)
            if json_result:
                print(warning("Usando estratégia de recuperação de dados"))
            else:
                return None

        # Validação e preenchimento de campos com dados do commit original
        json_result = self._ensure_required_fields(json_result, commit_data)
        
        # Validação final do tipo de refatoramento
        if json_result.get("refactoring_type") not in ("pure", "floss"):
            old_type = json_result.get("refactoring_type", "undefined")
            json_result["refactoring_type"] = "floss"  # Default conservativo
            print(warning(f"Tipo de refatoramento inválido '{old_type}', usando 'floss'"))

        return json_result
    
    def _ensure_required_fields(self, result: dict, commit_data: dict) -> dict:
        """
        Garante que todos os campos obrigatórios estejam presentes e válidos.
        """
        required_fields = {
            'repository': commit_data.get('repository', 'Unknown'),
            'commit_hash_before': commit_data.get('commit_hash_before', 'Unknown'),
            'commit_hash_current': commit_data.get('commit_hash_current', 'Unknown'),
            'commit_message': commit_data.get('commit_message', ''),
            'refactoring_type': 'floss',  # Default conservativo
            'justification': 'Analysis completed but detailed justification not available'
        }
        
        for field, default_value in required_fields.items():
            if field not in result or not result[field] or str(result[field]).strip() == '':
                result[field] = default_value
                if field in ['repository', 'commit_hash_before', 'commit_hash_current']:
                    print(warning(f"Campo '{field}' estava ausente, preenchido com valor padrão"))
                elif field == 'refactoring_type':
                    print(warning(f"Campo '{field}' ausente, usando 'floss' como padrão"))
                elif field == 'justification':
                    print(info(f"Campo '{field}' preenchido com justificação padrão"))
        
        return result

    def print_prompt(self, prompt: str, max_length: Optional[int] = None) -> None:
        if not DEBUG_SHOW_PROMPT:
            return
        max_length = max_length or DEBUG_MAX_PROMPT_LENGTH
        print(f"\n{header('=' * 50)}")
        print(f"{header('PROMPT ENVIADO AO MODELO:')}")
        print(f"{header('=' * 50)}")
        if len(prompt) > max_length:
            print(prompt[:max_length] + dim("... [truncado]"))
            print(dim(f"\nPrompt completo tem {len(prompt)} caracteres. Exibindo primeiros {max_length} caracteres."))
        else:
            print(prompt)
        print(f"{header('=' * 50)}\n")
        
    def _extract_json_from_response(self, llm_response: str, commit_data: dict) -> Optional[dict]:
        """
        Extrai JSON da resposta do LLM usando múltiplas estratégias.
        
        Args:
            llm_response: Resposta bruta do LLM
            commit_data: Dados do commit para fallback
            
        Returns:
            Dicionário extraído ou None se não conseguir
        """
        # Primeiro, delegar para utilitário compartilhado que tenta várias estratégias
        try:
            result = extract_json_from_text(llm_response)
            if result and self._validate_basic_structure(result):
                return result
        except Exception as e:
            print(dim(f"extract_json_from_text falhou: {e}"))

        # Tentar extrair classificação do padrão FINAL: primeiro
        final_classification = extract_final_classification(llm_response)
        if final_classification:
            print(success(f"Classificação extraída via FINAL: {final_classification}"))

        # Fallback para estratégias específicas do handler
        strategies = [
            self._extract_with_patterns,
            self._extract_with_line_parsing,
            self._extract_with_field_extraction
        ]

        for strategy in strategies:
            try:
                result = strategy(llm_response, commit_data)
                if result and self._validate_basic_structure(result):
                    # Se encontramos FINAL: classification, usar ela ao invés da extraída
                    if final_classification and result.get('refactoring_type'):
                        result['refactoring_type'] = final_classification.lower()
                        print(info(f"Substituindo classificação por FINAL: {final_classification}"))
                    return result
            except Exception as e:
                print(dim(f"Estratégia {strategy.__name__} falhou: {e}"))
                continue

        # Se temos FINAL: mas não conseguimos extrair JSON completo, criar resultado mínimo
        if final_classification:
            return {
                'repository': commit_data.get('repository', 'Unknown'),
                'commit_hash_before': commit_data.get('commit_hash_before', 'Unknown'),
                'commit_hash_current': commit_data.get('commit_hash_current', 'Unknown'),
                'refactoring_type': final_classification.lower(),
                'justification': f'Classification extracted from FINAL: pattern. Full response: {llm_response[:200]}...',
                'commit_message': commit_data.get('commit_message', ''),
                'extraction_method': 'final_pattern'
            }

        return None
    
    def _extract_with_patterns(self, response: str, commit_data: dict) -> Optional[dict]:
        """Extração usando padrões regex."""
        json_patterns = [
            r'```json\s*(\{[\s\S]*?\})\s*```',
            r'```\s*(\{[\s\S]*?\})\s*```',
            r'(\{[\s\S]*?\})',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'  # JSON aninhado básico
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.MULTILINE | re.DOTALL)
            for match in matches:
                try:
                    try:
                        result = json.loads(match)
                    except json.JSONDecodeError:
                        if _json5 is not None:
                            result = _json5.loads(match)
                        else:
                            raise
                    if isinstance(result, dict):
                        return result
                except Exception:
                    # tentar balancear chaves e reparsear
                    start_idx = response.find(match)
                    end_idx = _find_json_end_index(response, start_idx)
                    if end_idx != -1:
                        candidate = response[start_idx:end_idx+1]
                        try:
                            result = json.loads(candidate)
                            if isinstance(result, dict):
                                return result
                        except Exception:
                            if _json5 is not None:
                                try:
                                    result = _json5.loads(candidate)
                                    if isinstance(result, dict):
                                        return result
                                except Exception:
                                    pass
                    continue
        return None

    def _extract_with_line_parsing(self, response: str, commit_data: dict) -> Optional[dict]:
        """Extração linha por linha procurando campos específicos."""
        result = {}
        lines = response.split('\n')
        
        field_patterns = {
            'project': [r'"project":\s*"([^"]*)"', r'project[:\s]*([^\n,}]+)'],
            'repository': [r'"repository":\s*"([^"]*)"', r'repository[:\s]*([^\n,}]+)'],
            'commit_hash_before': [r'"commit_hash_before":\s*"([^"]*)"', r'commit_hash_before[:\s]*([^\n,}]+)'],
            'commit_hash_current': [r'"commit_hash_current":\s*"([^"]*)"', r'commit_hash_current[:\s]*([^\n,}]+)'],
            'refactoring_type': [r'"refactoring_type":\s*"([^"]*)"', r'refactoring_type[:\s]*([^\n,}]+)', r'(pure|floss)'],
            'justification': [r'"justification":\s*"([^"]*)"', r'justification[:\s]*([^\n,}]+)']
        }
        
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    value = match.group(1).strip().strip('"').strip("'")
                    if value and value not in ['', 'Unknown', 'None']:
                        result[field] = value
                        break
        
        # Se 'project' foi encontrado, mapear para 'repository' como fallback
        if 'repository' not in result and 'project' in result:
            result['repository'] = result.get('project')

        return result if len(result) >= 2 else None
    
    def _extract_with_field_extraction(self, response: str, commit_data: dict) -> Optional[dict]:
        """Extração baseada na identificação de campos específicos no texto."""
        result = {}
        
        # Procurar por "pure" ou "floss" no texto
        refactoring_match = re.search(r'\b(pure|floss)\b', response.lower())
        if refactoring_match:
            result['refactoring_type'] = refactoring_match.group(1)
        
        # Procurar por justificação em texto livre
        justification_patterns = [
            r'(?:justification|reasoning|explanation)[\s:]*(.+?)(?=\n\n|\n[A-Z]|\.|$)',
            r'(?:this|the commit|changes)[\s\w]*(?:are|is|represents?)[\s\w]*(.+?)(?=\.|$)'
        ]
        
        for pattern in justification_patterns:
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            if match:
                justification = match.group(1).strip()
                if len(justification) > 10:  # Justificação mínima
                    result['justification'] = justification  # Capturar justificação completa
                    break
        
        return result if 'refactoring_type' in result else None
    
    def _validate_basic_structure(self, result: dict) -> bool:
        """Valida se o resultado tem a estrutura mínima necessária."""
        return (
            isinstance(result, dict) and 
            ('refactoring_type' in result or 'justification' in result) and
            len(result) > 0
        )
    
    def _create_fallback_result(self, response: str, commit_data: dict) -> Optional[dict]:
        """
        Cria um resultado de fallback quando não conseguimos extrair JSON.
        """
        print(warning("Tentando estratégia de recuperação de dados..."))
        
        # Tentar determinar o tipo baseado em palavras-chave no texto
        response_lower = response.lower()
        
        # Detectar tipo de refatoramento
        refactoring_type = "floss"  # Default conservativo
        
        if any(keyword in response_lower for keyword in ['pure', 'purely', 'only structural', 'no functional', 'no behavior']):
            if not any(keyword in response_lower for keyword in ['bug', 'fix', 'feature', 'new', 'behavior', 'functional']):
                refactoring_type = "pure"
        
        # Criar justificação baseada na análise
        justification_parts = []
        
        if 'behavioral' in response_lower or 'behavior' in response_lower:
            justification_parts.append("Contains behavioral changes")
        if 'structural' in response_lower:
            justification_parts.append("Contains structural changes")
        if 'bug' in response_lower or 'fix' in response_lower:
            justification_parts.append("Contains bug fixes")
        if 'feature' in response_lower or 'new' in response_lower:
            justification_parts.append("Contains new features")
            
        if not justification_parts:
            justification_parts.append("Unable to extract detailed analysis from LLM response")
        
        # Tentar extrair um trecho da resposta como justificação
        first_sentence = response.split('.')[0]
        if len(first_sentence) > 20 and len(first_sentence) < 200:
            justification_parts.append(f"LLM output: {first_sentence}")
        
        result = {
            'repository': commit_data.get('repository', 'Unknown'),
            'commit_hash_before': commit_data.get('commit_hash_before', 'Unknown'),
            'commit_hash_current': commit_data.get('commit_hash_current', 'Unknown'),
            'refactoring_type': refactoring_type,
            'justification': '. '.join(justification_parts),  # Capturar justificação completa
            'commit_message': commit_data.get('commit_message', ''),
            'fallback_used': True
        }
        
        return result
        

