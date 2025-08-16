"""
Módulo responsável por gerar visualizações interativas dos dados de análise de commits.
Fornece gráficos detalhados sobre as classificações de refatoramento e estatísticas.
"""

import json
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
from src.core.config import get_model_paths, get_current_llm_model
from src.utils.colors import *

class VisualizationHandler:
    def __init__(self):
        """Inicializa o manipulador de visualizações."""
        self.analyzed_data = None
        self.load_analyzed_data()
    
    def load_analyzed_data(self):
        """
        Carrega todos os dados de commits analisados.
        
        Returns:
            bool: True se carregamento foi bem-sucedido, False caso contrário.
        """
        try:
            paths = get_model_paths(get_current_llm_model())
            analyzed_commits_log = str(paths['ANALYZED_COMMITS_LOG'])
            analyses_dir = str(paths['ANALISES_DIR'])
            all_analyses = []

            if os.path.exists(analyzed_commits_log):
                with open(analyzed_commits_log, 'r') as f:
                    try:
                        main_data = json.load(f)
                        if isinstance(main_data, list):
                            all_analyses.extend(main_data)
                    except Exception as e:
                        print(warning(f"Erro ao ler analyzed_commits.json: {e}"))

            if os.path.exists(analyses_dir):
                analysis_files = [f for f in os.listdir(analyses_dir) if f.startswith('analise_') and f.endswith('.json')]
                for file_name in analysis_files:
                    file_path = os.path.join(analyses_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            file_data = json.load(f)
                            if isinstance(file_data, list):
                                all_analyses.extend(file_data)
                            else:
                                all_analyses.append(file_data)
                    except Exception as e:
                        print(warning(f"Erro ao carregar {file_name}: {str(e)}"))

            if all_analyses:
                # Remover duplicatas baseado no commit_hash_current
                unique_analyses = {}
                for item in all_analyses:
                    commit_hash = item.get('commit_hash_current')
                    if commit_hash and commit_hash not in unique_analyses:
                        unique_analyses[commit_hash] = item
                
                self.analyzed_data = pd.DataFrame(list(unique_analyses.values()))
                print(success(f"Carregados {len(self.analyzed_data)} commits únicos para visualização."))
                return True
            else:
                print(warning("Nenhum dado de análise encontrado."))
                return False
                
        except Exception as e:
            print(error(f"Erro ao carregar dados para visualização: {str(e)}"))
            return False
    
    def create_comprehensive_dashboard(self, save_html=True, save_image=False):
        """
        Cria um dashboard abrangente com múltiplos gráficos interativos.
        
        Args:
            save_html (bool): Se deve salvar como arquivo HTML interativo
            save_image (bool): Se deve salvar como imagem PNG
            
        Returns:
            str: Caminho do arquivo salvo ou None se erro
        """
        if self.analyzed_data is None or len(self.analyzed_data) == 0:
            print(error("Nenhum dado disponível para visualização."))
            return None
        
        try:
            # Preparar dados
            data = self.analyzed_data.copy()
            
            # Extrair nome do repositório da URL
            data['repo_name'] = data['repository'].apply(self._extract_repo_name)
            
            # Converter para categorias se necessário
            data['refactoring_type'] = data['refactoring_type'].astype('category')
            
            # Criar subplots
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=[
                    'Distribuição de Tipos de Refatoramento',
                    'Refatoramento por Repositório',
                    'Timeline de Análises',
                    'Distribuição por Confiança (se disponível)',
                    'Top 10 Repositórios por Volume',
                    'Estatísticas Gerais'
                ],
                specs=[
                    [{"type": "domain"}, {"type": "bar"}],
                    [{"type": "scatter", "colspan": 2}, None],
                    [{"type": "bar"}, {"type": "table"}]
                ],
                vertical_spacing=0.08,
                horizontal_spacing=0.05
            )
            
            # 1. Gráfico de Pizza - Distribuição de Tipos
            refact_counts = data['refactoring_type'].value_counts()
            colors = ['#2E8B57', '#DC143C']  # Verde para pure, vermelho para floss
            
            fig.add_trace(
                go.Pie(
                    labels=refact_counts.index,
                    values=refact_counts.values,
                    name="Tipos",
                    marker_colors=colors,
                    hovertemplate="<b>%{label}</b><br>Quantidade: %{value}<br>Percentual: %{percent}<extra></extra>"
                ),
                row=1, col=1
            )
            
            # 2. Gráfico de Barras - Por Repositório
            repo_refact = data.groupby(['repo_name', 'refactoring_type']).size().unstack(fill_value=0)
            
            if 'pure' in repo_refact.columns:
                fig.add_trace(
                    go.Bar(
                        x=repo_refact.index,
                        y=repo_refact['pure'],
                        name='Pure',
                        marker_color='#2E8B57',
                        hovertemplate="<b>%{x}</b><br>Pure: %{y}<extra></extra>"
                    ),
                    row=1, col=2
                )
            
            if 'floss' in repo_refact.columns:
                fig.add_trace(
                    go.Bar(
                        x=repo_refact.index,
                        y=repo_refact['floss'],
                        name='Floss',
                        marker_color='#DC143C',
                        hovertemplate="<b>%{x}</b><br>Floss: %{y}<extra></extra>"
                    ),
                    row=1, col=2
                )
            
            # 3. Timeline (se houver dados de timestamp)
            self._add_timeline_chart(fig, data, row=2, col=1)
            
            # 4. Gráfico de Confiança (se disponível)
            if 'confidence_level' in data.columns or 'diff_size_chars' in data.columns:
                self._add_confidence_chart(fig, data, row=2, col=2)
            
            # 5. Top 10 Repositórios
            top_repos = data['repo_name'].value_counts().head(10)
            fig.add_trace(
                go.Bar(
                    x=top_repos.values,
                    y=top_repos.index,
                    orientation='h',
                    marker_color='#4169E1',
                    name='Volume',
                    hovertemplate="<b>%{y}</b><br>Commits: %{x}<extra></extra>"
                ),
                row=3, col=1
            )
            
            # 6. Tabela de Estatísticas
            stats = self._generate_statistics(data)
            fig.add_trace(
                go.Table(
                    header=dict(
                        values=['Métrica', 'Valor'],
                        fill_color='#4169E1',
                        font_color='white',
                        font_size=12,
                        align='left'
                    ),
                    cells=dict(
                        values=[list(stats.keys()), list(stats.values())],
                        fill_color='#F0F8FF',
                        font_size=11,
                        align='left'
                    )
                ),
                row=3, col=2
            )
            
            # Configurar layout
            current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            fig.update_layout(
                title={
                    'text': f"<b>Dashboard de Análise de Refatoramento</b><br><sub>Gerado em {current_date} | Total de {len(data)} commits analisados</sub>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20}
                },
                height=1200,
                showlegend=True,
                template='plotly_white',
                font=dict(family="Arial, sans-serif", size=10),
                margin=dict(l=50, r=50, t=100, b=50)
            )
            
            # Atualizar eixos
            fig.update_xaxes(title_text="Repositórios", row=1, col=2)
            fig.update_yaxes(title_text="Quantidade", row=1, col=2)
            fig.update_xaxes(title_text="Quantidade de Commits", row=3, col=1)
            fig.update_yaxes(title_text="Repositórios", row=3, col=1)
            
            # Salvar arquivos
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            saved_files = []
            
            if save_html:
                html_filename = f"dashboard_refatoramento_{timestamp}.html"
                fig.write_html(html_filename)
                saved_files.append(html_filename)
                print(success(f"Dashboard HTML salvo: {bold(html_filename)}"))
            
            if save_image:
                try:
                    png_filename = f"dashboard_refatoramento_{timestamp}.png"
                    fig.write_image(png_filename, width=1400, height=1200, scale=2)
                    saved_files.append(png_filename)
                    print(success(f"Dashboard PNG salvo: {bold(png_filename)}"))
                except Exception as e:
                    print(warning(f"Erro ao salvar PNG (instale kaleido: pip install kaleido): {str(e)}"))
            
            # Mostrar gráfico
            fig.show()
            
            return saved_files[0] if saved_files else None
            
        except Exception as e:
            print(error(f"Erro ao criar dashboard: {str(e)}"))
            return None
    
    def create_comparison_chart(self, comparison_data, save_html=True, save_image=False):
        """
        Cria gráfico específico para comparação LLM vs Purity.
        
        Args:
            comparison_data (pd.DataFrame): Dados da comparação
            save_html (bool): Se deve salvar como HTML
            save_image (bool): Se deve salvar como PNG
            
        Returns:
            str: Caminho do arquivo salvo
        """
        try:
            if comparison_data is None or len(comparison_data) == 0:
                print(error("Nenhum dado de comparação disponível."))
                return None
            
            # Verificar se temos dados de comparação válidos (ambos os sistemas)
            valid_comparison = comparison_data[
                (comparison_data.get('in_purity', False) == True) & 
                (comparison_data.get('analyzed_by_llm', False) == True)
            ]
            
            if len(valid_comparison) == 0:
                print(warning("Nenhum commit foi analisado por ambos os sistemas."))
                # Mostrar estatísticas dos dados disponíveis
                purity_only = len(comparison_data[comparison_data.get('in_purity', False) == True])
                llm_only = len(comparison_data[comparison_data.get('analyzed_by_llm', False) == True])
                print(info(f"Commits apenas Purity: {purity_only}"))
                print(info(f"Commits apenas LLM: {llm_only}"))
                return None
            
            # Usar dados válidos para comparação
            data_to_plot = valid_comparison
            
            # Criar subplots para comparação
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=[
                    'Concordância LLM vs Purity',
                    'Distribuição de Classificações LLM',
                    'Distribuição de Classificações Purity',
                    'Matriz de Confusão'
                ],
                specs=[
                    [{"type": "domain"}, {"type": "domain"}],
                    [{"type": "domain"}, {"type": "heatmap"}]
                ]
            )
            
            # 1. Gráfico de concordância
            agreement_counts = data_to_plot['agreement'].value_counts()
            total_valid = len(data_to_plot)
            concordancia_pct = (agreement_counts.get(True, 0) / total_valid * 100) if total_valid > 0 else 0
            
            fig.add_trace(
                go.Pie(
                    labels=[f'Concordância ({agreement_counts.get(True, 0)})', 
                           f'Discordância ({agreement_counts.get(False, 0)})'],
                    values=[agreement_counts.get(True, 0), agreement_counts.get(False, 0)],
                    marker_colors=['#2E8B57', '#DC143C'],
                    name="Concordância",
                    textinfo='label+percent'
                ),
                row=1, col=1
            )
            
            # 2. Distribuição LLM
            llm_counts = data_to_plot['llm_classification'].value_counts()
            fig.add_trace(
                go.Pie(
                    labels=[f'{label} ({count})' for label, count in llm_counts.items()],
                    values=llm_counts.values,
                    name="LLM",
                    textinfo='label+percent'
                ),
                row=1, col=2
            )
            
            # 3. Distribuição Purity
            purity_counts = data_to_plot['purity_classification'].value_counts()
            fig.add_trace(
                go.Pie(
                    labels=[f'{label} ({count})' for label, count in purity_counts.items()],
                    values=purity_counts.values,
                    name="Purity",
                    textinfo='label+percent'
                ),
                row=2, col=1
            )
            
            # 4. Matriz de confusão
            confusion_matrix = pd.crosstab(
                data_to_plot['purity_classification'], 
                data_to_plot['llm_classification']
            )
            
            fig.add_trace(
                go.Heatmap(
                    z=confusion_matrix.values,
                    x=confusion_matrix.columns,
                    y=confusion_matrix.index,
                    colorscale='Blues',
                    text=confusion_matrix.values,
                    texttemplate="%{text}",
                    textfont={"size": 16},
                    name="Matriz"
                ),
                row=2, col=2
            )
            
            # Layout
            current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            fig.update_layout(
                title={
                    'text': f"<b>Comparação LLM vs Purity Checker</b><br><sub>Gerado em {current_date} | {len(data_to_plot)} commits com análise de ambos | Concordância: {concordancia_pct:.1f}%</sub>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 18}
                },
                height=800,
                showlegend=False,
                annotations=[
                    dict(
                        text=f"<b>Estatísticas Gerais:</b><br>" +
                             f"• Total de commits comparados: {len(data_to_plot)}<br>" +
                             f"• Concordância: {agreement_counts.get(True, 0)} ({concordancia_pct:.1f}%)<br>" +
                             f"• Discordância: {agreement_counts.get(False, 0)} ({100-concordancia_pct:.1f}%)",
                        xref="paper", yref="paper",
                        x=0.02, y=0.98, xanchor="left", yanchor="top",
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="rgba(0,0,0,0.2)",
                        borderwidth=1,
                        font=dict(size=12)
                    )
                ]
            )
            
            # Ajustar títulos dos subplots
            fig.update_xaxes(title_text="Classificação LLM", row=2, col=2)
            fig.update_yaxes(title_text="Classificação Purity", row=2, col=2)
            
            # Salvar e mostrar
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            saved_files = []
            
            if save_html:
                html_filename = f"comparacao_llm_purity_{timestamp}.html"
                fig.write_html(html_filename)
                saved_files.append(html_filename)
                print(success(f"Gráfico de comparação HTML salvo: {bold(html_filename)}"))
            
            if save_image:
                try:
                    png_filename = f"comparacao_llm_purity_{timestamp}.png"
                    fig.write_image(png_filename, width=1200, height=800, scale=2)
                    saved_files.append(png_filename)
                    print(success(f"Gráfico de comparação PNG salvo: {bold(png_filename)}"))
                except:
                    print(warning("Erro ao salvar PNG (instale kaleido: pip install kaleido)"))
            
            # Mostrar gráfico interativo
            fig.show()
            
            return saved_files[0] if saved_files else None
            
        except Exception as e:
            print(error(f"Erro ao criar gráfico de comparação: {str(e)}"))
            return None
    
    def _extract_repo_name(self, repo_url):
        """Extrai o nome do repositório da URL."""
        try:
            return repo_url.split('/')[-1].replace('.git', '')
        except:
            return 'Unknown'
    
    def _add_timeline_chart(self, fig, data, row, col):
        """Adiciona gráfico de timeline se houver dados de data."""
        try:
            # Tentar extrair data do commit_hash_current ou criar timeline artificial
            if 'timestamp' in data.columns:
                timeline_data = data.groupby('timestamp')['refactoring_type'].value_counts().unstack(fill_value=0)
            else:
                # Criar timeline baseado na ordem dos dados
                data_indexed = data.reset_index()
                timeline_data = data_indexed.groupby(data_indexed.index // 10)['refactoring_type'].value_counts().unstack(fill_value=0)
                timeline_data.index = [f"Batch {i+1}" for i in timeline_data.index]
            
            if 'pure' in timeline_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=timeline_data.index,
                        y=timeline_data['pure'],
                        mode='lines+markers',
                        name='Pure (Timeline)',
                        line=dict(color='#2E8B57'),
                        marker=dict(size=6)
                    ),
                    row=row, col=col
                )
            
            if 'floss' in timeline_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=timeline_data.index,
                        y=timeline_data['floss'],
                        mode='lines+markers',
                        name='Floss (Timeline)',
                        line=dict(color='#DC143C'),
                        marker=dict(size=6)
                    ),
                    row=row, col=col
                )
                
        except Exception as e:
            print(warning(f"Erro ao criar timeline: {str(e)}"))
    
    def _add_confidence_chart(self, fig, data, row, col):
        """Adiciona gráfico de confiança se disponível."""
        try:
            if 'confidence_level' in data.columns:
                confidence_counts = data['confidence_level'].value_counts()
                fig.add_trace(
                    go.Bar(
                        x=confidence_counts.index,
                        y=confidence_counts.values,
                        marker_color='#9370DB',
                        name='Confiança',
                        hovertemplate="<b>%{x}</b><br>Quantidade: %{y}<extra></extra>"
                    ),
                    row=row, col=col
                )
            elif 'diff_size_chars' in data.columns:
                # Gráfico alternativo - tamanho de diff se disponível
                fig.add_trace(
                    go.Histogram(
                        x=data['diff_size_chars'],
                        nbinsx=20,
                        marker_color='#9370DB',
                        name='Tamanho Diff',
                        hovertemplate="<b>Tamanho</b><br>Chars: %{x}<br>Frequência: %{y}<extra></extra>"
                    ),
                    row=row, col=col
                )
            else:
                # Gráfico placeholder se não houver dados
                fig.add_trace(
                    go.Scatter(
                        x=[1, 2, 3],
                        y=[1, 2, 1],
                        mode='lines+markers',
                        name='Placeholder',
                        marker_color='#9370DB'
                    ),
                    row=row, col=col
                )
        except Exception as e:
            print(warning(f"Erro ao criar gráfico de confiança: {str(e)}"))
    
    def _generate_statistics(self, data):
        """Gera estatísticas resumidas dos dados."""
        stats = {}
        
        try:
            stats['Total de Commits'] = len(data)
            stats['Repositórios Únicos'] = data['repo_name'].nunique()
            
            refact_counts = data['refactoring_type'].value_counts()
            stats['Commits Pure'] = refact_counts.get('pure', 0)
            stats['Commits Floss'] = refact_counts.get('floss', 0)
            
            if len(data) > 0:
                stats['% Pure'] = f"{(stats['Commits Pure'] / len(data) * 100):.1f}%"
                stats['% Floss'] = f"{(stats['Commits Floss'] / len(data) * 100):.1f}%"
            
            top_repo = data['repo_name'].value_counts().index[0] if len(data) > 0 else 'N/A'
            stats['Repo com Mais Commits'] = top_repo
            
            if 'diff_size_chars' in data.columns:
                stats['Tamanho Médio Diff'] = f"{data['diff_size_chars'].mean():.0f} chars"
            
            if 'confidence_level' in data.columns:
                stats['Confiança Mais Comum'] = data['confidence_level'].mode().iloc[0] if len(data) > 0 else 'N/A'
                
        except Exception as e:
            print(warning(f"Erro ao gerar estatísticas: {str(e)}"))
            
        return stats

    def get_summary_stats(self):
        """
        Retorna estatísticas resumidas dos dados carregados.
        
        Returns:
            dict: Dicionário com estatísticas principais
        """
        if self.analyzed_data is None or len(self.analyzed_data) == 0:
            return {"error": "Nenhum dado disponível"}
        
        return self._generate_statistics(self.analyzed_data)
