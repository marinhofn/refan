"""
Módulo responsável por carregar e processar dados da ferramenta Purity e compará-los
com as análises LLM existentes.
"""

import os
import json
import pandas as pd
import datetime
from src.core.config import PURITY_CSV_PATH, PURITY_COMPARISON_DIR, get_model_paths, get_current_llm_model
from src.utils.colors import *

class PurityHandler:
    def __init__(self):
        """Inicializa o manipulador de dados do Purity."""
        self.purity_data = None
        self.floss_commits = None
        
    def load_purity_data(self):
        """
        Carrega os dados do CSV do PurityChecker.
        
        Returns:
            bool: True se o carregamento foi bem-sucedido, False caso contrário.
        """
        try:
            if not os.path.exists(PURITY_CSV_PATH):
                print(error(f"Erro: O arquivo {PURITY_CSV_PATH} não foi encontrado."))
                return False
                
            # Carregar dados brutos
            raw_data = pd.read_csv(PURITY_CSV_PATH, delimiter=';')
            print(success(f"Dados brutos do Purity carregados. Total de {len(raw_data)} registros."))
            
            # Limpar e validar dados
            self.purity_data = self._clean_and_validate_data(raw_data)
            print(success(f"Dados do Purity processados. Total de {len(self.purity_data)} registros válidos."))
            return True
        except Exception as e:
            print(error(f"Erro ao carregar os dados do Purity: {str(e)}"))
            return False
    
    def _clean_and_validate_data(self, raw_data):
        """
        Limpa e valida os dados do CSV, lidando com duplicatas e valores inconsistentes.
        
        Args:
            raw_data (pd.DataFrame): Dados brutos do CSV
            
        Returns:
            pd.DataFrame: Dados limpos e validados
        """
        try:
            print(progress("Limpando e validando dados do Purity..."))
            
            # Remover linhas onde o commit é None ou vazio
            valid_data = raw_data[
                raw_data['commit'].notna() & 
                (raw_data['commit'] != '') &
                (raw_data['commit'].str.len() >= 7)  # Hash mínimo
            ].copy()
            
            print(info(f"Removidas {len(raw_data) - len(valid_data)} linhas com commits inválidos"))
            
            # Separar registros com purity definida vs None
            with_purity = valid_data[valid_data['purity'].notna()].copy()
            without_purity = valid_data[valid_data['purity'].isna()].copy()
            
            print(info(f"Registros com classificação Purity: {len(with_purity)}"))
            print(info(f"Registros sem classificação Purity: {len(without_purity)}"))
            
            # Resolver duplicatas com classificações diferentes
            if len(with_purity) > 0:
                cleaned_purity = self._resolve_duplicate_classifications(with_purity)
            else:
                cleaned_purity = with_purity
            
            # Combinar dados limpos com registros sem classificação
            # Manter apenas um registro por commit para os sem classificação
            if len(without_purity) > 0:
                unique_without_purity = without_purity.drop_duplicates(subset=['commit'], keep='first')
                print(info(f"Mantidos {len(unique_without_purity)} registros únicos sem classificação"))
                final_data = pd.concat([cleaned_purity, unique_without_purity], ignore_index=True)
            else:
                final_data = cleaned_purity
            
            print(success(f"Limpeza concluída. {len(final_data)} registros finais"))
            return final_data
            
        except Exception as e:
            print(error(f"Erro durante limpeza dos dados: {str(e)}"))
            return raw_data  # Retorna dados originais em caso de erro
    
    def _resolve_duplicate_classifications(self, data_with_purity):
        """
        Resolve duplicatas onde o mesmo commit tem classificações diferentes.
        
        Args:
            data_with_purity (pd.DataFrame): Dados com classificação purity definida
            
        Returns:
            pd.DataFrame: Dados com duplicatas resolvidas
        """
        print(progress("Resolvendo duplicatas de classificação..."))
        
        # Agrupar por commit e verificar inconsistências
        grouped = data_with_purity.groupby('commit')
        resolved_data = []
        
        inconsistent_commits = 0
        total_commits = len(grouped)
        
        for commit_hash, group in grouped:
            unique_purities = group['purity'].unique()
            
            if len(unique_purities) == 1:
                # Sem conflito - manter o primeiro registro de cada tipo de refactoring
                resolved_data.append(self._consolidate_single_commit(group))
            else:
                # Conflito de classificação
                inconsistent_commits += 1
                if inconsistent_commits <= 5:  # Log apenas os primeiros 5
                    print(warning(f"Commit {commit_hash} tem classificações conflitantes: {unique_purities.tolist()}"))
                
                # Estratégia de resolução: priorizar False (floss) sobre True (pure)
                # Assumindo que se há conflito, é mais seguro classificar como floss
                resolved_record = self._resolve_classification_conflict(group)
                resolved_data.append(resolved_record)
        
        if inconsistent_commits > 5:
            print(warning(f"... e mais {inconsistent_commits - 5} commits com classificações conflitantes"))
        
        print(info(f"Resolvidos {inconsistent_commits}/{total_commits} commits com classificações conflitantes"))
        
        return pd.DataFrame(resolved_data)
    
    def _consolidate_single_commit(self, group):
        """
        Consolida múltiplos registros do mesmo commit com a mesma classificação.
        
        Args:
            group (pd.DataFrame): Grupo de registros do mesmo commit
            
        Returns:
            dict: Registro consolidado
        """
        # Pegar o primeiro registro como base
        base_record = group.iloc[0].to_dict()
        
        # Consolidar descrições de refatoramento se houver múltiplas
        refactoring_descriptions = []
        refactoring_types = []
        
        for _, row in group.iterrows():
            if pd.notna(row['refactoring_description']) and row['refactoring_description'] not in refactoring_descriptions:
                refactoring_descriptions.append(str(row['refactoring_description']))
            if pd.notna(row['refactoring_type']) and row['refactoring_type'] not in refactoring_types:
                refactoring_types.append(str(row['refactoring_type']))
        
        # Combinar descrições
        if refactoring_descriptions:
            base_record['refactoring_description'] = ' | '.join(refactoring_descriptions)
        if refactoring_types:
            base_record['refactoring_type'] = ' | '.join(refactoring_types)
        
        return base_record
    
    def _resolve_classification_conflict(self, group):
        """
        Resolve conflito quando o mesmo commit tem classificações True e False.
        
        Args:
            group (pd.DataFrame): Grupo de registros conflitantes
            
        Returns:
            dict: Registro com classificação resolvida
        """
        # Estratégia: Se há qualquer classificação False (floss), usar False
        # Isso é conservativo - assume que refatoramento impuro é mais provável
        
        has_false = False in group['purity'].values
        has_true = True in group['purity'].values
        
        if has_false:
            # Priorizar registros com purity=False
            false_records = group[group['purity'] == False]
            base_record = false_records.iloc[0].to_dict()
            final_classification = False
        else:
            # Apenas registros True
            base_record = group.iloc[0].to_dict()
            final_classification = True
        
        # Adicionar informação sobre o conflito na descrição
        base_record['purity'] = final_classification
        
        # Consolidar todas as descrições para mostrar a complexidade
        all_descriptions = []
        for _, row in group.iterrows():
            if pd.notna(row['refactoring_description']):
                desc = f"[{row['purity']}] {row['refactoring_description']}"
                if desc not in all_descriptions:
                    all_descriptions.append(desc)
        
        if all_descriptions:
            base_record['refactoring_description'] = ' | '.join(all_descriptions)
        
        # Adicionar flag indicando que houve conflito
        base_record['had_classification_conflict'] = True
        
        return base_record
    
    def get_floss_commits(self, limit=None):
        """
        Extrai commits que foram classificados como 'false' (floss) pelo Purity.
        
        Args:
            limit (int, optional): Número máximo de commits únicos a retornar. Se None, retorna todos.
        
        Returns:
            bool: True se a extração foi bem-sucedida, False caso contrário.
        """
        if self.purity_data is None:
            print(error("Erro: Dados do Purity não foram carregados. Execute load_purity_data() primeiro."))
            return False
        
        try:
            # Filtrar apenas registros onde purity == false
            floss_data = self.purity_data[self.purity_data['purity'] == False].copy()
            
            if len(floss_data) == 0:
                print(warning("Nenhum commit classificado como 'floss' encontrado."))
                return False
            
            # Obter commits únicos
            unique_commits = floss_data['commit'].unique()
            
            # Aplicar limite se especificado
            if limit is not None and limit > 0:
                self.floss_commits = unique_commits[:limit]
                print(success(f"Selecionados os primeiros {len(self.floss_commits)} commits únicos classificados como 'floss' pelo Purity (limite: {limit})."))
            else:
                self.floss_commits = unique_commits
                print(success(f"Encontrados {len(self.floss_commits)} commits únicos classificados como 'floss' pelo Purity."))
            
            return True
        except Exception as e:
            print(error(f"Erro ao extrair commits floss: {str(e)}"))
            return False
    
    def get_floss_commits_list(self):
        """
        Retorna a lista de commits classificados como floss pelo Purity.
        
        Returns:
            list: Lista de hashes de commits ou None se não disponível.
        """
        if self.floss_commits is None:
            return None
        return self.floss_commits.tolist()
    
    def create_comparison_dataframe(self, floss_commits_list, llm_analysis_results):
        """
        Cria um DataFrame comparando os resultados do Purity com os resultados LLM.
        
        Args:
            floss_commits_list (list): Lista de commits classificados como floss pelo Purity.
            llm_analysis_results (list): Lista de análises LLM.
            
        Returns:
            pd.DataFrame: DataFrame com a comparação.
        """
        try:
            comparison_data = []
            
            # Criar um dicionário para acesso rápido às análises LLM
            llm_results_dict = {item['commit_hash_current']: item for item in llm_analysis_results}
            
            for commit_hash in floss_commits_list:
                row = {
                    'commit_hash': commit_hash,
                    'purity_classification': 'floss',
                    'llm_classification': 'not_analyzed',
                    'llm_justification': 'Commit not analyzed by LLM',
                    'agreement': False,
                    'repository': '',
                    'commit_message': ''
                }
                
                # Verificar se existe análise LLM para este commit
                if commit_hash in llm_results_dict:
                    llm_result = llm_results_dict[commit_hash]
                    row['llm_classification'] = llm_result['refactoring_type']
                    row['llm_justification'] = llm_result['justification']
                    row['repository'] = llm_result['repository']
                    row['commit_message'] = llm_result['commit_message']
                    
                    # Verificar se há concordância (ambos classificaram como floss)
                    row['agreement'] = llm_result['refactoring_type'] == 'floss'
                
                comparison_data.append(row)
            
            return pd.DataFrame(comparison_data)
        except Exception as e:
            print(error(f"Erro ao criar DataFrame de comparação: {str(e)}"))
            return None
    
    def load_all_llm_analyses(self):
        """
        Carrega todas as análises LLM existentes dos arquivos JSON.
        
        Returns:
            list: Lista com todas as análises LLM ou lista vazia em caso de erro.
        """
        try:
            all_analyses = []
            
            paths = get_model_paths(get_current_llm_model())
            analyses_dir = str(paths['ANALISES_DIR'])
            if not os.path.exists(analyses_dir):
                print(warning(f"Diretório {analyses_dir} não encontrado."))
                return []
            
            # Listar todos os arquivos JSON de análise
            analysis_files = [f for f in os.listdir(analyses_dir) if f.startswith('analise_') and f.endswith('.json')]
            
            if not analysis_files:
                print(warning("Nenhum arquivo de análise LLM encontrado."))
                return []
            
            print(info(f"Encontrados {len(analysis_files)} arquivos de análise LLM."))
            
            for file_name in analysis_files:
                file_path = os.path.join(analyses_dir, file_name)
                try:
                    with open(file_path, 'r') as f:
                        file_analyses = json.load(f)
                        if isinstance(file_analyses, list):
                            all_analyses.extend(file_analyses)
                        else:
                            all_analyses.append(file_analyses)
                except Exception as e:
                    print(warning(f"Erro ao carregar {file_name}: {str(e)}"))
                    continue
            
            print(success(f"Carregadas {len(all_analyses)} análises LLM no total."))
            return all_analyses
        except Exception as e:
            print(error(f"Erro ao carregar análises LLM: {str(e)}"))
            return []
    
    def save_comparison_results(self, comparison_df):
        """
        Salva os resultados da comparação em um arquivo CSV.
        
        Args:
            comparison_df (pd.DataFrame): DataFrame com os resultados da comparação.
            
        Returns:
            str: Caminho do arquivo salvo ou None em caso de erro.
        """
        if comparison_df is None or len(comparison_df) == 0:
            print(warning("Nenhum resultado de comparação para salvar."))
            return None
        
        try:
            # Garantir que o diretório existe
            if not os.path.exists(PURITY_COMPARISON_DIR):
                os.makedirs(PURITY_COMPARISON_DIR)
            
            # Gerar nome do arquivo com timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"purity_llm_comparison_{timestamp}.csv"
            filepath = os.path.join(PURITY_COMPARISON_DIR, filename)
            
            # Salvar o arquivo
            comparison_df.to_csv(filepath, index=False)
            
            print(success(f"Comparação salva com sucesso em: {bold(filepath)}"))
            return filepath
        except Exception as e:
            print(error(f"Erro ao salvar comparação: {str(e)}"))
            return None
    
    def generate_comparison_summary(self, comparison_df):
        """
        Gera um resumo estatístico da comparação.
        
        Args:
            comparison_df (pd.DataFrame): DataFrame com os resultados da comparação.
        """
        if comparison_df is None or len(comparison_df) == 0:
            print(warning("Nenhum dado para gerar resumo."))
            return
        
        try:
            total_commits = len(comparison_df)
            analyzed_by_llm = len(comparison_df[comparison_df['llm_classification'] != 'not_analyzed'])
            not_analyzed_by_llm = total_commits - analyzed_by_llm
            
            if analyzed_by_llm > 0:
                agreement_count = len(comparison_df[comparison_df['agreement'] == True])
                disagreement_count = analyzed_by_llm - agreement_count
                
                llm_pure_count = len(comparison_df[comparison_df['llm_classification'] == 'pure'])
                llm_floss_count = len(comparison_df[comparison_df['llm_classification'] == 'floss'])
                
                agreement_percentage = (agreement_count / analyzed_by_llm) * 100
            else:
                agreement_count = disagreement_count = 0
                llm_pure_count = llm_floss_count = 0
                agreement_percentage = 0
            
            print(f"\n{header('=' * 60)}")
            print(f"{header('RESUMO DA COMPARAÇÃO PURITY vs LLM')}")
            print(f"{header('=' * 60)}")
            print(f"{info('Total de commits classificados como FLOSS pelo Purity:')} {bold(str(total_commits))}")
            print(f"{info('Analisados pelo LLM:')} {bold(str(analyzed_by_llm))}")
            print(f"{warning('Não analisados pelo LLM:')} {bold(str(not_analyzed_by_llm))}")
            print()
            
            if analyzed_by_llm > 0:
                print(f"{success('Concordância (ambos classificaram como FLOSS):')} {bold(str(agreement_count))} ({agreement_percentage:.1f}%)")
                print(f"{error('Discordância (LLM classificou como PURE):')} {bold(str(disagreement_count))}")
                print()
                print(f"{dim('Detalhamento das classificações LLM:')}")
                print(f"  {success('• FLOSS:')} {bold(str(llm_floss_count))}")
                print(f"  {warning('• PURE:')} {bold(str(llm_pure_count))}")
            
            print(f"{header('=' * 60)}")
        except Exception as e:
            print(error(f"Erro ao gerar resumo: {str(e)}"))

    def get_all_purity_commits(self, limit=None):
        """
        Obtém todos os commits do Purity (floss + pure) após limpeza de dados.
        
        Args:
            limit (int, optional): Limite de commits a retornar
            
        Returns:
            list: Lista de commits com suas classificações
        """
        try:
            if self.purity_data is None:
                print(error("Dados do Purity não carregados. Execute load_purity_data() primeiro."))
                return None
            
            # Usar apenas dados com classificação definida (purity não é None)
            classified_data = self.purity_data[self.purity_data['purity'].notna()].copy()
            
            if len(classified_data) == 0:
                print(warning("Nenhum commit com classificação Purity válida encontrado."))
                return []
            
            print(info(f"Processando {len(classified_data)} commits com classificação Purity válida"))
            print(dim(f"  • Classificação válida = commits com purity True/False (não None/NaN)"))
            
            # Obter commits únicos (já foram processados na limpeza)
            if limit:
                classified_data = classified_data.head(limit)
                print(info(f"Limitando a {limit} commits"))
            
            # Converter para lista de dicionários
            commits_list = []
            for _, row in classified_data.iterrows():
                # Determinar tipo baseado no valor da coluna 'purity'
                purity_value = row['purity']
                if purity_value == True:
                    commit_type = 'pure'
                elif purity_value == False:
                    commit_type = 'floss'
                else:
                    continue  # Pular registros sem classificação clara
                
                commit_info = {
                    'commit_hash_current': row['commit'],
                    'commit2': row['commit'],  # Alias para compatibilidade
                    'type': commit_type,
                    'purity_value': purity_value,
                    'purity_description': row.get('purity_description', ''),
                    'refactoring_type': row.get('refactoring_type', ''),
                    'refactoring_description': row.get('refactoring_description', ''),
                    'had_classification_conflict': row.get('had_classification_conflict', False)
                }
                commits_list.append(commit_info)
            
            # Estatísticas finais
            floss_count = sum(1 for c in commits_list if c['type'] == 'floss')
            pure_count = sum(1 for c in commits_list if c['type'] == 'pure')
            conflict_count = sum(1 for c in commits_list if c.get('had_classification_conflict', False))
            
            print(success(f"Commits processados com sucesso:"))
            print(info(f"  • Total: {len(commits_list)}"))
            print(info(f"  • Floss: {floss_count}"))
            print(info(f"  • Pure: {pure_count}"))
            if conflict_count > 0:
                print(warning(f"  • Com conflitos resolvidos: {conflict_count}"))
            
            return commits_list
            
        except Exception as e:
            print(error(f"Erro ao obter commits do Purity: {str(e)}"))
            import traceback
            traceback.print_exc()
            return None

    def get_unanalyzed_purity_commits(self, limit=None, analyzed_commits=None):
        """
        Obtém commits do Purity que ainda não foram analisados pelo LLM.
        
        Args:
            limit (int, optional): Número máximo de commits a retornar
            analyzed_commits (set, optional): Set de hashes já analisados
            
        Returns:
            tuple: (lista de commits não analisados, estatísticas)
        """
        try:
            if self.purity_data is None:
                print(error("Dados do Purity não carregados."))
                return None, None
            
            # Obter todos os commits classificados
            all_purity_commits = self.get_all_purity_commits()
            if not all_purity_commits:
                return None, None
            
            # Carregar análises LLM existentes se não fornecidas
            if analyzed_commits is None:
                llm_analyses = self.load_all_llm_analyses()
                analyzed_commits = set(item['commit_hash_current'] for item in llm_analyses)
            
            # Filtrar commits não analisados
            unanalyzed_commits = [
                commit for commit in all_purity_commits 
                if commit['commit_hash_current'] not in analyzed_commits
            ]
            
            # Aplicar limite se especificado
            if limit and len(unanalyzed_commits) > limit:
                unanalyzed_commits = unanalyzed_commits[:limit]
                print(info(f"Limitando análise aos primeiros {limit} commits não analisados"))
            
            # Estatísticas
            stats = {
                'total_purity': len(all_purity_commits),
                'already_analyzed': len(all_purity_commits) - len(unanalyzed_commits),
                'to_analyze': len(unanalyzed_commits),
                'floss_to_analyze': sum(1 for c in unanalyzed_commits if c['type'] == 'floss'),
                'pure_to_analyze': sum(1 for c in unanalyzed_commits if c['type'] == 'pure')
            }
            
            print(f"\n{header('ANÁLISE DE COMMITS PURITY:')}")
            print(f"{info('Total de commits Purity:')} {stats['total_purity']}")
            print(f"{success('Já analisados:')} {stats['already_analyzed']}")
            print(f"{warning('Pendentes de análise:')} {stats['to_analyze']}")
            print(f"{dim('  • Floss:')} {stats['floss_to_analyze']}")
            print(f"{dim('  • Pure:')} {stats['pure_to_analyze']}")
            
            return unanalyzed_commits, stats
            
        except Exception as e:
            print(error(f"Erro ao obter commits não analisados: {str(e)}"))
            return None, None

    def generate_comparison_data(self, llm_analyses, purity_commits):
        """
        Gera dados de comparação entre análises LLM e classificações Purity.
        
        Args:
            llm_analyses (list): Lista de análises LLM
            purity_commits (list): Lista de commits do Purity
            
        Returns:
            pandas.DataFrame: DataFrame com dados de comparação
        """
        try:
            # Criar dicionário de classificações Purity por commit hash
            purity_dict = {commit['commit_hash_current']: commit['type'] for commit in purity_commits}
            
            # Criar dicionário de análises LLM por commit hash
            llm_dict = {analysis['commit_hash_current']: analysis.get('refactoring_type', 'unknown') 
                       for analysis in llm_analyses}
            
            # Combinar dados
            comparison_data = []
            all_commit_hashes = set(purity_dict.keys()) | set(llm_dict.keys())
            
            for commit_hash in all_commit_hashes:
                purity_classification = purity_dict.get(commit_hash, 'not_in_purity')
                llm_classification = llm_dict.get(commit_hash, 'not_analyzed')
                
                # Determinar concordância
                agreement = False
                if purity_classification != 'not_in_purity' and llm_classification != 'not_analyzed':
                    agreement = purity_classification == llm_classification
                
                comparison_data.append({
                    'commit_hash': commit_hash,
                    'purity_classification': purity_classification,
                    'llm_classification': llm_classification,
                    'agreement': agreement,
                    'in_purity': purity_classification != 'not_in_purity',
                    'analyzed_by_llm': llm_classification != 'not_analyzed'
                })
            
            return pd.DataFrame(comparison_data)
            
        except Exception as e:
            print(error(f"Erro ao gerar dados de comparação: {str(e)}"))
            return None

    def display_comparison_statistics(self, comparison_df):
        """
        Exibe estatísticas da comparação LLM vs Purity.
        
        Args:
            comparison_df (pandas.DataFrame): DataFrame com dados de comparação
        """
        try:
            print(f"\n{header('=' * 60)}")
            print(f"{header('ESTATÍSTICAS DA COMPARAÇÃO LLM vs PURITY')}")
            print(f"{header('=' * 60)}")
            
            total_commits = len(comparison_df)
            print(f"{info('Total de commits únicos:')} {bold(str(total_commits))}")
            
            # Commits em ambos
            both_systems = comparison_df[
                (comparison_df['in_purity'] == True) & 
                (comparison_df['analyzed_by_llm'] == True)
            ]
            print(f"{info('Commits em ambos os sistemas:')} {bold(str(len(both_systems)))}")
            
            # Concordância
            if len(both_systems) > 0:
                agreements = both_systems['agreement'].sum()
                agreement_rate = (agreements / len(both_systems)) * 100
                print(f"{success('Concordâncias:')} {bold(str(agreements))} ({agreement_rate:.1f}%)")
                print(f"{warning('Discordâncias:')} {bold(str(len(both_systems) - agreements))}")
            
            # Por sistema
            only_purity = comparison_df[
                (comparison_df['in_purity'] == True) & 
                (comparison_df['analyzed_by_llm'] == False)
            ]
            only_llm = comparison_df[
                (comparison_df['in_purity'] == False) & 
                (comparison_df['analyzed_by_llm'] == True)
            ]
            
            print(f"{info('Apenas no Purity:')} {bold(str(len(only_purity)))}")
            print(f"{info('Apenas analisados pelo LLM:')} {bold(str(len(only_llm)))}")
            
            # Distribuição por tipo
            if len(both_systems) > 0:
                print(f"\n{header('DISTRIBUIÇÃO NOS COMMITS COMUNS:')}")
                purity_dist = both_systems['purity_classification'].value_counts()
                llm_dist = both_systems['llm_classification'].value_counts()
                
                print(f"{cyan('Purity:')}")
                for classification, count in purity_dist.items():
                    print(f"  • {classification}: {count}")
                
                print(f"{cyan('LLM:')}")
                for classification, count in llm_dist.items():
                    print(f"  • {classification}: {count}")
            
            print(f"{header('=' * 60)}")
            
        except Exception as e:
            print(error(f"Erro ao exibir estatísticas: {str(e)}"))
