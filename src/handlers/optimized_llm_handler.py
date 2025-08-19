"""
LLM Handler otimizado com suporte a arquivos para diffs grandes e prompt melhorado.
"""

import json
import re
import os
import datetime
from typing import Optional, Protocol

import requests

from src.analyzers.optimized_prompt import (
    OPTIMIZED_LLM_PROMPT,
    build_optimized_commit_prompt_with_file_support,
    cleanup_temp_diff_file,
    OPTIMIZED_CONFIG
)
from src.core.config import (
    LLM_HOST,
    LLM_MODEL,
    DEBUG_SHOW_PROMPT,
    DEBUG_MAX_PROMPT_LENGTH,
    check_llm_model_status,
    get_generation_base_options,
)
from src.utils.colors import *
import math

# -----------------------------
# Utilidades de otimização de prompt
# -----------------------------

def estimate_token_count(text: str) -> int:
    """Estimativa grosseira de tokens (~4 chars/token média inglês)."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def dynamic_num_ctx(diff_text: str) -> int:
    tokens = estimate_token_count(diff_text)
    if tokens < 3000:
        return 4096
    if tokens < 6000:
        return 6144
    if tokens < 9000:
        return 8192
    # Para diffs gigantes limitar para evitar explosão de memória
    return 8192

def reduce_diff(diff_text: str, max_chars: int = 60000, per_file_line_limit: int = 400) -> tuple[str, dict]:
    """Reduz diff grande limitando linhas por arquivo e tamanho total.
    Retorna diff possivelmente reduzido e metadados de redução.
    """
    if len(diff_text) <= max_chars:
        return diff_text, {"reduced": False}
    sections = diff_text.split('\n')
    reduced_lines = []
    file_line_count = 0
    current_file = None
    per_file_counter = 0
    truncated_files = 0
    for line in sections:
        if line.startswith('diff --git'):
            current_file = line
            per_file_counter = 0
        if per_file_counter < per_file_line_limit:
            reduced_lines.append(line)
            per_file_counter += 1
        else:
            if line.startswith('@@'):
                # manter cabeçalho de hunk para contexto mesmo se estourou limite
                reduced_lines.append(line)
            elif line.startswith('diff --git'):
                reduced_lines.append(line)
                per_file_counter = 1
            else:
                # pular linha
                if per_file_counter == per_file_line_limit:
                    reduced_lines.append('... (linhas adicionais omitidas)')
                    truncated_files += 1
                    per_file_counter += 1
        if len('\n'.join(reduced_lines)) > max_chars:
            reduced_lines.append('\n... (diff truncado por limite global)')
            break
    new_diff = '\n'.join(reduced_lines)
    return new_diff, {"reduced": True, "original_chars": len(diff_text), "new_chars": len(new_diff), "truncated_files": truncated_files}

# -----------------------------
# Adaptadores de LLM
# -----------------------------

class LLMAdapter(Protocol):
    def complete(self, prompt: str) -> Optional[str]:
        ...


class OptimizedOllamaAdapter:
    """Adaptador otimizado para a API local do Ollama com suporte a arquivos."""

    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model

    def complete(self, prompt: str, attempts: int = 3, keep_alive: str | int | None = None, num_ctx: int | None = None) -> Optional[str]:
        base_opts = get_generation_base_options()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # manter modelo carregado por mais tempo para evitar cold start em modelos grandes
            "keep_alive": keep_alive if keep_alive is not None else "10m",
            "options": {
                "num_ctx": num_ctx or 4096,
                "temperature": 0.1,
                "num_predict": 800,
                **base_opts,
            },
        }
        last_error = None
        prompt_size = len(prompt)
        # Ajustar timeout proporcional ao tamanho
        if prompt_size > 80000:
            timeout = 600
        elif prompt_size > 50000:
            timeout = 420
        elif prompt_size > 30000:
            timeout = 300
        else:
            timeout = 180
        for i in range(1, attempts + 1):
            try:
                print(dim(f"Envio tentativa {i}/{attempts} - prompt {prompt_size} chars timeout {timeout}s"))
                resp = requests.post(self.host, json=payload, timeout=timeout)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code} - {resp.text[:200]}"
                else:
                    data = resp.json()
                    return data.get("response")
            except requests.exceptions.Timeout:
                last_error = f"timeout > {timeout}s"
            except Exception as e:
                last_error = str(e)
            print(warning(f"Tentativa {i}/{attempts} falhou: {last_error}"))
        print(error(f"Falha após {attempts} tentativas: {last_error}"))
        return None


# -----------------------------
# Handler principal otimizado
# -----------------------------

class OptimizedLLMHandler:
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, llm_type: str = "ollama"):
        self.model = model or LLM_MODEL
        self.host = host or LLM_HOST
        self.llm_prompt = OPTIMIZED_LLM_PROMPT
        self.config = OPTIMIZED_CONFIG
        self.failures_file = "json_failures.json"
        
        if llm_type == "ollama":
            self.adapter: LLMAdapter = OptimizedOllamaAdapter(self.host, self.model)
        else:
            raise NotImplementedError(f"LLM type '{llm_type}' não suportado ainda.")
    
    def save_json_failure(self, commit_hash: str, repository: str, commit_message: str, raw_response: str, error_msg: str):
        """
        Salva falhas de parsing JSON em arquivo separado.
        
        Args:
            commit_hash (str): Hash do commit que falhou
            repository (str): Repositório do commit
            commit_message (str): Mensagem do commit
            raw_response (str): Resposta completa da LLM
            error_msg (str): Mensagem de erro detalhada
        """
        try:
            failure_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "commit_hash": commit_hash,
                "repository": repository,
                "commit_message": commit_message,
                "error": error_msg,
                "llm_response_complete": raw_response,
                "llm_response_excerpt": raw_response[:2000] if raw_response else None,
                "analysis_attempt": "JSON parsing failed"
            }
            
            # Carregar falhas existentes
            existing_failures = []
            if os.path.exists(self.failures_file):
                try:
                    with open(self.failures_file, 'r', encoding='utf-8') as f:
                        existing_failures = json.load(f)
                except json.JSONDecodeError:
                    print(warning(f"Arquivo de falhas {self.failures_file} corrompido, criando novo"))
                    existing_failures = []
            
            # Adicionar nova falha
            existing_failures.append(failure_entry)
            
            # Salvar arquivo atualizado
            with open(self.failures_file, 'w', encoding='utf-8') as f:
                json.dump(existing_failures, f, indent=2, ensure_ascii=False)
            
            print(warning(f"💾 Falha JSON salva em {self.failures_file} (total: {len(existing_failures)} falhas)"))
            
        except Exception as e:
            print(error(f"⚠️ Erro ao salvar falha JSON: {str(e)}"))

    def analyze_commit(self, repository: str, commit1: str, commit2: str, commit_message: str, diff: str, show_prompt: bool = False):
        """
        Analisa um commit usando o prompt e estratégia otimizados.
        
        Args:
            repository (str): URL do repositório
            commit1 (str): Hash do commit anterior
            commit2 (str): Hash do commit atual
            commit_message (str): Mensagem do commit
            diff (str): Diff completo entre os commits
            show_prompt (bool): Se deve mostrar o prompt antes do envio
            
        Returns:
            dict: Resultado da análise ou None em caso de erro
        """
        # Health check leve na primeira utilização
        if not hasattr(self, "_checked"):
            hc = check_llm_model_status(self.model, verbose=False)
            self._checked = True
            if not hc.get("available"):
                print(warning(f"Modelo '{self.model}' pode não estar pronto (health check falhou: {hc.get('error')}). Prosseguindo..."))
        commit_data = {
            "repository": repository,
            "commit_hash_before": commit1,
            "commit_hash_current": commit2,
            "commit_message": commit_message,
            "diff": diff,
        }
        
        # Possível redução de diff antes de construir prompt
        original_diff = diff
        reduced_meta = {}
        if len(diff) > 60000:  # heurística
            diff, reduced_meta = reduce_diff(diff)
            if reduced_meta.get("reduced"):
                print(warning(f"Diff reduzido de {reduced_meta['original_chars']} para {reduced_meta['new_chars']} chars (arquivos truncados: {reduced_meta['truncated_files']})"))
        # Construir prompt com suporte a arquivo
        prompt, diff_file_path = build_optimized_commit_prompt_with_file_support({**commit_data, "diff": diff}, self.llm_prompt)
        
        # Mostrar informações sobre a estratégia usada
        if diff_file_path:
            print(info(f"Diff grande ({len(diff)} chars) - usando abordagem de arquivo: {diff_file_path}"))
        else:
            print(info(f"Diff pequeno ({len(diff)} chars) - enviando diretamente no prompt"))
        
        if show_prompt and DEBUG_SHOW_PROMPT:
            self.print_prompt(prompt)
        
        try:
            # Enviar para o LLM com parâmetros dinâmicos
            ctx = dynamic_num_ctx(diff)
            llm_response = self.adapter.complete(prompt, num_ctx=ctx)
            if not llm_response:
                print(error("Falha ao obter resposta do LLM."))
                return None

            # Processar resposta com informações para logging de falhas
            result = self._process_llm_response(
                llm_response, 
                commit_message, 
                commit_hash=commit2, 
                repository=repository
            )
            
            # Adicionar informações extras sobre o processamento
            if result:
                result["diff_size_chars"] = len(diff)
                result["diff_lines"] = len(diff.splitlines())
                if reduced_meta.get("reduced"):
                    result["reduction"] = reduced_meta
                result["processing_method"] = "file" if diff_file_path else "direct"
            
            return result
            
        finally:
            # Limpar arquivo temporário se foi criado
            if diff_file_path:
                cleanup_temp_diff_file(diff_file_path)

    def analyze_commit_refactoring(self, current_hash: str, previous_hash: str, repository: str, diff_content: str, commit_message: str | None = None, repo_path: str | None = None):
        """
        Analisa um commit de refatoramento usando handler otimizado.
        
        Args:
            current_hash (str): Hash do commit atual
            previous_hash (str): Hash do commit anterior
            repository (str): URL do repositório
            diff_content (str): Conteúdo do diff
            
        Returns:
            dict: Resultado da análise com campos 'success' e dados do commit
        """
        try:
            # Obter mensagem do commit apenas se não fornecida para evitar clone/atualização duplicada
            if not commit_message:
                commit_message = "Commit message not available"
                try:
                    from src.handlers.git_handler import GitHandler
                    git_handler = GitHandler()
                    if repo_path is None:
                        success_flag, repo_path = git_handler.ensure_repo_cloned(repository)
                    else:
                        success_flag = True
                    if success_flag:
                        commit_message = git_handler.get_commit_message(repo_path, current_hash) or commit_message
                except Exception as e:
                    print(warning(f"Não foi possível obter mensagem do commit: {e}"))
            
            # Usar o método analyze_commit existente
            result = self.analyze_commit(
                repository=repository,
                commit1=previous_hash,
                commit2=current_hash,
                commit_message=commit_message,
                diff=diff_content,
                show_prompt=False
            )
            
            if result:
                # Adicionar campo success esperado pelo main
                result['success'] = True
                return result
            else:
                return {
                    'success': False,
                    'error': 'Falha na análise do LLM'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro durante análise: {str(e)}'
            }

    def _process_llm_response(self, llm_response: str, commit_message: str, commit_hash: str = None, repository: str = None) -> Optional[dict]:
        """
        Processa a resposta do LLM e extrai o JSON.
        
        Args:
            llm_response (str): Resposta raw do LLM
            commit_message (str): Mensagem do commit para adicionar ao resultado
            commit_hash (str): Hash do commit para logging de falhas
            repository (str): Repositório para logging de falhas
            
        Returns:
            dict: Resultado processado ou None em caso de erro
        """
        if not llm_response or not llm_response.strip():
            error_msg = "Resposta vazia do LLM"
            print(error(error_msg))
            if commit_hash:
                self.save_json_failure(commit_hash, repository or "unknown", commit_message, llm_response, error_msg)
            return None
        
        # Tentar diferentes estratégias para extrair JSON
        json_result = None
        
        # Estratégia 1: Buscar JSON completo entre chaves
        json_patterns = [
            r'({[\s\S]*?})',
            r'```json\s*({[\s\S]*?})\s*```',
            r'```\s*({[\s\S]*?})\s*```',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, llm_response, re.MULTILINE | re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    json_result = json.loads(json_str)
                    break
                except json.JSONDecodeError:
                    continue
        
        # Estratégia 2: Tentar reparar JSON incompleto
        if not json_result:
            json_result = self._attempt_json_repair(llm_response)
        
        if not json_result:
            error_msg = "Não foi possível extrair JSON válido da resposta"
            print(error(error_msg))
            print(dim(f"Resposta recebida (primeiros 1000 chars): {llm_response[:1000]}"))

            # Salvar falha completa
            if commit_hash:
                self.save_json_failure(commit_hash, repository or "unknown", commit_message, llm_response, error_msg)

            return None

        # Validação e correção dos campos - fornecer commit/repository como defaults
        json_result = self._validate_and_fix_json_fields(json_result, commit_message, commit_hash=commit_hash, repository=repository)

        return json_result
    
    def _attempt_json_repair(self, llm_response: str) -> Optional[dict]:
        """
        Tenta reparar JSON malformado comum.
        
        Args:
            llm_response (str): Resposta do LLM
            
        Returns:
            dict: JSON reparado ou None se não conseguir
        """
        try:
            # Procurar por início de JSON
            start_idx = llm_response.find('{')
            if start_idx == -1:
                return None
            
            # Procurar pelo final do JSON
            end_idx = llm_response.rfind('}')
            if end_idx == -1:
                return None
            
            json_text = llm_response[start_idx:end_idx+1]
            
            # Reparos comuns
            repairs = [
                # Tentar o JSON como está
                lambda x: x,
                # Escapar aspas duplas dentro de strings
                lambda x: self._fix_quotes_in_json(x),
                # Remover quebras de linha dentro de strings
                lambda x: re.sub(r'"\s*\n\s*([^"]*)\s*\n\s*"', r'"\1"', x),
                # Vírgula desnecessária antes de }
                lambda x: re.sub(r',\s*}', '}', x),
                # Chaves não fechadas
                lambda x: x + '}' if x.count('{') > x.count('}') else x,
            ]
            
            for repair in repairs:
                try:
                    repaired = repair(json_text)
                    result = json.loads(repaired)
                    if repair != repairs[0]:  # Se foi reparado
                        print(warning("JSON foi reparado automaticamente"))
                    return result
                except:
                    continue
                    
        except Exception:
            pass
        
        return None
    
    def _fix_quotes_in_json(self, json_str: str) -> str:
        """
        Corrige aspas não escapadas dentro de valores JSON.
        
        Args:
            json_str (str): String JSON com possíveis aspas não escapadas
            
        Returns:
            str: JSON com aspas corrigidas
        """
        try:
            # Usar regex para encontrar e corrigir valores de string
            # Padrão: "campo": "valor com "aspas" problemáticas"
            
            def fix_value(match):
                field = match.group(1)
                value = match.group(2)
                
                # Escapar aspas duplas que não estão escapadas
                # Primeiro, temporariamente marcar aspas já escapadas
                temp_value = value.replace('\\"', '___ESCAPED_QUOTE___')
                # Escapar aspas não escapadas
                fixed_value = temp_value.replace('"', '\\"')
                # Restaurar aspas originalmente escapadas
                fixed_value = fixed_value.replace('___ESCAPED_QUOTE___', '\\"')
                
                return f'"{field}": "{fixed_value}"'
            
            # Aplicar correção para campos de string
            pattern = r'"([^"]+)":\s*"([^"]*(?:[^\\]"[^"]*)*)"'
            fixed_json = re.sub(pattern, fix_value, json_str, flags=re.DOTALL)
            
            return fixed_json
            
        except Exception:
            return json_str
    
    def _validate_and_fix_json_fields(self, json_result: dict, commit_message: str, commit_hash: str | None = None, repository: str | None = None) -> Optional[dict]:
        """
        Valida e corrige campos obrigatórios do JSON.
        
        Args:
            json_result (dict): JSON extraído
            commit_message (str): Mensagem do commit
            
        Returns:
            dict: JSON validado e corrigido ou None se inválido
        """
        # Campos obrigatórios - preferir valores que já conhecemos do commit
        required_fields = {
            "repository": repository or "",
            "commit_hash_before": json_result.get('commit_hash_before', ''),
            "commit_hash_current": commit_hash or json_result.get('commit_hash_current', ''),
            "refactoring_type": "floss",  # default conservativo
            "justification": "Analysis failed - insufficient data"
        }

        # Preencher campos faltantes usando os defaults acima
        for field, default_value in required_fields.items():
            if field not in json_result or not json_result[field]:
                json_result[field] = default_value
                print(warning(f"Campo '{field}' estava ausente, preenchido com valor padrão"))
        
        # Validação específica do tipo de refatoramento
        if json_result.get("refactoring_type") not in ("pure", "floss"):
            print(warning(f"Tipo de refatoramento inválido: {json_result.get('refactoring_type')}, usando 'floss' como padrão"))
            json_result["refactoring_type"] = "floss"
        
    # Adicionar campos opcionais se não existirem
        optional_fields = {
            "technical_evidence": "Not provided",
            "confidence_level": "low",
            "diff_source": "unknown",
            "commit_message": commit_message
        }
        
        for field, default_value in optional_fields.items():
            if field not in json_result:
                json_result[field] = default_value
        
        # Atualizar commit_message
        json_result["commit_message"] = commit_message
        
        return json_result

    def print_prompt(self, prompt: str, max_length: Optional[int] = None) -> None:
        """
        Imprime o prompt para debug, limitando o tamanho se necessário.
        
        Args:
            prompt (str): Prompt a ser exibido
            max_length (int, optional): Tamanho máximo para exibição
        """
        if not DEBUG_SHOW_PROMPT:
            return
            
        max_length = max_length or DEBUG_MAX_PROMPT_LENGTH
        print(f"\n{header('=' * 50)}")
        print(f"{header('PROMPT OTIMIZADO ENVIADO AO MODELO:')}")
        print(f"{header('=' * 50)}")
        
        if len(prompt) > max_length:
            print(prompt[:max_length] + dim("... [truncado para exibição]"))
            print(dim(f"\nPrompt completo tem {len(prompt)} caracteres. Exibindo primeiros {max_length} caracteres."))
        else:
            print(prompt)
        print(f"{header('=' * 50)}\n")

    def get_stats(self) -> dict:
        """
        Retorna estatísticas sobre a configuração atual.
        
        Returns:
            dict: Estatísticas de configuração
        """
        return {
            "model": self.model,
            "host": self.host,
            "max_direct_diff_size": self.config["max_direct_diff_size"],
            "use_file_for_large_diffs": self.config["use_file_for_large_diffs"],
            "temp_diff_dir": self.config["temp_diff_dir"],
            "conservative_classification": self.config["conservative_classification"]
        }
