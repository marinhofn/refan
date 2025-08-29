"""
LLM Handler otimizado com suporte a arquivos para diffs grandes e prompt melhorado.
"""

import json
import re
try:
    import json5 as _json5  # optional, helps with trailing commas/comments
except Exception:
    _json5 = None
import os
import datetime
import warnings
from typing import Optional, Protocol, Dict, Any
from src.utils.json_parser import extract_json_from_text

import requests
try:
    import pandas as pd
except ImportError:
    pd = None

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

# Função auxiliar para extração de JSON
def extract_json_from_text(text):
    """Extrai JSON do texto usando várias estratégias"""
    import re
    import json
    
    # Tentar encontrar JSON entre chaves
    json_patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',
        r'```\s*(\{[\s\S]*?\})\s*```',
        r'(\{[\s\S]*?\})',
        r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, dict):
                    return result
            except:
                continue
    return None

# -----------------------------
# Carregador de dados dos CSVs
# -----------------------------

class CSVDataLoader:
    """Carrega dados dos CSVs para preencher automaticamente campos do JSON."""
    
    def __init__(self, csv_dir: str = "csv"):
        self.csv_dir = csv_dir
        self.commits_data = None
        self.purity_data = None
        self._load_csv_data()
    
    def _load_csv_data(self):
        """Carrega dados dos CSVs."""
        if pd is None:
            warnings.warn("pandas não disponível, usando fallback sem dados de CSV")
            return
            
        try:
            # Carrega commits_with_refactoring.csv
            commits_path = os.path.join(self.csv_dir, "commits_with_refactoring.csv")
            if os.path.exists(commits_path):
                self.commits_data = pd.read_csv(commits_path)
                print(f"✅ Carregados {len(self.commits_data)} commits de {commits_path}")
            
            # Carrega puritychecker_detailed_classification.csv
            purity_path = os.path.join(self.csv_dir, "puritychecker_detailed_classification.csv")
            if os.path.exists(purity_path):
                self.purity_data = pd.read_csv(purity_path, sep=';')
                print(f"✅ Carregados {len(self.purity_data)} registros de pureza de {purity_path}")
                
        except Exception as e:
            warnings.warn(f"Erro ao carregar CSVs: {e}")
    
    def get_commit_info(self, commit_hash: str) -> Dict[str, Any]:
        """Obtém informações do commit pelos CSVs."""
        result = {}
        
        if self.commits_data is not None:
            # Procura por commit1 ou commit2
            commit_row = None
            if not self.commits_data[
                (self.commits_data['commit1'] == commit_hash) | 
                (self.commits_data['commit2'] == commit_hash)
            ].empty:
                commit_row = self.commits_data[
                    (self.commits_data['commit1'] == commit_hash) | 
                    (self.commits_data['commit2'] == commit_hash)
                ].iloc[0]
            
            if commit_row is not None:
                result['repository'] = self._extract_repo_name(commit_row.get('project', ''))
                result['commit_hash_before'] = commit_row.get('commit1', '')
                result['commit_hash_current'] = commit_row.get('commit2', '')
        
        if self.purity_data is not None:
            # Busca evidências técnicas do puritychecker
            purity_rows = self.purity_data[self.purity_data['commit'] == commit_hash]
            if not purity_rows.empty:
                evidences = []
                for _, row in purity_rows.iterrows():
                    if pd.notna(row.get('refactoring_description')):
                        evidences.append(row['refactoring_description'])
                
                if evidences:
                    result['technical_evidence'] = '; '.join(evidences[:3])  # Limita a 3 evidências
        
        return result
    
    def _extract_repo_name(self, project_url: str) -> str:
        """Extrai nome do repositório da URL."""
        if not project_url:
            return "unknown"
        # https://github.com/apache/log4j -> log4j
        return project_url.split('/')[-1] if '/' in project_url else project_url

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
                "num_predict": 200000,  # Permitir respostas mais longas da LLM
                "think": False,
                **base_opts,
            },
            # top-level flag to request no 'think' blocks when supported by server
            "think": False,
        }
        last_error = None
        prompt_size = len(prompt)
        # Ajustar timeout proporcional ao tamanho
        if prompt_size > 80000:
            timeout = 6000
        elif prompt_size > 50000:
            timeout = 4200
        elif prompt_size > 30000:
            timeout = 3000
        else:
            timeout = 1800
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
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, llm_type: str = "ollama", csv_dir: str = "csv"):
        self.model = model or LLM_MODEL
        self.host = host or LLM_HOST
        self.llm_prompt = OPTIMIZED_LLM_PROMPT
        self.config = OPTIMIZED_CONFIG
        self.failures_file = "json_failures.json"
        self.csv_loader = CSVDataLoader(csv_dir)
        
        if llm_type == "ollama":
            self.adapter: LLMAdapter = OptimizedOllamaAdapter(self.host, self.model)
        else:
            raise NotImplementedError(f"LLM type '{llm_type}' não suportado ainda.")
    
    def save_json_failure(self, commit_hash: str, repository: str, commit_message: str, raw_response: str, error_msg: str, prompt_excerpt: str | None = None):
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
                "llm_response_excerpt": raw_response,  # Capturar resposta completa sem truncamento
                "analysis_attempt": "JSON parsing failed",
                "prompt_excerpt": prompt_excerpt
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
                previous_hash=commit1,
                repository=repository,
                prompt=prompt
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

    def _process_llm_response(self, llm_response: str, commit_message: str, commit_hash: str = None, previous_hash: str | None = None, repository: str = None, prompt: str | None = None) -> Optional[dict]:
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
                prompt_excerpt = prompt[:2000] if prompt else None
                self.save_json_failure(commit_hash, repository or "unknown", commit_message, llm_response, error_msg, prompt_excerpt=prompt_excerpt)
            return None
        
        # Preservar resposta raw para análise futura
        raw_response = llm_response.strip()
        
        # Primeira tentativa: procurar padrão FINAL: (PRIORIDADE ABSOLUTA)
        final_classification = self._extract_final_classification(llm_response)
        if final_classification:
            print(success(f"Classificação extraída via FINAL: {final_classification}"))
            # Criar resultado imediato com FINAL: - não precisa de JSON
            result_with_final = {
                'repository': repository or 'Unknown',
                'commit_hash_before': previous_hash or 'Unknown', 
                'commit_hash_current': commit_hash or 'Unknown',
                'refactoring_type': final_classification.lower(),
                'justification': raw_response,  # Resposta completa como justificativa
                'commit_message': commit_message,
                'extraction_method': 'final_pattern',
                'llm_raw_response': raw_response
            }
            return result_with_final
        
        # Tentar diferentes estratégias para extrair JSON APENAS se não temos FINAL:
        json_result = None

        # Segunda tentativa: extrair JSON usando utilitário compartilhado
        json_result = extract_json_from_text(llm_response)

        if not json_result:
            print(warning(f"JSON parsing falhou. Tentando extrair justificativa do texto..."))
            
            # Criar JSON com justificativa extraída do texto raw
            json_result = self._extract_analysis_from_raw_text(raw_response)
            
            # Terceira tentativa: retry com prompt simplificado se possível
            if not json_result or not json_result.get("justification") or len(json_result.get("justification", "")) < 10:
                if commit_hash and prompt:
                    print(dim(f"Tentando retry com prompt simplificado para hash {commit_hash}"))
                    retry_result = self._retry_analysis_with_simplified_prompt(
                        commit_hash, previous_hash, repository, prompt
                    )
                    if retry_result and retry_result.get("justification"):
                        json_result = retry_result
            
            if not json_result:
                # Se temos FINAL: mas não conseguimos extrair JSON completo, criar resultado mínimo
                if final_classification:
                    json_result = {
                        'repository': repository or 'Unknown',
                        'commit_hash_before': previous_hash or 'Unknown',
                        'commit_hash_current': commit_hash or 'Unknown',
                        'refactoring_type': final_classification.lower(),
                        'justification': f'Classification extracted from FINAL: pattern. Full response: {raw_response}',
                        'commit_message': commit_message,
                        'extraction_method': 'final_pattern'
                    }
                else:
                    error_msg = "Não foi possível extrair JSON válido da resposta após todas as tentativas"
                    print(error(error_msg))
                    print(dim(f"Resposta recebida (primeiros 1000 chars): {llm_response[:1000]}"))

                    # Salvar falha completa com contexto do prompt
                    if commit_hash:
                        prompt_excerpt = prompt[:2000] if prompt else None
                        self.save_json_failure(commit_hash, repository or "unknown", commit_message, llm_response, error_msg, prompt_excerpt=prompt_excerpt)

                    return None
        
        # Se encontramos FINAL: classification, usar ela ao invés da extraída do JSON
        if final_classification and json_result and json_result.get('refactoring_type'):
            json_result['refactoring_type'] = final_classification.lower()
            print(info(f"Substituindo classificação por FINAL: {final_classification}"))

        # Validação e correção dos campos - fornecer commit/repository como defaults
        # Normalizar sinônimos comuns (project -> repository, commit1/commit2 -> commit_hash_before/_current)
        if isinstance(json_result, dict):
            # 'project' -> 'repository'
            if 'repository' not in json_result and 'project' in json_result:
                json_result['repository'] = json_result.get('project')
            # commit hash synonyms
            if 'commit_hash_before' not in json_result and 'commit1' in json_result:
                json_result['commit_hash_before'] = json_result.get('commit1')
            if 'commit_hash_current' not in json_result and 'commit2' in json_result:
                json_result['commit_hash_current'] = json_result.get('commit2')

        # Validar e preencher campos usando hashes conhecidos (previous_hash, commit_hash)
        json_result = self._validate_and_fix_json_fields(
            json_result,
            commit_message,
            commit_hash=commit_hash,
            previous_hash=previous_hash,
            repository=repository
        )
        
        # Sempre adicionar a resposta raw para análise futura
        if json_result:
            json_result["llm_raw_response"] = raw_response

        return json_result

    def _extract_analysis_from_raw_text(self, raw_response: str) -> dict:
        """
        Extrai informações de análise do texto raw quando JSON parsing falha.
        Usa critérios rígidos para evitar classificação incorreta.
        
        Args:
            raw_response (str): Resposta bruta da LLM
            
        Returns:
            dict: JSON construído a partir do texto
        """
        result = {}
        
        # Procurar por classificação no texto com critérios mais rígidos
        lower_text = raw_response.lower()
        
        # Detectar PURE com indicadores específicos
        pure_indicators = [
            'pure refactoring', 'puro', 'estrutural apenas',
            'sem mudanças funcionais', 'without functional changes',
            'only structural', 'apenas estrutural', 'structure only',
            'no functional impact', 'sem impacto funcional',
            'identical behavior', 'comportamento idêntico'
        ]
        
        # Detectar FLOSS com indicadores específicos
        floss_indicators = [
            'floss', 'functional changes', 'mudanças funcionais',
            'behavioral change', 'mudança comportamental',
            'logic change', 'mudança de lógica',
            'algorithm change', 'mudança de algoritmo',
            'new functionality', 'nova funcionalidade',
            'functional impact', 'impacto funcional'
        ]
        
        # Detectar tipo de refactoring com base em indicadores específicos
        pure_score = sum(1 for indicator in pure_indicators if indicator in lower_text)
        floss_score = sum(1 for indicator in floss_indicators if indicator in lower_text)
        
        if pure_score > floss_score and pure_score > 0:
            result["refactoring_type"] = "pure"
        elif floss_score > pure_score and floss_score > 0:
            result["refactoring_type"] = "floss"
        else:
            # Se não há indicadores claros, analisar contexto mais amplo
            # Procurar por negações de mudanças funcionais (indica PURE)
            negation_patterns = [
                'não altera', 'not change', 'no change', 'without changing',
                'sem alterar', 'maintains', 'preserva', 'mantém'
            ]
            
            negation_count = sum(1 for pattern in negation_patterns if pattern in lower_text)
            
            if negation_count > 0:
                result["refactoring_type"] = "pure"
            else:
                # Default conservador para FLOSS quando incerto
                result["refactoring_type"] = "floss"
        
        # Detectar nível de confiança
        if any(word in lower_text for word in ['high', 'alta', 'certain', 'confident']):
            result["confidence_level"] = "high"
        elif any(word in lower_text for word in ['medium', 'média', 'moderate']):
            result["confidence_level"] = "medium"
        else:
            result["confidence_level"] = "low"
        
        # Usar o texto completo como justificativa se não conseguiu extrair JSON
        # Capturar resposta completa da LLM sem truncamento
        justification = raw_response.strip()
        
        result["justification"] = justification if justification else "Resposta da LLM não contém análise interpretável"
        
        return result

    def _retry_analysis_with_simplified_prompt(self, commit_hash: str, previous_hash: str, repository: str, original_prompt: str) -> Optional[dict]:
        """
        Tenta uma nova análise com prompt mais simples e direto quando a primeira falha.
        """
        try:
            print(dim(f"Executando retry para {commit_hash} com prompt simplificado"))
            
            # Criar prompt mais direto e específico
            simplified_prompt = f"""
CRITICAL: You must respond with ONLY a valid JSON object. No other text before or after.

Analyze this Git diff and classify as either "pure" or "floss" refactoring.

Repository: {repository or 'unknown'}
Previous commit: {previous_hash or 'unknown'}  
Current commit: {commit_hash}

Response format (respond with ONLY this JSON structure):
{{
    "repository": "{repository or 'unknown'}",
    "commit_hash_before": "{previous_hash or 'unknown'}",
    "commit_hash_current": "{commit_hash}",
    "refactoring_type": "pure",
    "justification": "Brief analysis of the changes",
    "technical_evidence": "Specific evidence from the diff",
    "confidence_level": "medium",
    "diff_source": "direct"
}}

{original_prompt[-2000:]}  
"""

            # Fazer nova chamada ao LLM
            response = self._call_ollama(simplified_prompt, model=self.model, attempts=2)
            
            if response:
                # Tentar extrair JSON da nova resposta
                json_result = extract_json_from_text(response)
                if json_result:
                    print(success(f"Retry bem-sucedido para hash {commit_hash}"))
                    return json_result
                else:
                    print(warning(f"Retry também falhou em extrair JSON para hash {commit_hash}"))
            else:
                print(warning(f"Retry não obteve resposta do LLM para hash {commit_hash}"))
                
        except Exception as e:
            print(error(f"Erro durante retry para hash {commit_hash}: {e}"))
            
        return None
    
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

            # Procurar pelo final do JSON mais próximo que balanceie chaves
            end_idx = self._find_json_end_index(llm_response, start_idx)
            if end_idx == -1:
                # fallback: rfind
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
                    # Primeiro tentar json padrão
                    try:
                        result = json.loads(repaired)
                    except json.JSONDecodeError:
                        # Tentar json5 se disponível (mais permissivo)
                        if _json5 is not None:
                            try:
                                result = _json5.loads(repaired)
                            except Exception:
                                raise
                        else:
                            raise
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

    def _find_json_end_index(self, text: str, start_idx: int) -> int:
        """
        Encontra o índice do fechamento '}' correspondente ao primeiro '{' em start_idx
        usando balanceamento simples. Retorna -1 se não encontrar.
        """
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
    
    def _validate_and_fix_json_fields(self, json_result: dict, commit_message: str, commit_hash: str | None = None, previous_hash: str | None = None, repository: str | None = None) -> Optional[dict]:
        """
        Valida e corrige campos obrigatórios do JSON usando dados dos CSVs quando possível.
        
        Args:
            json_result (dict): JSON extraído
            commit_message (str): Mensagem do commit
            
        Returns:
            dict: JSON validado e corrigido ou None se inválido
        """
        # Contador de campos preenchidos automaticamente
        fields_filled = []
        
        # Primeiro, tentar obter dados dos CSVs
        csv_data = {}
        if commit_hash:
            csv_data = self.csv_loader.get_commit_info(commit_hash)
            if csv_data:
                print(f"📊 Dados obtidos dos CSVs para {commit_hash}: {list(csv_data.keys())}")
        
        # Verificar se temos dados válidos do LLM para classificação
        has_valid_classification = (
            json_result.get("refactoring_type") in ("pure", "floss") and
            json_result.get("justification") and 
            json_result.get("justification") != "Analysis failed - insufficient data" and
            len(json_result.get("justification", "")) > 10
        )
        
        # Usar dados dos CSVs com prioridade, fallback para parâmetros passados
        if not json_result.get("repository"):
            json_result["repository"] = csv_data.get("repository") or repository or "unknown"
            if csv_data.get("repository") or repository:
                fields_filled.append("repository")
                
        if not json_result.get("commit_hash_before"):
            json_result["commit_hash_before"] = csv_data.get("commit_hash_before") or previous_hash or "unknown"
            if csv_data.get("commit_hash_before") or previous_hash:
                fields_filled.append("commit_hash_before")
                
        if not json_result.get("commit_hash_current"):
            json_result["commit_hash_current"] = csv_data.get("commit_hash_current") or commit_hash or "unknown"
            if csv_data.get("commit_hash_current") or commit_hash:
                fields_filled.append("commit_hash_current")
        
        # Para evidência técnica, usar dados do CSV se disponível
        if not json_result.get("technical_evidence") and csv_data.get("technical_evidence"):
            json_result["technical_evidence"] = csv_data["technical_evidence"]
            fields_filled.append("technical_evidence")
        
        # Para classificação, só usar padrão se realmente não temos dados válidos
        if not json_result.get("refactoring_type") or json_result.get("refactoring_type") not in ("pure", "floss"):
            json_result["refactoring_type"] = "floss"  # padrão conservativo
            fields_filled.append("refactoring_type")
            
        # Para justificativa, evitar usar o fallback genérico se temos resposta raw da LLM
        current_justification = json_result.get("justification", "")
        if not current_justification or len(current_justification) < 5:
            # Se temos resposta raw, usá-la como justificativa
            raw_response = json_result.get("llm_raw_response", "")
            if raw_response and len(raw_response.strip()) > 10:
                # Capturar resposta completa da LLM sem truncamento
                justification = raw_response.strip()
                json_result["justification"] = f"Resposta LLM (JSON parsing falhou): {justification}"
            else:
                json_result["justification"] = "Analysis failed - insufficient data"
            fields_filled.append("justification")
        
        # Adicionar campos opcionais se não existirem
        optional_fields = {
            "technical_evidence": csv_data.get("technical_evidence", "Not provided"),
            "confidence_level": "low",
            "diff_source": "direct"
        }
        
        for field, default_value in optional_fields.items():
            if field not in json_result or not json_result[field]:
                json_result[field] = default_value
                if field != "technical_evidence" or not csv_data.get("technical_evidence"):
                    fields_filled.append(field)
        
        # Sempre adicionar/atualizar commit_message
        json_result["commit_message"] = commit_message
        
        # Relatório do que foi preenchido
        if fields_filled:
            # Separar campos automáticos dos campos de análise
            auto_fields = [f for f in fields_filled if f in ['repository', 'commit_hash_before', 'commit_hash_current', 'technical_evidence', 'diff_source']]
            analysis_fields = [f for f in fields_filled if f in ['refactoring_type', 'justification', 'confidence_level']]
            
            if auto_fields and not analysis_fields:
                print(dim(f"Campos preenchidos automaticamente do sistema: {', '.join(auto_fields)}"))
            elif analysis_fields:
                auto_msg = f" Campos automáticos: {', '.join(auto_fields)}." if auto_fields else ""
                print(warning(f"LLM não forneceu análise completa. Campos de análise preenchidos com padrão: {', '.join(analysis_fields)}.{auto_msg}"))
            else:
                print(dim(f"Campos complementados: {', '.join(fields_filled)}"))
        else:
            print(success(f"Análise LLM está completa"))
        
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
    
    def _extract_final_classification(self, response: str) -> Optional[str]:
        """Procura por padrão FINAL: PURE ou FINAL: FLOSS na resposta.
        
        Returns:
            'PURE' ou 'FLOSS' se encontrado, None caso contrário
        """
        import re
        
        # Procurar por padrões FINAL: (case insensitive) - expandido para mais variações
        patterns = [
            r'FINAL:\s*(PURE|FLOSS)',
            r'FINAL:\s*(pure|floss)',
            r'Final:\s*(PURE|FLOSS)', 
            r'Final:\s*(pure|floss)',
            r'CONCLUSÃO:\s*(PURE|FLOSS)',
            r'CONCLUSÃO:\s*(pure|floss)',
            r'CLASSIFICATION:\s*(PURE|FLOSS)',
            r'CLASSIFICATION:\s*(pure|floss)',
            r'RESULTADO:\s*(PURE|FLOSS)',
            r'RESULTADO:\s*(pure|floss)',
            # Padrões mais flexíveis
            r'\bFINAL[:\s]+([Pp][Uu][Rr][Ee]|[Ff][Ll][Oo][Ss][Ss])\b',
            r'\b(PURE|FLOSS)\s*$',  # Final da linha
            r'^\s*(PURE|FLOSS)\s*$',  # Linha isolada
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                classification = match.upper()
                # Verificar se é uma classificação válida
                if classification in ['PURE', 'FLOSS']:
                    return classification
                    
        return None

    def get_stats(self) -> dict:
        """
        Retorna estatísticas sobre a configuração atual.
        
        Returns:
            dict: Estatísticas de configuração
        """
        return {
            "model": self.model,
            "host": self.host,
            "max_direct_diff_size": self.config.get("max_direct_diff_size"),
            "use_file_for_large_diffs": self.config.get("use_file_for_large_diffs"),
            "temp_diff_dir": self.config.get("temp_diff_dir"),
            "conservative_classification": self.config.get("conservative_classification")
        }
