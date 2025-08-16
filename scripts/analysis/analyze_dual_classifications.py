#!/usr/bin/env python3
"""
Analisador específico para dados com AMBAS classificações (Purity + LLM)
Gera CSV de comparação apenas para commits já classificados por ambos sistemas.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


import pandas as pd
import os
from datetime import datetime
from src.utils.colors import *
import json

class DualClassificationAnalyzer:
    """Analisador para commits com ambas classificações (Purity + LLM)."""
    
    def __init__(self):
        self.source_file = "csv/hashes_no_rpt_purity_with_analysis.csv"
        self.output_dir = "csv"
        
    def extract_dual_classified_data(self) -> pd.DataFrame:
        """Extrai apenas commits com ambas classificações válidas."""
        
        print(header("🔍 EXTRAINDO DADOS COM AMBAS CLASSIFICAÇÕES"))
        print(header("=" * 55))
        
        # Carregar dados principais
        df = pd.read_csv(self.source_file)
        print(info(f"📊 Total de commits no arquivo: {len(df):,}"))
        
        # Filtrar commits com ambas classificações válidas
        both_classified = df[
            (df['purity_analysis'].notna()) & 
            (df['llm_analysis'].notna()) & 
            (df['llm_analysis'] != '') & 
            (df['llm_analysis'] != 'FAILED') &
            (df['llm_analysis'] != 'ERROR')
        ].copy()
        
        print(success(f"✅ Commits com ambas classificações: {len(both_classified):,}"))
        
        if len(both_classified) == 0:
            print(error("❌ Nenhum commit com ambas classificações encontrado"))
            return None
            
        # Estatísticas dos dados filtrados
        print(f"\n{info('📈 Distribuição Purity:')}")
        purity_counts = both_classified['purity_analysis'].value_counts()
        for purity, count in purity_counts.items():
            print(f"   {purity}: {count} ({count/len(both_classified)*100:.1f}%)")
            
        print(f"\n{info('🤖 Distribuição LLM:')}")
        llm_counts = both_classified['llm_analysis'].value_counts()
        for llm, count in llm_counts.items():
            print(f"   {llm}: {count} ({count/len(both_classified)*100:.1f}%)")
        
        return both_classified
    
    def create_comparison_csv(self, df: pd.DataFrame, include_repository_info: bool = True) -> str:
        """Cria CSV de comparação formatado."""
        
        print(f"\n{info('📝 Criando CSV de comparação...')}")
        
        # Preparar dados de comparação
        comparison_data = df[['hash', 'purity_analysis', 'llm_analysis']].copy()
        
        # Normalizar classificações para comparação
        comparison_data['purity_normalized'] = comparison_data['purity_analysis'].map({
            'TRUE': 'PURE',
            'FALSE': 'FLOSS', 
            'NONE': 'UNKNOWN'
        })
        
        # Calcular acordo/desacordo
        comparison_data['agreement'] = (
            comparison_data['purity_normalized'] == comparison_data['llm_analysis']
        )
        
        # Renomear colunas para formato padrão
        final_data = comparison_data.rename(columns={
            'hash': 'commit_hash',
            'purity_analysis': 'purity_classification',
            'llm_analysis': 'llm_classification'
        })
        
        # Adicionar informações do repositório se solicitado
        if include_repository_info:
            print(info("🔍 Buscando informações de repositório..."))
            final_data = self._add_repository_info(final_data)
        
        # Salvar arquivo
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(self.output_dir, f"dual_classification_comparison_{timestamp}.csv")
        
        final_data.to_csv(output_file, index=False)
        print(success(f"✅ CSV salvo: {output_file}"))
        
        return output_file
    
    def _add_repository_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona informações de repositório aos dados."""
        
        # Tentar carregar dados do repositório do arquivo principal
        try:
            # Verificar se existe arquivo com dados de repositório
            main_data_file = "csv/commits_with_refactoring.csv"
            if os.path.exists(main_data_file):
                main_df = pd.read_csv(main_data_file)
                
                # Fazer merge para obter informações do repositório
                if 'commit1' in main_df.columns:
                    # Tentar fazer merge com commit1 (hash before)
                    merged = df.merge(
                        main_df[['commit1', 'project', 'project_name']],
                        left_on='commit_hash',
                        right_on='commit1',
                        how='left'
                    )
                    
                    # Se não encontrou, tentar com commit2 (hash after)  
                    if merged['project'].isna().all():
                        merged = df.merge(
                            main_df[['commit2', 'project', 'project_name']],
                            left_on='commit_hash',
                            right_on='commit2',
                            how='left'
                        )
                    
                    # Adicionar colunas de repositório
                    df['repository'] = merged['project'].fillna('unknown')
                    df['project_name'] = merged['project_name'].fillna('unknown')
                    
                    print(success(f"✅ Informações de repositório adicionadas para {(~df['repository'].eq('unknown')).sum()} commits"))
                else:
                    df['repository'] = 'unknown'
                    df['project_name'] = 'unknown'
                    print(warning("⚠️ Formato do arquivo principal não reconhecido"))
            else:
                df['repository'] = 'unknown'
                df['project_name'] = 'unknown'
                print(warning("⚠️ Arquivo de dados principais não encontrado"))
                
        except Exception as e:
            print(error(f"❌ Erro ao adicionar info do repositório: {e}"))
            df['repository'] = 'unknown'
            df['project_name'] = 'unknown'
            
        return df
    
    def analyze_agreements(self, df: pd.DataFrame) -> dict:
        """Analisa padrões de acordo/desacordo."""
        
        print(f"\n{header('📊 ANÁLISE DE ACORDOS/DESACORDOS')}")
        print(header("=" * 40))
        
        # Preparar dados para análise
        analysis_data = df.copy()
        analysis_data['purity_normalized'] = analysis_data['purity_analysis'].map({
            'TRUE': 'PURE',
            'FALSE': 'FLOSS',
            'NONE': 'UNKNOWN'
        })
        analysis_data['agreement'] = (
            analysis_data['purity_normalized'] == analysis_data['llm_analysis']
        )
        
        # Estatísticas gerais
        total = len(analysis_data)
        agreements = analysis_data['agreement'].sum()
        disagreements = total - agreements
        agreement_rate = (agreements / total * 100) if total > 0 else 0
        
        print(f"{info('📈 Estatísticas Gerais:')}")
        print(f"   Total de comparações: {total}")
        print(f"   Acordos: {agreements} ({agreement_rate:.1f}%)")
        print(f"   Desacordos: {disagreements} ({100-agreement_rate:.1f}%)")
        
        # Análise por tipo de classificação Purity
        print(f"\n{info('🔍 Análise por classificação Purity:')}")
        for purity_type in ['TRUE', 'FALSE', 'NONE']:
            subset = analysis_data[analysis_data['purity_analysis'] == purity_type]
            if len(subset) > 0:
                subset_agreements = subset['agreement'].sum()
                subset_rate = (subset_agreements / len(subset) * 100)
                print(f"   {purity_type}: {subset_agreements}/{len(subset)} acordos ({subset_rate:.1f}%)")
        
        # Análise por tipo de classificação LLM
        print(f"\n{info('🤖 Análise por classificação LLM:')}")
        for llm_type in analysis_data['llm_analysis'].unique():
            subset = analysis_data[analysis_data['llm_analysis'] == llm_type]
            if len(subset) > 0:
                subset_agreements = subset['agreement'].sum()
                subset_rate = (subset_agreements / len(subset) * 100)
                print(f"   {llm_type}: {subset_agreements}/{len(subset)} acordos ({subset_rate:.1f}%)")
        
        # Matriz de confusão
        print(f"\n{info('📋 Matriz de Confusão:')}")
        confusion_matrix = pd.crosstab(
            analysis_data['purity_normalized'], 
            analysis_data['llm_analysis'],
            margins=True
        )
        print(confusion_matrix)
        
        return {
            'total_comparisons': total,
            'agreements': agreements,
            'disagreements': disagreements,
            'agreement_rate': agreement_rate,
            'confusion_matrix': confusion_matrix.to_dict()
        }
    
    def save_analysis_report(self, stats: dict, output_file: str) -> str:
        """Salva relatório de análise em JSON."""
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_file = f"analysis_report_{timestamp}.json"
        
        report_data = {
            'generation_timestamp': datetime.now().isoformat(),
            'source_file': self.source_file,
            'output_csv': output_file,
            'statistics': stats,
            'description': 'Análise comparativa entre classificações Purity e LLM para commits com ambas classificações'
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
            
        print(success(f"✅ Relatório salvo: {report_file}"))
        return report_file

def main():
    """Função principal."""
    
    analyzer = DualClassificationAnalyzer()
    
    # Extrair dados com ambas classificações
    dual_data = analyzer.extract_dual_classified_data()
    
    if dual_data is None or len(dual_data) == 0:
        print(error("❌ Não há dados suficientes para análise"))
        return
    
    # Criar CSV de comparação
    comparison_file = analyzer.create_comparison_csv(dual_data, include_repository_info=True)
    
    # Analisar padrões de acordo/desacordo
    analysis_stats = analyzer.analyze_agreements(dual_data)
    
    # Salvar relatório
    report_file = analyzer.save_analysis_report(analysis_stats, comparison_file)
    
    print(f"\n{success('🎉 ANÁLISE COMPLETA!')}")
    print(f"📄 CSV de comparação: {comparison_file}")
    print(f"📊 Relatório: {report_file}")
    print(f"\n{info('💡 Próximos passos:')}")
    print("1. Use o CSV para análises estatísticas")
    print("2. Execute visualizações: python demo_llm_visualization.py")
    print("3. Examine padrões de desacordo para melhorar classificações")

if __name__ == "__main__":
    main()
