"""Handler unificado para comunicação com LLMs via Ollama.

Resultado da fusão de llm_handler.py (original) e optimized_llm_handler.py
(REFACTORING_PLAN.md Phase 3), endurecido na Fase E2 (EVOLUTION_PLAN.md,
VAL-2/VAL-3): a extração de resposta aceita apenas vereditos explícitos do
modelo (linha FINAL: e/ou JSON validado por schema); respostas sem veredito
são FALHAS registradas — nenhuma heurística fabrica rótulo, nenhum campo de
pesquisa recebe valor simulado. Inclui monitoramento/reset DeepSeek.
"""

import hashlib
import os
import random
import time
from typing import Optional, Protocol
from src.utils.json_parser import extract_classification_json
from src.utils.classification import extract_final_classification
from src.utils.failure_logger import save_json_failure as _save_json_failure

import requests

from src.analyzers.optimized_prompt import (
    OPTIMIZED_LLM_PROMPT,
    build_optimized_commit_prompt_with_file_support,
    cleanup_temp_diff_file,
    OPTIMIZED_CONFIG,
)

# Re-export para compatibilidade: build_commit_prompt usa o prompt otimizado
# como wrapper simplificado para callers que esperam (commit_data, system_prompt) -> str
def build_commit_prompt(commit_data: dict, system_prompt: str) -> str:
    """Constrói prompt para classificação de commit (compatibilidade).

    Delega para build_optimized_commit_prompt_with_file_support, ignorando
    o suporte a arquivos temporários (retorna apenas o prompt string).
    """
    prompt, _temp_file = build_optimized_commit_prompt_with_file_support(
        commit_data=commit_data,
        system_prompt=system_prompt,
    )
    return prompt


from src.core.config import (
    LLM_HOST,
    get_current_llm_model,  # Use function instead of static import
    DEBUG_SHOW_PROMPT,
    DEBUG_MAX_PROMPT_LENGTH,
    check_llm_model_status,
    get_generation_base_options,
)
from src.utils.colors import dim, error, header, info, success, warning

# -----------------------------
# Utilidades de otimização de prompt
# -----------------------------

from src.utils.llm_sizing import plan_generation
from src.core.settings import settings as _settings


def reduce_diff(diff_text: str, max_chars: int | None = None, per_file_line_limit: int | None = None) -> tuple:
    """Reduz diff grande limitando linhas por arquivo e tamanho total.

    Mais sofisticada que reduce_diff_simple: preserva cabeçalhos de hunk
    e limita por arquivo antes de truncar globalmente. Limiares default
    vêm de RefanSettings (max_diff_chars, per_file_line_limit).
    """
    if max_chars is None:
        max_chars = _settings.max_diff_chars
    if per_file_line_limit is None:
        per_file_line_limit = _settings.per_file_line_limit
    if len(diff_text) <= max_chars:
        return diff_text, {"reduced": False}
    sections = diff_text.split('\n')
    reduced_lines = []
    per_file_counter = 0
    truncated_files = 0
    # Comprimento acumulado incremental: o join por iteração era O(n^2)
    # exatamente nos diffs grandes que esta função existe para tratar.
    running_len = 0

    def _append(text: str) -> None:
        nonlocal running_len
        reduced_lines.append(text)
        running_len += len(text) + 1  # +1 pelo '\n' do join final

    for line in sections:
        if line.startswith('diff --git'):
            per_file_counter = 0
        if per_file_counter < per_file_line_limit:
            _append(line)
            per_file_counter += 1
        else:
            if line.startswith('@@'):
                _append(line)
            elif line.startswith('diff --git'):
                _append(line)
                per_file_counter = 1
            else:
                if per_file_counter == per_file_line_limit:
                    _append('... (linhas adicionais omitidas)')
                    truncated_files += 1
                    per_file_counter += 1
        if running_len > max_chars:
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


