"""
Módulo responsável por carregar e processar o arquivo CSV de entrada.
Fornece funções para filtrar e manipular os dados de commits.
"""

import os
import json
import pandas as pd
import random
from src.core.config import CSV_PATH, PURITY_CSV_PATH, get_model_paths, get_current_llm_model
from src.utils.colors import *

class DataHandler:
    def __init__(self):
        """Inicializa o manipulador de dados."""
        self.data = None
        self.filtered_data = None
        self._refresh_model_paths()
        self.analyzed_commits = self._load_analyzed_commits()

    def _refresh_model_paths(self):
        """Atualiza caminhos dependentes do modelo atual."""
        paths = get_model_paths(get_current_llm_model())
        self.analyzed_commits_log = str(paths['ANALYZED_COMMITS_LOG'])
        
    def _load_analyzed_commits(self):
        """
        Carrega a lista de commits já analisados.
        
        Returns:
            set: Conjunto de IDs de commits já analisados.
        """
        try:
            if not os.path.exists(self.analyzed_commits_log):
                return set()
            with open(self.analyzed_commits_log, 'r') as f:
                commits_data = json.load(f)
            analyzed_commits = set()
            for item in commits_data:
                commit_hash = item.get('commit2') or item.get('commit_hash_current')
                if commit_hash:
                    analyzed_commits.add(commit_hash)
            print(info(f"Carregados {len(analyzed_commits)} commits já analisados."))
            return analyzed_commits
        except Exception as e:
            print(warning(f"Aviso: Erro ao carregar commits analisados: {str(e)}"))
            return set()
    
    def save_analyzed_commits(self, new_commits):
        """
        Adiciona novos commits analisados ao registro.
        
        Args:
            new_commits (list): Lista de dicionários com informações dos commits analisados.
        """
        try:
            existing_data = []
            if os.path.exists(self.analyzed_commits_log):
                with open(self.analyzed_commits_log, 'r') as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        existing_data = []
            
            # Adicionar novos commits
            existing_data.extend(new_commits)
            
            # Atualizar o conjunto de commits analisados
            for item in new_commits:
                # Suporte a ambos os formatos de nome de coluna
                commit_hash = item.get('commit2') or item.get('commit_hash_current')
                if commit_hash:
                    self.analyzed_commits.add(commit_hash)
            
            # Salvar o arquivo atualizado
            with open(self.analyzed_commits_log, 'w') as f:
                json.dump(existing_data, f, indent=4)

                print(success(f"Registro de commits analisados atualizado. {bold('Total:')} {bold(len(self.analyzed_commits))}"))
        except Exception as e:
            print(error(f"Erro ao salvar registro de commits analisados: {str(e)}"))
    
    def load_data(self):
        """
        Carrega os dados do CSV e verifica sua existência.
        
        Returns:
            bool: True se o carregamento foi bem-sucedido, False caso contrário.
        """
        try:
            if not os.path.exists(CSV_PATH):
                print(error(f"Erro: O arquivo {CSV_PATH} não foi encontrado."))
                return False
                
            self.data = pd.read_csv(CSV_PATH)
            print(success(f"Dados carregados com sucesso. Total de {len(self.data)} registros."))
            return True
        except Exception as e:
            print(error(f"Erro ao carregar os dados: {str(e)}"))
            return False
    
    def filter_data(self):
        """
        Filtra os dados mantendo apenas os cinco primeiros commits de cada projeto.
        Também remove duplicatas baseadas no commit2 (commit atual).
        
        Returns:
            bool: True se a filtragem foi bem-sucedida, False caso contrário.
        """
        if self.data is None:
            print(error("Erro: Dados não foram carregados. Execute load_data() primeiro."))
            return False
        
        try:
            # Agrupar por projeto e selecionar os últimos 12 registros de cada grupo
            filtered_by_project = self.data.groupby('project_name').tail(12).reset_index(drop=True)
            
            # Remover duplicatas baseadas no commit2 (mantendo a primeira ocorrência)
            self.filtered_data = filtered_by_project.drop_duplicates(subset=['commit2'], keep='first').reset_index(drop=True)
            
            original_count = len(filtered_by_project)
            deduplicated_count = len(self.filtered_data)
            duplicates_removed = original_count - deduplicated_count
            
            print(success(f"Dados filtrados com sucesso. Total de {deduplicated_count} registros únicos após filtragem."))
            if duplicates_removed > 0:
                print(info(f"Removidas {duplicates_removed} duplicatas baseadas no commit atual (commit2)."))
            
            return True
        except Exception as e:
            print(error(f"Erro ao filtrar os dados: {str(e)}"))
            return False
    
    def get_n_commits(self, n, skip_analyzed=True):
        """
        Retorna os primeiros N commits da lista filtrada, opcionalmente pulando commits já analisados.
        
        Args:
            n (int): Número de commits a serem retornados.
            skip_analyzed (bool): Se True, pula commits já analisados.
            
        Returns:
            pd.DataFrame: DataFrame com os N primeiros commits não analisados.
        """
        if self.filtered_data is None:
            print(error("Erro: Dados filtrados não estão disponíveis. Execute filter_data() primeiro."))
            return None
            
        try:
            if n <= 0:
                print(error("Erro: O número de commits deve ser positivo."))
                return None
            
            if skip_analyzed and self.analyzed_commits:
                unanalyzed_data = self.filtered_data[~self.filtered_data['commit2'].isin(self.analyzed_commits)]
                if len(unanalyzed_data) == 0:
                    print(warning("Aviso: Todos os commits já foram analisados."))
                    return None
                print(info(f"Encontrados {len(unanalyzed_data)} commits não analisados."))
                result = unanalyzed_data.head(n)
            else:
                # Sem filtro ou sem commits analisados anteriormente
                result = self.filtered_data.head(n)
                
            if len(result) < n:
                print(warning(f"Aviso: Apenas {len(result)} commits disponíveis, menor que os {n} solicitados."))
            return result
        except Exception as e:
            print(error(f"Erro ao obter {n} commits: {str(e)}"))
            return None
    
    def get_random_commit(self, skip_analyzed=True):
        """Retorna um commit aleatório da lista filtrada, opcionalmente pulando commits já analisados."""
        if self.filtered_data is None or len(self.filtered_data) == 0:
            print(error("Erro: Dados filtrados não estão disponíveis ou estão vazios."))
            return None
            
        try:
            if skip_analyzed and self.analyzed_commits:
                # Filtrar commits que ainda não foram analisados
                unanalyzed_data = self.filtered_data[~self.filtered_data['commit2'].isin(self.analyzed_commits)]
                
                if len(unanalyzed_data) == 0:
                    print(warning("Aviso: Todos os commits já foram analisados."))
                    return None
                    
                print(info(f"Selecionando entre {len(unanalyzed_data)} commits não analisados."))
                random_index = random.randint(0, len(unanalyzed_data) - 1)
                return unanalyzed_data.iloc[[random_index]]
            else:
                random_index = random.randint(0, len(self.filtered_data) - 1)
                return self.filtered_data.iloc[[random_index]]
        except Exception as e:
            print(error(f"Erro ao selecionar commit aleatório: {str(e)}"))
            return None
    
    def get_all_filtered_commits(self, skip_analyzed=True):
        """
        Retorna todos os commits da lista filtrada, opcionalmente pulando commits já analisados.
        
        Args:
            skip_analyzed (bool): Se True, retorna apenas commits não analisados.
            
        Returns:
            pd.DataFrame: DataFrame com os commits filtrados.
        """
        if self.filtered_data is None:
            print(error("Erro: Dados filtrados não estão disponíveis. Execute filter_data() primeiro."))
            return None
            
        if skip_analyzed and self.analyzed_commits:
            # Filtrar commits que ainda não foram analisados
            unanalyzed_data = self.filtered_data[~self.filtered_data['commit2'].isin(self.analyzed_commits)]
            
            if len(unanalyzed_data) == 0:
                print(warning("Aviso: Todos os commits já foram analisados."))
                return None
                
            print(info(f"Retornando {len(unanalyzed_data)} commits não analisados."))
            return unanalyzed_data
        else:
            return self.filtered_data
    
    def create_purity_commits_dataframe(self, floss_commits_list):
        """
        Cria um DataFrame para análise dos commits classificados como floss pelo Purity.
        
        Args:
            floss_commits_list (list): Lista de hashes de commits classificados como floss.
            
        Returns:
            pd.DataFrame: DataFrame com informações dos commits para análise.
        """
        if not floss_commits_list:
            print(error("Lista de commits floss está vazia."))
            return None
        
        try:
            # Carregar dados originais (sem filtro) para encontrar todos os commits
            if not os.path.exists(CSV_PATH):
                print(error(f"Arquivo {CSV_PATH} não encontrado."))
                return None
            
            original_data = pd.read_csv(CSV_PATH)
            
            # Filtrar commits que estão na lista de floss do Purity
            purity_commits = original_data[original_data['commit2'].isin(floss_commits_list)].copy()
            
            if len(purity_commits) == 0:
                print(warning("Nenhum commit da lista floss encontrado no arquivo CSV principal."))
                return None
            
            print(success(f"Encontrados {len(purity_commits)} commits do Purity no arquivo CSV principal."))
            return purity_commits
        except Exception as e:
            print(error(f"Erro ao criar DataFrame dos commits Purity: {str(e)}"))
            return None

    def get_commits_by_hashes(self, commit_hashes, skip_filtering=False):
        """
        Obtém commits específicos pelos seus hashes, opcionalmente pulando filtros.
        
        Args:
            commit_hashes (list): Lista de hashes de commits para buscar
            skip_filtering (bool): Se True, busca nos dados originais sem filtros
            
        Returns:
            pandas.DataFrame: DataFrame com os commits encontrados
        """
        try:
            if skip_filtering:
                # Carregar dados originais sem filtros
                if not os.path.exists(CSV_PATH):
                    print(error(f"Arquivo {CSV_PATH} não encontrado."))
                    return None
                
                original_data = pd.read_csv(CSV_PATH)
                data_to_search = original_data
            else:
                # Usar dados filtrados
                if self.filtered_data is None:
                    print(error("Dados filtrados não disponíveis."))
                    return None
                data_to_search = self.filtered_data
            
            # Buscar commits pelos hashes
            found_commits = data_to_search[
                data_to_search['commit2'].isin(commit_hashes)
            ].copy()
            
            if len(found_commits) == 0:
                print(warning("Nenhum commit encontrado para os hashes fornecidos."))
                return None
            
            print(info(f"Encontrados {len(found_commits)} commits dos {len(commit_hashes)} solicitados."))
            return found_commits
            
        except Exception as e:
            print(error(f"Erro ao buscar commits por hash: {str(e)}"))
            return None

    def check_dataset_duplicates(self):
        """
        Verifica e reporta duplicatas no dataset baseadas no commit2.
        
        Returns:
            dict: Estatísticas sobre duplicatas no dataset
        """
        try:
            if self.data is None:
                print(error("Dados não carregados."))
                return None
            
            # Análise de duplicatas por commit2 (commit atual)
            commit2_counts = self.data['commit2'].value_counts()
            duplicated_commit2 = commit2_counts[commit2_counts > 1]
            
            # Estatísticas gerais
            total_rows = len(self.data)
            unique_commit2 = len(commit2_counts)
            duplicated_count = len(duplicated_commit2)
            
            stats = {
                "total_rows": total_rows,
                "unique_commit2": unique_commit2,
                "duplicated_commit2": duplicated_count,
                "max_duplicates": duplicated_commit2.max() if len(duplicated_commit2) > 0 else 0,
                "total_duplicate_rows": duplicated_commit2.sum() if len(duplicated_commit2) > 0 else 0
            }
            
            print(f"\n{header('ANÁLISE DE DUPLICATAS NO DATASET:')}")
            print(f"{info('Total de linhas:')} {total_rows}")
            print(f"{info('Commits únicos (commit2):')} {unique_commit2}")
            print(f"{warning('Commits duplicados:')} {duplicated_count}")
            print(f"{error('Máximo de duplicatas:')} {stats['max_duplicates']}")
            print(f"{error('Total de linhas duplicadas:')} {stats['total_duplicate_rows']}")
            
            if duplicated_count > 0:
                print(f"\n{warning('Top 5 commits mais duplicados:')}")
                for i, (commit_hash, count) in enumerate(duplicated_commit2.head().items()):
                    print(f"  {i+1}. {commit_hash[:8]}... ({count} ocorrências)")
            
            return stats
            
        except Exception as e:
            print(error(f"Erro ao verificar duplicatas: {str(e)}"))
            return None
