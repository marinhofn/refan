#!/usr/bin/env python3
"""
Módulo para análise LLM específica do arquivo hashes_no_rpt_purity_with_analysis.csv
Preenche a coluna llm_analysis com análises de commits de refatoramento.
"""

import pandas as pd
import hashlib
import json
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import time
import sys

from src.handlers.llm_handler import LLMHandler
from src.handlers.git_handler import GitHandler
from src.handlers.data_handler import DataHandler
from src.models.commit import CommitPair, AnalysisResult
from src.models.adapters import commit_from_csv_row, analysis_from_llm_response, analysis_to_session_dict
from src.analyzers.optimized_prompt import OPTIMIZED_LLM_PROMPT
from src.utils.persistence import SessionWriter
from src.utils.timeutils import utc_now, utc_now_iso, utc_now_stamp
from src.utils.version_info import get_tool_version
from src.utils.classification import summarize_convergence
from src.utils.hardware_info import get_hardware_info, sample_gpu_metrics
from src.utils.colors import dim, error, header, info, success, warning
from src.core.settings import settings as _settings

class ProgressBar:
    """Barra de progresso simples para análise LLM."""
    
    def __init__(self, total: int, width: int = 50, title: str = "Progress"):
        self.total = total
        self.current = 0
        self.width = width
        self.title = title
        self.start_time = time.time()
        
    def update(self, current: int = None):
        """Atualiza a barra de progresso."""
        if current is not None:
            self.current = current
        else:
            self.current += 1
            
        # Calcular porcentagem
        percentage = min(100, (self.current / self.total) * 100) if self.total > 0 else 0
        
        # Calcular tempo estimado
        elapsed_time = time.time() - self.start_time
        if self.current > 0:
            avg_time_per_item = elapsed_time / self.current
            remaining_items = self.total - self.current
            eta_seconds = avg_time_per_item * remaining_items
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "calculating..."
        
        # Criar barra visual
        filled = int(self.width * percentage / 100)
        bar = '█' * filled + '░' * (self.width - filled)
        
        # Formatar elapsed time
        elapsed_str = self._format_time(elapsed_time)
        
        # Imprimir barra
        sys.stdout.write(f'\r{self.title}: |{bar}| {percentage:.1f}% ({self.current}/{self.total}) '
                        f'Elapsed: {elapsed_str} ETA: {eta_str} \n')
        sys.stdout.flush()
        
        if self.current >= self.total:
            print()  # Nova linha ao completar
            
    def _format_time(self, seconds: float) -> str:
        """Formata tempo em formato legível."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds//60:.0f}m {seconds%60:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"

class LLMPurityAnalyzer:
    """Analisador LLM específico para preenchimento da coluna de análise de pureza."""
    
    def __init__(self, model: str | None = None, csv_file_path: str | None = None, dry_run: bool = False):
        """Inicializa o analisador LLM.

        Args:
            model: Nome do modelo LLM a usar (se None usa o atual configurado).
            csv_file_path: Caminho para o CSV a ser usado/atualizado. Se None usa o CSV global.
        """
        self.llm_handler = LLMHandler(model=model)
        self.git_handler = GitHandler()
        self.data_handler = DataHandler()
        self.dry_run = dry_run
        # Arquivos de trabalho (dependem do modelo escolhido)
        from src.core.config import get_model_paths, get_current_llm_model, ensure_model_directories
        current_model = model or get_current_llm_model()
        paths = get_model_paths(current_model)
        ensure_model_directories()
        # CSV a utilizar (se informado, usamos esse caminho; caso contrário, o CSV global)
        # Note: default master CSV is the FLOSS purity file
        self.csv_file_path = csv_file_path or "csv/floss_hashes_no_rpt_purity_with_analysis.csv"
        self.backup_dir = str(paths['ANALISES_DIR'])  # Diretório específico do modelo
        self.session_log_file = None
        self.current_model = current_model

        # Rastreabilidade (HARDENING_PLAN.md, Fase H5): hash do prompt em
        # uso e versão da ferramenta acompanham todo registro persistido,
        # fechando a cadeia de auditoria dado bruto -> resultado.
        self.prompt_sha256 = hashlib.sha256(OPTIMIZED_LLM_PROMPT.encode()).hexdigest()
        self.tool_version = get_tool_version()

        # Supabase (opcional: conecta se configurado)
        self.supabase = None
        self.command_handler = None
        if _settings.supabase_enabled:
            try:
                from src.persistence.supabase_client import SupabaseClient
                from src.runner.command_handler import CommandHandler
                self.supabase = SupabaseClient(_settings.supabase_url, _settings.supabase_service_key)
                self.command_handler = CommandHandler(self.supabase, _settings.runner_id)
                print(success("Supabase conectado para persistência cloud"))
            except Exception as e:
                print(warning(f"Supabase indisponível, usando modo local: {e}"))

        # Estatísticas da sessão
        self.stats = {
            "start_time": utc_now(),
            "total_processed": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "skipped_already_analyzed": 0,
            "processing_errors": 0
        }

        os.makedirs(self.backup_dir, exist_ok=True)
        # Flag para evitar criação de múltiplos backups durante a mesma sessão
        self._backup_created = False
        
    def _create_session_log_file(self) -> str:
        """Cria arquivo de log da sessão específico por modelo e tipo."""
        timestamp = utc_now_stamp()
        
        # Detectar tipo de análise baseado no caminho do CSV
        csv_name = Path(self.csv_file_path).name
        if "true_purity" in csv_name.lower():
            analysis_type = "TRUE_hashes"
        elif "floss" in csv_name.lower():
            analysis_type = "FLOSS_hashes"
        else:
            analysis_type = "general"
        
        # Obter modelo atual
        from src.core.config import get_current_llm_model
        current_model = get_current_llm_model().replace(':', '_')
        
        log_filename = f"{current_model}_{analysis_type}_analysis_{timestamp}.json"
        log_path = os.path.join(self.backup_dir, log_filename)
        return log_path
    
    def _load_csv_data(self) -> Optional[pd.DataFrame]:
        """Carrega os dados do CSV de análise de pureza."""
        try:
            if not os.path.exists(self.csv_file_path):
                print(error(f"Arquivo {self.csv_file_path} não encontrado."))
                return None
            
            df = pd.read_csv(self.csv_file_path)
            # Garantir que a coluna llm_analysis exista e seja string para evitar warnings
            if 'llm_analysis' not in df.columns:
                # Criar coluna com dtype string para evitar futuros warnings ao atribuir
                df['llm_analysis'] = pd.Series([''] * len(df), dtype='string')
            else:
                # Forçar dtype string (preserva valores existentes)
                try:
                    df['llm_analysis'] = df['llm_analysis'].astype('string')
                except Exception:
                    # Em casos estranhos, recriar a coluna como string
                    df['llm_analysis'] = pd.Series(df['llm_analysis'].astype(str).fillna(''), dtype='string')
            print(success(f"Carregados {len(df)} hashes do arquivo de análise."))
            return df
            
        except Exception as e:
            print(error(f"Erro ao carregar CSV: {str(e)}"))
            return None
    
    def _save_csv_data(self, df: pd.DataFrame) -> bool:
        """Salva os dados atualizados no CSV."""
        try:
            # Criar um backup apenas uma vez por sessão para evitar poluição
            # do diretório csv. O backup será armazenado no diretório do modelo
            # (self.backup_dir) para manter os arquivos de trabalho organizados.
            backup_timestamp = utc_now_stamp()
            if (not self._backup_created) and os.path.exists(self.csv_file_path):
                # Nome seguro para o backup
                original_name = Path(self.csv_file_path).name
                backup_path = os.path.join(self.backup_dir, f"{original_name}.backup_{backup_timestamp}")
                df_original = pd.read_csv(self.csv_file_path)
                df_original.to_csv(backup_path, index=False)
                print(info(f"Backup criado: {backup_path}"))
                self._backup_created = True

            # Fase E4 (ROB-1): publicação atômica sob lock — crash durante a
            # escrita não corrompe o master; concorrência não perde escrita.
            from src.utils.atomic_io import atomic_write_text, file_lock
            with file_lock(self.csv_file_path):
                atomic_write_text(self.csv_file_path, df.to_csv(index=False))
            print(success(f"Arquivo {self.csv_file_path} atualizado com sucesso."))
            return True
            
        except Exception as e:
            print(error(f"Erro ao salvar CSV: {str(e)}"))
            return False
    
    def _get_commit_data_from_refactoring_csv(self, hash_commit: str) -> Optional[CommitPair]:
        """Busca dados do commit no arquivo commits_with_refactoring.csv."""
        try:
            if not self.data_handler.load_data():
                return None

            matches = self.data_handler.data[
                self.data_handler.data['commit2'] == hash_commit
            ]

            if matches.empty:
                print(warning(f"Commit {hash_commit[:8]}... não encontrado no arquivo de refatorações."))
                return None

            return commit_from_csv_row(matches.iloc[0])

        except Exception as e:
            print(error(f"Erro ao buscar dados do commit {hash_commit[:8]}...: {str(e)}"))
            return None
    
    def _get_diff_for_commit(self, commit: CommitPair) -> Optional[tuple]:
        """Obtém o diff entre dois commits e retorna também o caminho local do repositório.

        Returns:
            tuple(diff_content, repo_path) ou None em caso de erro.
        """
        try:
            ok, repo_path = self.git_handler.ensure_repo_cloned(
                commit.repository,
                required_hashes=[commit.commit_hash_before, commit.commit_hash_current],
            )
            if not ok:
                print(error(f"Falha ao preparar repositório: {commit.repository}"))
                return None
            diff_content = self.git_handler.get_commit_diff(
                repo_path, commit.commit_hash_before, commit.commit_hash_current
            )
            if not diff_content:
                print(warning(f"Diff vazio entre commits {commit.commit_hash_before[:8]}...{commit.commit_hash_current[:8]}"))
                return None
            return diff_content, repo_path
        except Exception as e:
            print(error(f"Erro ao obter diff: {str(e)}"))
            return None
    
    def _analyze_single_commit(self, hash_commit: str, purity_classification: str) -> Optional[Dict]:
        """Analisa um único commit com a LLM."""
        try:
            print(info(f"Analisando commit {hash_commit[:8]}... (Purity: {purity_classification})"))

            commit = self._get_commit_data_from_refactoring_csv(hash_commit)
            if not commit:
                return None

            # Dry-run: não realiza chamadas git/LLM
            if self.dry_run:
                print(dim(f"Dry-run ativado: simulando análise para {hash_commit[:8]}..."))
                dry_result = AnalysisResult(
                    repository=commit.repository,
                    commit_hash_before=commit.commit_hash_before,
                    commit_hash_current=commit.commit_hash_current,
                    refactoring_type="DRY_RUN",
                    justification="Dry run - análise simulada (nenhuma chamada LLM foi realizada).",
                    confidence_level="0",
                    project_name=commit.project_name,
                    llm_raw_response="DRY_RUN - No LLM call made",
                    technical_evidence="DRY_RUN - No analysis performed",
                    diff_source="dry_run",
                    success=True,
                )
                result_dict = analysis_to_session_dict(dry_result)
                result_dict['purity_classification'] = purity_classification
                print(success(f"✅ Commit {hash_commit[:8]}... simuladamente analisado: DRY_RUN"))
                return result_dict

            # Obter diff
            diff_result = self._get_diff_for_commit(commit)
            if not diff_result:
                return None
            diff_content, repo_path = diff_result

            # Obter mensagem do commit
            try:
                commit.commit_message = self.git_handler.get_commit_message(
                    repo_path, commit.commit_hash_current
                ) or "Commit message not available"
            except Exception:
                commit.commit_message = "Commit message not available"

            # Análise com LLM
            try:
                llm_result = self.llm_handler.analyze_commit_refactoring(
                    current_hash=hash_commit,
                    previous_hash=commit.commit_hash_before,
                    repository=commit.repository,
                    diff_content=diff_content,
                    commit_message=commit.commit_message,
                    repo_path=repo_path,
                )

                if llm_result and llm_result.get('success') and llm_result.get('refactoring_type'):
                    analysis = analysis_from_llm_response(llm_result, commit)
                    analysis.diff_size_chars = len(diff_content)
                    analysis.diff_lines = len(diff_content.splitlines())
                    result_dict = analysis_to_session_dict(analysis)
                    result_dict['purity_classification'] = purity_classification
                    print(success(f"✅ Commit {hash_commit[:8]}... analisado: {analysis.refactoring_type.upper()}"))
                    return result_dict
                else:
                    # Falha honesta (Fase E2, VAL-2/VAL-6): sem veredito do
                    # modelo o registro é FAILED — nas séries <= v2.1 este
                    # caminho fabricava um rótulo 'floss' com confidence 'low',
                    # indistinguível de uma medição real no CSV/JSONL.
                    failure = AnalysisResult(
                        repository=commit.repository,
                        commit_hash_before=commit.commit_hash_before,
                        commit_hash_current=commit.commit_hash_current,
                        refactoring_type="FAILED",
                        justification=None,
                        confidence_level=None,
                        technical_evidence=None,
                        project_name=commit.project_name,
                        diff_size_chars=len(diff_content),
                        diff_lines=len(diff_content.splitlines()),
                        llm_raw_response=(llm_result or {}).get('llm_raw_response', '') or '',
                        extraction_method="none",
                        success=False,
                    )
                    result_dict = analysis_to_session_dict(failure)
                    result_dict['purity_classification'] = purity_classification
                    result_dict['error_type'] = 'llm_no_verdict'
                    result_dict['error_message'] = (llm_result or {}).get(
                        'error', 'Resposta do LLM sem veredito extraível'
                    )
                    print(warning(f"⚠️ Commit {hash_commit[:8]}... sem veredito do LLM — registrado como FAILED"))
                    return result_dict

            except Exception as llm_error:
                print(error(f"❌ Erro na chamada LLM para {hash_commit[:8]}...: {str(llm_error)}"))
                return None

        except Exception as e:
            print(error(f"Erro na análise do commit {hash_commit[:8]}...: {str(e)}"))
            return None
    
    def _save_session_analysis(self, analyses: List[Dict]) -> None:
        """Salva análises da sessão em arquivo JSON com dados detalhados."""
        try:
            if not self.session_log_file:
                self.session_log_file = self._create_session_log_file()
            
            # Detectar tipo de análise
            csv_name = Path(self.csv_file_path).name
            if "true_purity" in csv_name.lower():
                analysis_type = "TRUE_hashes"
                description = "Análise de hashes com classificação Purity=TRUE"
            elif "floss" in csv_name.lower():
                analysis_type = "FLOSS_hashes"
                description = "Análise de hashes com classificação Purity=FALSE (FLOSS)"
            else:
                analysis_type = "general"
                description = "Análise geral de hashes"
            
            # Obter modelo atual
            from src.core.config import get_current_llm_model
            current_model = get_current_llm_model()
            
            session_data = {
                "session_info": {
                    "model_used": current_model,
                    "model_digest": getattr(self, "model_digest", ""),
                    "ollama_version": getattr(self, "ollama_version", ""),
                    "analysis_type": analysis_type,
                    "description": description,
                    "csv_file_analyzed": self.csv_file_path,
                    "prompt_sha256": self.prompt_sha256,
                    "tool_version": self.tool_version,
                    "config_snapshot": _settings.to_dict(),
                    "start_time": self.stats["start_time"].isoformat(),
                    "end_time": utc_now_iso(),
                    "total_processed": self.stats["total_processed"],
                    "successful_analyses": self.stats["successful_analyses"],
                    "failed_analyses": self.stats["failed_analyses"],
                    "skipped_already_analyzed": self.stats["skipped_already_analyzed"],
                    "processing_errors": self.stats["processing_errors"]
                },
                "detailed_analyses": analyses,
                "summary": {
                    "total_commits": len(analyses),
                    "classifications": {},
                    "convergence_analysis": {}
                }
            }
            
            # Adicionar estatísticas de classificações
            if analyses:
                classifications = {}
                
                for analysis in analyses:
                    llm_class = analysis.get('llm_classification', 'UNKNOWN')
                    # Contar classificações LLM
                    classifications[llm_class] = classifications.get(llm_class, 0) + 1

                # Convergência Purity × LLM pela fonte única (TRUE↔PURE,
                # FALSE↔FLOSS; sem veredito → not_comparable). Correção do
                # defeito VAL-1 (EVOLUTION_PLAN.md): a comparação anterior
                # usava os literais 'TRUE'/'FALSE' contra PURE/FLOSS e
                # reportava 0 concordâncias em toda sessão.
                convergence = summarize_convergence(
                    (a.get('purity_classification'), a.get('llm_classification'))
                    for a in analyses
                )

                session_data["summary"]["classifications"] = classifications
                session_data["summary"]["convergence_analysis"] = convergence
            
            from src.utils.atomic_io import atomic_write_json
            atomic_write_json(self.session_log_file, session_data)
            
            print(success(f"📊 Dados detalhados salvos em: {self.session_log_file}"))
            print(info(f"   Modelo: {current_model}"))
            print(info(f"   Tipo: {analysis_type}"))
            print(info(f"   Total analisado: {len(analyses)} commits"))
            
        except Exception as e:
            print(error(f"Erro ao salvar sessão: {str(e)}"))
    
    def analyze_commits(self, 
                       max_commits: Optional[int] = None, 
                       skip_analyzed: bool = True,
                       purity_filter: Optional[str] = None,
                       retry_failed: bool = False) -> Dict[str, Any]:
        """
        Analisa commits e preenche a coluna llm_analysis.
        
        Args:
            max_commits: Número máximo de commits para analisar (None = todos)
            skip_analyzed: Se True, pula commits que já têm análise LLM
            purity_filter: Filtro por classificação Purity ('TRUE', 'FALSE', 'NONE', None = todos)
            retry_failed: Se True, reanalisa commits marcados FAILED/ERROR
                (Fase E2, VAL-6 — antes ficavam em limbo permanente: nem
                pendentes, nem completos, nunca reanalisados)
            
        Returns:
            Dict com estatísticas da análise
        """
        print(header(f"\n{'='*60}"))
        print(header("INICIANDO ANÁLISE LLM DE COMMITS DE REFATORAMENTO"))
        print(header(f"{'='*60}"))
        
        # Carregar dados do CSV
        df = self._load_csv_data()
        if df is None:
            return self.stats
        
        # Aplicar filtros
        analysis_df = df.copy()
        
        # Filtrar por classificação Purity se especificado
        if purity_filter:
            initial_count = len(analysis_df)
            analysis_df = analysis_df[analysis_df['purity_analysis'] == purity_filter]
            print(info(f"Filtro Purity '{purity_filter}': {len(analysis_df)} de {initial_count} commits"))
        
        # Pular commits já analisados se solicitado
        if skip_analyzed:
            initial_count = len(analysis_df)
            pending_mask = (
                (analysis_df['llm_analysis'].isna()) | 
                (analysis_df['llm_analysis'] == '') |
                (analysis_df['llm_analysis'] == 'None')
            )
            if retry_failed:
                pending_mask |= analysis_df['llm_analysis'].isin(['FAILED', 'ERROR'])
            analysis_df = analysis_df[pending_mask]
            skipped = initial_count - len(analysis_df)
            self.stats["skipped_already_analyzed"] = skipped
            print(info(f"Pulando {skipped} commits já analisados. Restam {len(analysis_df)} para análise."))
        
        # Limitar número de commits se especificado
        if max_commits and max_commits > 0:
            analysis_df = analysis_df.head(max_commits)
            print(info(f"Limitando análise a {len(analysis_df)} commits."))
        
        if len(analysis_df) == 0:
            print(warning("Nenhum commit para analisar após aplicação dos filtros."))
            return self.stats
        
        print(info(f"Iniciando análise de {len(analysis_df)} commits..."))
        
        # Identidade exata do modelo (Fase E3, REP-1): sem digest não há
        # rastreabilidade — a sessão real é ABORTADA. Dry-run é isento
        # (não é medição; roda offline).
        self.model_digest = ""
        self.ollama_version = ""
        model_info = None
        if not self.dry_run:
            model_info = self.llm_handler.get_model_info()
            if not model_info or not model_info.get("digest"):
                raise RuntimeError(
                    f"Não foi possível obter o digest do modelo '{self.current_model}' "
                    f"no Ollama local. Sem o digest, os resultados não são "
                    f"reprodutíveis nem auditáveis (REP-1). Verifique se o Ollama "
                    f"está ativo e o modelo foi baixado (ollama pull)."
                )
            self.model_digest = model_info["digest"]
            self.ollama_version = model_info.get("ollama_version", "")
            print(info(f"Modelo {self.current_model} digest {self.model_digest[:19]}... (Ollama {self.ollama_version or '?'})"))

        # Inicializar barra de progresso
        progress_bar = ProgressBar(len(analysis_df), title="LLM Analysis")
        
        # Inicializar persistência incremental (JSONL append-only)
        sessions_dir = os.path.join(self.backup_dir, "sessions")
        session_writer = SessionWriter(sessions_dir)
        analyses_results = []
        processed_count = 0

        # Inicializar sessão Supabase (se conectado)
        cloud_session_id = None
        cloud_model_id = None
        cloud_prompt_id = None
        # Dry-run nunca toca o cloud: além de não ser medição, 'DRY_RUN'
        # violaria o CHECK de classification do schema.
        if self.supabase and not self.dry_run:
            from src.persistence.supabase_client import PromptVersionConflictError
            try:
                cloud_model_id = self.supabase.get_or_create_model(
                    self.current_model,
                    digest=self.model_digest,
                    ollama_version=self.ollama_version,
                )

                # Proveniência imutável (Fase E2, VAL-4): se a tag registrada
                # no banco tem hash diferente do prompt em execução,
                # get_or_create_prompt_version levanta conflito e a sessão é
                # ABORTADA — a política anterior (H5) avisava e prosseguia,
                # sobrescrevendo o registro histórico via upsert.
                cloud_prompt_id = self.supabase.get_or_create_prompt_version(
                    _settings.prompt_version_tag, OPTIMIZED_LLM_PROMPT
                )
                if cloud_model_id and cloud_prompt_id:
                    cloud_session_id = self.supabase.start_session(
                        model_id=cloud_model_id,
                        prompt_version_id=cloud_prompt_id,
                        config_snapshot={
                            **_settings.to_dict(),
                            "prompt_sha256": self.prompt_sha256,
                            "tool_version": self.tool_version,
                            "model_digest": self.model_digest,
                            "model_modified_at": (model_info or {}).get("modified_at", ""),
                            "ollama_version": self.ollama_version,
                            "hardware": get_hardware_info(),
                        },
                        runner_hostname=_settings.runner_id,
                        total_planned=len(analysis_df),
                        purity_filter=purity_filter,
                    )
                    if cloud_session_id:
                        print(info(f"Sessão Supabase criada: {cloud_session_id[:8]}..."))
            except PromptVersionConflictError as e:
                print(error(f"Sessão abortada — conflito de versão de prompt: {e}"))
                raise
            except Exception as e:
                print(warning(f"Falha ao criar sessão Supabase: {e}"))

        try:
            for idx, row in analysis_df.iterrows():
                # Controle remoto: verificar comandos pendentes
                if self.command_handler:
                    from src.runner.command_handler import AnalysisCancelled
                    try:
                        self.command_handler.poll_and_execute()
                        self.command_handler.wait_if_paused()
                    except AnalysisCancelled:
                        print(warning("Análise cancelada via comando remoto"))
                        break

                processed_count += 1
                self.stats["total_processed"] += 1

                hash_commit = row['hash']
                purity_classification = row['purity_analysis']

                # Controle remoto: verificar skip list
                if self.command_handler and self.command_handler.should_skip(hash_commit):
                    print(dim(f"⏭️ Skip (remoto): {hash_commit[:8]}..."))
                    self.stats["skipped_already_analyzed"] += 1
                    continue

                # Controle remoto (ROB-5): reanálises agendadas via dashboard
                # entram na frente da fila desta sessão (antes: comando aceito
                # e jamais consumido).
                if self.command_handler:
                    for queued_hash in self.command_handler.drain_reanalyze_queue():
                        in_master = df['hash'] == queued_hash
                        if not in_master.any():
                            print(warning(f"Reanálise remota ignorada: {queued_hash[:8]}... não está no master"))
                            continue
                        queued_purity = df.loc[in_master, 'purity_analysis'].iloc[0]
                        print(info(f"Reanálise remota: {queued_hash[:8]}..."))
                        requeued = self._analyze_single_commit(queued_hash, queued_purity)
                        if requeued:
                            requeued["prompt_sha256"] = self.prompt_sha256
                            requeued["tool_version"] = self.tool_version
                            requeued["model_digest"] = self.model_digest
                            requeued["ollama_version"] = self.ollama_version
                            requeued["reanalyzed_via_remote_command"] = True
                            analyses_results.append(requeued)
                            session_writer.append(requeued)
                            if not self.dry_run:
                                df.loc[in_master, 'llm_analysis'] = requeued['llm_classification']

                progress_bar.update(processed_count)
                print(f"{info(f'Processing:')} {hash_commit[:8]}... (Purity: {purity_classification})")

                try:
                    result = self._analyze_single_commit(hash_commit, purity_classification)

                    if result:
                        classification = result['llm_classification']
                        has_verdict = classification in ("PURE", "FLOSS")
                        # Dry-run é simulação: o CSV master nunca é mutado
                        # (Fase E2 — um dry-run chegou a gravar 'DRY_RUN' no
                        # master rastreado em jul/2026).
                        if not self.dry_run:
                            df.loc[df['hash'] == hash_commit, 'llm_analysis'] = classification
                        # Rastreabilidade: todo registro persistido carrega o
                        # hash do prompt e a versão da ferramenta que o gerou.
                        result["prompt_sha256"] = self.prompt_sha256
                        result["tool_version"] = self.tool_version
                        result["model_digest"] = self.model_digest
                        result["ollama_version"] = self.ollama_version
                        analyses_results.append(result)
                        if has_verdict:
                            self.stats["successful_analyses"] += 1
                        elif classification == "FAILED":
                            # Falha com registro completo (VAL-6): conta como
                            # falha, é persistida em JSONL e reportada ao cloud.
                            self.stats["failed_analyses"] += 1

                        # Persistência local: JSONL append (O(1), crash-safe)
                        session_writer.append(result)

                        # Persistência cloud: Supabase (se conectado)
                        if self.supabase and cloud_session_id:
                            try:
                                commit_id = self.supabase.upsert_commit(
                                    commit_hash_current=hash_commit,
                                    commit_hash_before=result.get("commit_hash_before", ""),
                                    repository_url=result.get("repository", ""),
                                    project_name=result.get("project_name", ""),
                                    purity_analysis=purity_classification,
                                )
                                if commit_id and has_verdict:
                                    self.supabase.record_result(
                                        session_id=cloud_session_id,
                                        commit_id=commit_id,
                                        model_id=cloud_model_id,
                                        prompt_version_id=cloud_prompt_id,
                                        classification=classification,
                                        justification=result.get("llm_justification") or "",
                                        confidence_level=result.get("llm_confidence") or "",
                                        technical_evidence=result.get("technical_evidence") or "",
                                        llm_raw_response=result.get("llm_raw_response", ""),
                                        extraction_method=result.get("extraction_method", ""),
                                        diff_source=result.get("diff_source", "direct"),
                                        diff_size_chars=result.get("diff_size", 0),
                                        diff_lines=result.get("diff_lines", 0),
                                        processing_time_ms=result.get("processing_time_ms", 0),
                                    )
                                elif classification == "FAILED":
                                    # Falhas são dados (VAL-6): antes nenhuma
                                    # falha chegava ao cloud (record_failure
                                    # não tinha callers).
                                    self.supabase.record_failure(
                                        session_id=cloud_session_id,
                                        commit_id=commit_id,
                                        model_id=cloud_model_id,
                                        error_type=result.get('error_type', 'llm_no_verdict'),
                                        error_message=result.get('error_message', ''),
                                        llm_raw_response=result.get('llm_raw_response', '') or '',
                                    )
                                # Heartbeat (com métricas de GPU quando NVIDIA)
                                gpu_pct, gpu_mem = sample_gpu_metrics()
                                self.supabase.update_heartbeat(
                                    runner_id=_settings.runner_id,
                                    session_id=cloud_session_id,
                                    status="running",
                                    current_commit_hash=hash_commit,
                                    current_commit_index=processed_count,
                                    total_commits_in_batch=len(analysis_df),
                                    model_name=self.current_model,
                                    gpu_utilization_pct=gpu_pct,
                                    memory_used_mb=gpu_mem,
                                )
                            except Exception as e:
                                print(dim(f"Supabase sync falhou (JSONL local OK): {e}"))

                        icon = "✅" if has_verdict else "⚠️"
                        print(success(f"{icon} {hash_commit[:8]}... → {classification}"))
                    else:
                        # Abortada antes de qualquer resposta (diff/dados
                        # indisponíveis): marca ERROR no master e reporta ao
                        # cloud sem commit_id.
                        if not self.dry_run:
                            df.loc[df['hash'] == hash_commit, 'llm_analysis'] = 'FAILED'
                        self.stats["failed_analyses"] += 1
                        if self.supabase and cloud_session_id:
                            try:
                                self.supabase.record_failure(
                                    session_id=cloud_session_id,
                                    commit_id=None,
                                    model_id=cloud_model_id,
                                    error_type='analysis_error',
                                    error_message=f'Análise abortada para {hash_commit} (diff/dados indisponíveis)',
                                )
                            except Exception as e:
                                print(dim(f"Supabase record_failure falhou: {e}"))
                        print(error(f"❌ Failed: {hash_commit[:8]}..."))

                    # Mensagem honesta (ROB-1): o que está salvo neste ponto é
                    # o JSONL incremental; o CSV master é escrito ao final.
                    print(dim(f"Registro em JSONL ({processed_count}/{len(analysis_df)}); CSV master é escrito ao final"))
                    time.sleep(1)

                except Exception as e:
                    self.stats["processing_errors"] += 1
                    if not self.dry_run:
                        df.loc[df['hash'] == hash_commit, 'llm_analysis'] = 'ERROR'
                    print(error(f"⚠️ Error: {hash_commit[:8]}... - {str(e)}"))
                    continue

        except KeyboardInterrupt:
            print(warning('\n⚠️ Interrupção detectada (CTRL+C). Salvando progresso atual...'))

        # Salvar CSV e sessão JSON uma vez no final (ou após CTRL+C)
        try:
            if self.dry_run:
                print(info("Dry-run: CSV master preservado (nenhuma mutação)."))
            else:
                self._save_csv_data(df)
            self._save_session_analysis(analyses_results)
            print(success(f'💾 Progresso final salvo. JSONL: {session_writer.path} ({session_writer.count} registros)'))
        except Exception as e:
            print(error(f"❌ Falha ao salvar progresso: {e}"))
            return self.stats

        # Finalizar sessão Supabase
        if self.supabase and cloud_session_id:
            try:
                self.supabase.update_session_status(
                    session_id=cloud_session_id,
                    status="completed",
                    total_completed=self.stats["successful_analyses"],
                    total_failed=self.stats["failed_analyses"],
                    total_skipped=self.stats["skipped_already_analyzed"],
                )
                # ROB-6: sem o refresh a view model_metrics nunca refletia
                # as sessões — AVG(processing_time_ms) e contagens paradas.
                self.supabase.refresh_model_metrics()
                self.supabase.update_heartbeat(
                    runner_id=_settings.runner_id,
                    status="idle",
                )
                print(success("Sessão Supabase finalizada"))
            except Exception as e:
                print(warning(f"Falha ao finalizar sessão Supabase: {e}"))

        # Imprimir estatísticas finais
        self._print_final_stats()
        
        return self.stats
    
    def _print_final_stats(self) -> None:
        """Imprime estatísticas finais da análise."""
        end_time = utc_now()
        duration = end_time - self.stats["start_time"]
        
        print(f"\n{header('='*60)}")
        print(header("ESTATÍSTICAS FINAIS DA ANÁLISE"))
        print(header(f"{'='*60}"))
        
        print(f"{info('Tempo de execução:')} {duration}")
        print(f"{info('Total processado:')} {self.stats['total_processed']}")
        print(f"{success('Análises bem-sucedidas:')} {self.stats['successful_analyses']}")
        print(f"{error('Análises falharam:')} {self.stats['failed_analyses']}")
        print(f"{warning('Já analisados (pulados):')} {self.stats['skipped_already_analyzed']}")
        print(f"{error('Erros de processamento:')} {self.stats['processing_errors']}")
        
        if self.stats['total_processed'] > 0:
            success_rate = (self.stats['successful_analyses'] / self.stats['total_processed']) * 100
            print(f"{info('Taxa de sucesso:')} {success_rate:.1f}%")
        
        if self.session_log_file:
            print(f"{info('Log da sessão:')} {self.session_log_file}")
    
    def get_analysis_summary(self) -> Optional[Dict]:
        """Retorna resumo das análises realizadas."""
        try:
            df = self._load_csv_data()
            if df is None:
                return None
            
            # Estatísticas por categoria
            purity_counts = df['purity_analysis'].value_counts()
            llm_counts = df['llm_analysis'].value_counts()
            
            # Análise cruzada
            cross_analysis = pd.crosstab(df['purity_analysis'], df['llm_analysis'], margins=True)
            
            summary = {
                "total_hashes": len(df),
                "purity_distribution": purity_counts.to_dict(),
                "llm_distribution": llm_counts.to_dict(),
                "cross_analysis": cross_analysis.to_dict(),
                "completed_analyses": len(df[
                    (df['llm_analysis'].notna()) & 
                    (df['llm_analysis'] != '') & 
                    (~df['llm_analysis'].isin(['FAILED', 'ERROR']))
                ]),
                "pending_analyses": len(df[
                    (df['llm_analysis'].isna()) | 
                    (df['llm_analysis'] == '') |
                    (df['llm_analysis'] == 'None')
                ]),
                # VAL-6: FAILED/ERROR eram invisíveis (nem completos nem
                # pendentes); agora são contados e reanalisáveis via
                # --retry-failed.
                "failed_analyses": len(df[df['llm_analysis'].isin(['FAILED', 'ERROR'])])
            }
            
            return summary
            
        except Exception as e:
            print(error(f"Erro ao gerar resumo: {str(e)}"))
            return None


def main():
    """Função principal para execução standalone."""
    analyzer = LLMPurityAnalyzer()
    
    # Exemplo de uso
    print("LLM Purity Analyzer - Opções:")
    print("1. Analisar primeiros N commits")
    print("2. Analisar todos os commits")
    print("3. Analisar apenas commits FALSE do Purity")
    print("4. Analisar apenas commits TRUE do Purity")
    print("5. Resumo das análises existentes")
    
    try:
        choice = input("Escolha uma opção (1-5): ").strip()
        
        if choice == "1":
            n = int(input("Quantos commits analisar? "))
            analyzer.analyze_commits(max_commits=n)
        elif choice == "2":
            analyzer.analyze_commits()
        elif choice == "3":
            analyzer.analyze_commits(purity_filter="FALSE")
        elif choice == "4":
            analyzer.analyze_commits(purity_filter="TRUE")
        elif choice == "5":
            summary = analyzer.get_analysis_summary()
            if summary:
                print(json.dumps(summary, indent=2))
        else:
            print("Opção inválida.")
    
    except KeyboardInterrupt:
        print("\n\nAnálise interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro: {str(e)}")


if __name__ == "__main__":
    main()