class OllamaAdapter:
    """Adaptador otimizado para a API local do Ollama com suporte a arquivos."""

    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model
        # Monitoramento específico para DeepSeek
        self._last_duration = None
        self._analysis_count = 0
        self._performance_degraded = False

    def complete(self, prompt: str, attempts: int | None = None, keep_alive: str | int | None = None, num_ctx: int | None = None, num_predict: int | None = None, seed: int | None = None) -> Optional[str]:
        if attempts is None:
            attempts = _settings.max_retries
        base_opts = get_generation_base_options()

        # Resolvido uma única vez fora do loop de retry: as referências nos
        # blocos de monitoramento/timeout abaixo dependem desta variável.
        is_deepseek = _settings.is_deepseek(self.model)

        # VAL-7: o num_ctx planejado pelo chamador é respeitado; o teto
        # empírico DeepSeek atua como LIMITE superior, não mais como
        # override cego para context_small.
        effective_num_ctx = num_ctx or _settings.context_small
        if is_deepseek:
            effective_num_ctx = min(effective_num_ctx, _settings.context_ceiling_deepseek)
        effective_num_predict = num_predict if num_predict is not None else _settings.num_predict

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive if keep_alive is not None else _settings.get_keep_alive(self.model),
            "options": {
                "num_ctx": effective_num_ctx,
                "temperature": _settings.temperature,
                "num_predict": effective_num_predict,
                "think": False,
                **base_opts,
            },
            "think": False,
        }
        # Reprodutibilidade (H5 + E3/REP-2): seed explícito do chamador tem
        # prioridade; sem ele, aplica o regime das settings (seed fixo, ou
        # omissão no regime aleatório legado). Ver docs/REPRODUCIBILITY.md.
        if seed is not None:
            payload["options"]["seed"] = seed
        elif not _settings.use_random_seed:
            payload["options"]["seed"] = _settings.llm_seed
        last_error = None
        prompt_size = len(prompt)
        timeout = _settings.get_timeout(prompt_size)
        start_time = time.time()
        
        for i in range(1, attempts + 1):
            try:
                print(dim(f"Envio tentativa {i}/{attempts} - prompt {prompt_size} chars timeout {timeout}s"))
                resp = requests.post(self.host, json=payload, timeout=timeout)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code} - {resp.text[:200]}"
                else:
                    data = resp.json()
                    response = data.get("response")
                    
                    # Monitoramento de performance para DeepSeek
                    if is_deepseek and response:
                        end_time = time.time()
                        duration = end_time - start_time
                        self._track_deepseek_performance(duration, prompt_size)
                    
                    return response
            except requests.exceptions.Timeout:
                last_error = f"timeout > {timeout}s"
                # Para DeepSeek, tentar reset em caso de timeout
                if is_deepseek and i < attempts:
                    print(warning("DeepSeek timeout - tentando reset do modelo"))
                    self._reset_deepseek_context()
            except Exception as e:
                last_error = str(e)
            print(warning(f"Tentativa {i}/{attempts} falhou: {last_error}"))
        print(error(f"Falha após {attempts} tentativas: {last_error}"))
        return None

    def _track_deepseek_performance(self, duration: float, prompt_size: int):
        """Monitora performance do DeepSeek e detecta degradação"""
        self._analysis_count += 1
        
        if self._last_duration is not None:
            # Detectar degradação significativa (3x mais lento)
            if duration > self._last_duration * 3:
                print(warning(f"DeepSeek: Performance degradada detectada: {duration:.1f}s vs {self._last_duration:.1f}s"))
                self._performance_degraded = True
                self._reset_deepseek_context()
        
        # Reset preventivo periódico (ver settings.deepseek_reset_interval)
        if self._analysis_count % _settings.deepseek_reset_interval == 0:
            print(dim(f"DeepSeek: Reset automático após {self._analysis_count} análises"))
            self._reset_deepseek_context()
        
        self._last_duration = duration
        print(dim(f"DeepSeek: Análise #{self._analysis_count} - {duration:.1f}s (prompt: {prompt_size} chars)"))
    
    def _reset_deepseek_context(self):
        """Força reset do contexto do DeepSeek"""
        try:
            reset_payload = {
                "model": self.model,
                "keep_alive": "0"  # Força descarga do modelo
            }
            # Usar endpoint genérico do Ollama para reset
            resp = requests.post(self.host, json=reset_payload, timeout=10)
            if resp.status_code == 200:
                print(success("DeepSeek: Contexto resetado com sucesso"))
                self._performance_degraded = False
            else:
                print(warning(f"DeepSeek: Falha no reset - status {resp.status_code}"))
        except Exception as e:
            print(error(f"DeepSeek: Erro no reset do contexto: {e}"))


# -----------------------------
# Handler principal otimizado
# -----------------------------

