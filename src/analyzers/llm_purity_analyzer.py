#!/usr/bin/env python3
"""
Módulo para análise LLM específica do arquivo hashes_no_rpt_purity_with_analysis.csv
Preenche a coluna llm_analysis com análises de commits de refatoramento.
"""

import pandas as pd
import json
import os
import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import time
import sys

from src.handlers.llm_handler import LLMHandler
from src.handlers.git_handler import GitHandler
from src.handlers.data_handler import DataHandler
from src.models.commit import CommitPair, AnalysisResult
from src.models.adapters import commit_from_csv_row, analysis_from_llm_response, analysis_to_session_dict
from src.utils.colors import *

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

        # Estatísticas da sessão
        self.stats = {
            "start_time": datetime.datetime.now(),
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
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
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
            backup_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if (not self._backup_created) and os.path.exists(self.csv_file_path):
                # Nome seguro para o backup
                original_name = Path(self.csv_file_path).name
                backup_path = os.path.join(self.backup_dir, f"{original_name}.backup_{backup_timestamp}")
                df_original = pd.read_csv(self.csv_file_path)
                df_original.to_csv(backup_path, index=False)
                print(info(f"Backup criado: {backup_path}"))
                self._backup_created = True

            # Salvar arquivo atualizado (sobrescreve o CSV de trabalho)
            df.to_csv(self.csv_file_path, index=False)
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
            ok, repo_path = self.git_handler.ensure_repo_cloned(commit.repository)
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
                    # Fallback conservativo com dados parciais
                    fallback = AnalysisResult(
                        repository=commit.repository,
                        commit_hash_before=commit.commit_hash_before,
                        commit_hash_current=commit.commit_hash_current,
                        refactoring_type="floss",
                        justification=llm_result.get('justification', 'Analysis failed - insufficient data') if llm_result else 'Analysis failed - insufficient data',
                        confidence_level="low",
                        project_name=commit.project_name,
                        diff_size_chars=len(diff_content),
                        diff_lines=len(diff_content.splitlines()),
                        llm_raw_response=llm_result.get('llm_raw_response', '') if llm_result else '',
                        technical_evidence=llm_result.get('technical_evidence', '') if llm_result else '',
                        success=False,
                    )
                    result_dict = analysis_to_session_dict(fallback)
                    result_dict['purity_classification'] = purity_classification
                    print(warning(f"⚠️ Commit {hash_commit[:8]}... - LLM falhou, usando dados parciais/padrão"))
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
                    "analysis_type": analysis_type,
                    "description": description,
                    "csv_file_analyzed": self.csv_file_path,
                    "start_time": self.stats["start_time"].isoformat(),
                    "end_time": datetime.datetime.now().isoformat(),
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
                convergence = {"agree": 0, "disagree": 0}
                
                for analysis in analyses:
                    llm_class = analysis.get('llm_classification', 'UNKNOWN')
                    purity_class = analysis.get('purity_classification', 'UNKNOWN')
                    
                    # Contar classificações LLM
                    classifications[llm_class] = classifications.get(llm_class, 0) + 1
                    
                    # Análise de convergência (TRUE vs FLOSS)
                    if (purity_class == 'TRUE' and llm_class == 'TRUE') or \
                       (purity_class == 'FALSE' and llm_class == 'FALSE'):
                        convergence["agree"] += 1
                    else:
                        convergence["disagree"] += 1
                
                session_data["summary"]["classifications"] = classifications
                session_data["summary"]["convergence_analysis"] = convergence
            
            with open(self.session_log_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            print(success(f"📊 Dados detalhados salvos em: {self.session_log_file}"))
            print(info(f"   Modelo: {current_model}"))
            print(info(f"   Tipo: {analysis_type}"))
            print(info(f"   Total analisado: {len(analyses)} commits"))
            
        except Exception as e:
            print(error(f"Erro ao salvar sessão: {str(e)}"))
    
    def analyze_commits(self, 
                       max_commits: Optional[int] = None, 
                       skip_analyzed: bool = True,
                       purity_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Analisa commits e preenche a coluna llm_analysis.
        
        Args:
            max_commits: Número máximo de commits para analisar (None = todos)
            skip_analyzed: Se True, pula commits que já têm análise LLM
            purity_filter: Filtro por classificação Purity ('TRUE', 'FALSE', 'NONE', None = todos)
            
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
            analysis_df = analysis_df[
                (analysis_df['llm_analysis'].isna()) | 
                (analysis_df['llm_analysis'] == '') |
                (analysis_df['llm_analysis'] == 'None')
            ]
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
        
        # Inicializar barra de progresso
        progress_bar = ProgressBar(len(analysis_df), title="LLM Analysis")
        
        # Processar commits
        analyses_results = []
        processed_count = 0
        
        try:
            for idx, row in analysis_df.iterrows():
                processed_count += 1
                self.stats["total_processed"] += 1

                hash_commit = row['hash']
                purity_classification = row['purity_analysis']

                # Atualizar barra de progresso
                progress_bar.update(processed_count)

                # Imprimir detalhes do commit atual (em nova linha após a barra)
                print(f"{info(f'Processing:')} {hash_commit[:8]}... (Purity: {purity_classification})")

                try:
                    # Analisar commit
                    result = self._analyze_single_commit(hash_commit, purity_classification)

                    if result:
                        # Atualizar DataFrame
                        classification = result['llm_classification']
                        df.loc[df['hash'] == hash_commit, 'llm_analysis'] = classification

                        analyses_results.append(result)
                        self.stats["successful_analyses"] += 1

                        print(success(f"✅ {hash_commit[:8]}... → {classification}"))
                    else:
                        # Marcar como falha
                        df.loc[df['hash'] == hash_commit, 'llm_analysis'] = 'FAILED'
                        self.stats["failed_analyses"] += 1

                        print(error(f"❌ Failed: {hash_commit[:8]}..."))

                    # Salvar progresso IMEDIATAMENTE após cada commit para permitir
                    # interrupção segura (CTRL+C) sem perda de dados.
                    self._save_csv_data(df)
                    self._save_session_analysis(analyses_results)
                    print(dim(f"💾 Progress saved ({processed_count}/{len(analysis_df)})"))

                    # Pequena pausa entre análises
                    time.sleep(1)

                except Exception as e:
                    self.stats["processing_errors"] += 1
                    df.loc[df['hash'] == hash_commit, 'llm_analysis'] = 'ERROR'
                    print(error(f"⚠️ Error: {hash_commit[:8]}... - {str(e)}"))
                    continue
        except KeyboardInterrupt:
            # Usuário interrompeu com CTRL+C — salvar o que foi processado até agora
            print(warning('\n⚠️ Interrupção detectada (CTRL+C). Salvando progresso atual...'))
            try:
                self._save_csv_data(df)
                self._save_session_analysis(analyses_results)
                print(success('💾 Progresso salvo com sucesso após interrupção.'))
            except Exception as e:
                print(error(f"❌ Falha ao salvar progresso após interrupção: {e}"))
            return self.stats

        # Salvar resultados finais
        self._save_csv_data(df)
        self._save_session_analysis(analyses_results)
        
        # Imprimir estatísticas finais
        self._print_final_stats()
        
        return self.stats
    
    def _print_final_stats(self) -> None:
        """Imprime estatísticas finais da análise."""
        end_time = datetime.datetime.now()
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
                ])
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