class LLMHandler:
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, llm_type: str = "ollama"):
        self.model = model or get_current_llm_model()
        self.host = host or LLM_HOST
        self.llm_prompt = OPTIMIZED_LLM_PROMPT
        self.config = OPTIMIZED_CONFIG
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
        )

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
        
        # Redução de diff em duas camadas (Fase E2, VAL-7):
        # 1) política legada por tamanho absoluto (max_diff_chars);
        # 2) orçamento de contexto do MODELO — medido sobre o prompt real.
        original_diff_size = len(diff)
        reduced_meta = {}
        if len(diff) > _settings.max_diff_chars:
            diff, reduced_meta = reduce_diff(diff)
            if reduced_meta.get("reduced"):
                print(warning(f"Diff reduzido de {reduced_meta['original_chars']} para {reduced_meta['new_chars']} chars (arquivos truncados: {reduced_meta['truncated_files']})"))
        # Construir prompt com suporte a arquivo
        prompt, diff_file_path = build_optimized_commit_prompt_with_file_support({**commit_data, "diff": diff}, self.llm_prompt)

        # Planejar contexto para o PROMPT REAL. Se não couber no teto do
        # modelo, reduzir o diff ao orçamento e replanejar — antes o Ollama
        # descartava o excedente silenciosamente e o modelo classificava sem
        # ver o diff inteiro.
        plan = plan_generation(prompt, self.model)
        if not plan.fits:
            prompt_overhead = len(prompt) - len(diff)
            diff_budget = max(1000, plan.max_prompt_chars - prompt_overhead)
            diff, _fit_meta = reduce_diff(diff, max_chars=diff_budget)
            if len(diff) > diff_budget:
                diff = diff[:diff_budget] + "\n... (diff truncado para caber na janela de contexto)"
            prompt, diff_file_path = build_optimized_commit_prompt_with_file_support({**commit_data, "diff": diff}, self.llm_prompt)
            plan = plan_generation(prompt, self.model)
            print(warning(
                f"Diff excedia o teto de contexto do modelo — reduzido para "
                f"{len(diff)} chars (num_ctx={plan.num_ctx}); corte registrado em diff_truncated"
            ))

        # Mostrar informações sobre a estratégia usada
        if diff_file_path:
            print(info(f"Diff grande ({len(diff)} chars) - usando abordagem de arquivo: {diff_file_path}"))
        else:
            print(info(f"Diff ({len(diff)} chars) inline no prompt — num_ctx planejado: {plan.num_ctx}"))
        
        if show_prompt and DEBUG_SHOW_PROMPT:
            self.print_prompt(prompt)
        
        try:
            # Seed efetivo SEMPRE explícito e registrado (E3, REP-2): no
            # regime aleatório, o seed é sorteado no cliente e enviado — a
            # geração continua estocástica entre execuções, mas cada execução
            # passa a ser reproduzível (o Ollama sortearia internamente sem
            # registrar; distribucionalmente equivalente).
            if _settings.use_random_seed:
                seed_effective = random.SystemRandom().randint(0, 2**31 - 1)
            else:
                seed_effective = _settings.llm_seed

            # Enviar para o LLM com o plano de geração calculado
            started = time.monotonic()
            llm_response = self.adapter.complete(
                prompt,
                num_ctx=plan.num_ctx,
                num_predict=plan.num_predict,
                seed=seed_effective,
            )
            processing_time_ms = int((time.monotonic() - started) * 1000)
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
                # Rastreabilidade do envio (VAL-7/REP-2): o que foi de fato
                # usado nesta análise, registrado por resultado.
                result["original_diff_size_chars"] = original_diff_size
                result["diff_truncated"] = len(diff) < original_diff_size
                result["num_ctx_effective"] = plan.num_ctx
                result["num_predict_effective"] = plan.num_predict
                result["prompt_chars"] = len(prompt)
                result["seed_effective"] = seed_effective
                # REP-4: duração real da chamada de inferência.
                result["processing_time_ms"] = processing_time_ms
                # REP-2: hashes do que foi DE FATO enviado — auditáveis contra
                # reconstrução determinística (template versionado + git).
                result["prompt_sha256_effective"] = hashlib.sha256(prompt.encode()).hexdigest()
                result["diff_sha256"] = hashlib.sha256(diff.encode()).hexdigest()
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

    def _process_llm_response(self, llm_response: str, commit_message: str, commit_hash: str | None = None, previous_hash: str | None = None, repository: str | None = None, prompt: str | None = None) -> Optional[dict]:
        """Extrai o veredito e os campos de análise da resposta do LLM.

        Contrato (Fase E2, VAL-2/VAL-3):
        - fontes de veredito aceitas: linha ``FINAL: PURE|FLOSS`` (autoridade,
          instrução explícita do prompt) e/ou objeto JSON com
          ``refactoring_type`` válido (schema em extract_classification_json);
        - sem veredito em NENHUMA fonte -> falha registrada em json_failures
          e retorno None. Nenhuma heurística de palavras-chave fabrica rótulo;
        - ``justification``/``confidence_level``/``technical_evidence`` vêm
          exclusivamente do JSON do modelo; ausentes permanecem None — nunca
          constantes simuladas ("medium"/"") nem dados do Purity Checker
          (a antiga complementação via CSV do baseline contaminava a variável
          de forma circular);
        - ``extraction_method`` registra a proveniência do veredito:
          final_pattern | json | final_pattern+json.
        """
        if not llm_response or not llm_response.strip():
            error_msg = "Resposta vazia do LLM"
            print(error(error_msg))
            if commit_hash:
                prompt_excerpt = prompt[:2000] if prompt else None
                self.save_json_failure(commit_hash, repository or "unknown", commit_message, llm_response, error_msg, prompt_excerpt=prompt_excerpt)
            return None

        raw_response = llm_response.strip()

        final_classification = extract_final_classification(llm_response)
        json_result = extract_classification_json(llm_response)

        if not final_classification and not json_result:
            error_msg = (
                "Nenhum veredito extraível: sem linha FINAL: e sem JSON com "
                "refactoring_type válido"
            )
            print(error(error_msg))
            print(dim(f"Resposta recebida (primeiros 1000 chars): {raw_response[:1000]}"))
            if commit_hash:
                prompt_excerpt = prompt[:2000] if prompt else None
                self.save_json_failure(commit_hash, repository or "unknown", commit_message, raw_response, error_msg, prompt_excerpt=prompt_excerpt)
            return None

        result: dict = dict(json_result) if json_result else {}

        if final_classification and json_result:
            extraction_method = "final_pattern+json"
            if result.get("refactoring_type") != final_classification.lower():
                # Divergência entre as duas fontes de veredito: FINAL: é a
                # autoridade, mas a divergência fica registrada para auditoria.
                result["final_vs_json_conflict"] = True
                print(warning(
                    f"FINAL: {final_classification} diverge do JSON "
                    f"({result.get('refactoring_type')}); FINAL: prevalece."
                ))
            result["refactoring_type"] = final_classification.lower()
        elif final_classification:
            extraction_method = "final_pattern"
            result["refactoring_type"] = final_classification.lower()
        else:
            extraction_method = "json"

        result["extraction_method"] = extraction_method

        # Sinônimos comuns emitidos por alguns modelos.
        if "repository" not in result and "project" in result:
            result["repository"] = result.get("project")
        if "commit_hash_before" not in result and "commit1" in result:
            result["commit_hash_before"] = result.get("commit1")
        if "commit_hash_current" not in result and "commit2" in result:
            result["commit_hash_current"] = result.get("commit2")

        # Identificadores: metadados já conhecidos pelo chamador — preencher
        # não fabrica medição (diferente das variáveis de pesquisa abaixo).
        if not result.get("repository"):
            result["repository"] = repository or "unknown"
        if not result.get("commit_hash_before"):
            result["commit_hash_before"] = previous_hash or "unknown"
        if not result.get("commit_hash_current"):
            result["commit_hash_current"] = commit_hash or "unknown"

        # Variáveis de pesquisa: somente o que o modelo declarou (VAL-3);
        # string vazia é normalizada para None (ausência explícita).
        for research_field in ("justification", "confidence_level", "technical_evidence"):
            value = result.get(research_field)
            if value is not None and not str(value).strip():
                value = None
            result[research_field] = value

        result["commit_message"] = commit_message
        result["llm_raw_response"] = raw_response
        return result

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
            "max_direct_diff_size": self.config.get("max_direct_diff_size"),
            "use_file_for_large_diffs": self.config.get("use_file_for_large_diffs"),
            "temp_diff_dir": self.config.get("temp_diff_dir"),
            "conservative_classification": self.config.get("conservative_classification")
        }
