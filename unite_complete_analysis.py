#!/usr/bin/env python3
"""
Script para unir todos os hashes com análises completas de purity e dos 3 modelos LLM
Combina arquivos FLOSS + TRUE de cada modelo para cobertura completa
"""

import pandas as pd
import sys
from pathlib import Path

def load_model_complete_data(model_name):
    """Carrega e combina dados FLOSS + TRUE de um modelo específico"""
    print(f"Carregando dados completos do {model_name}...")
    
    # Definir caminhos dos arquivos
    if model_name == 'mistral':
        floss_file = 'csv/llm_analysis_csv/mistral_latest_floss_hashes_no_rpt_purity_with_analysis.csv'
        true_file = 'csv/llm_analysis_csv/mistral_latest_true_purity_hashes_with_analysis.csv'
    elif model_name == 'gemma':
        floss_file = 'csv/llm_analysis_csv/gemma2_2b_floss_hashes_no_rpt_purity_with_analysis.csv'
        true_file = 'csv/llm_analysis_csv/gemma2_2b_true_purity_hashes_with_analysis.csv'
    elif model_name == 'deepseek':
        floss_file = 'csv/llm_analysis_csv/deepseek-r1_8b_floss_hashes_no_rpt_purity_with_analysis.csv'
        true_file = 'csv/llm_analysis_csv/deepseek-r1_8b_true_purity_hashes_with_analysis.csv'
    else:
        print(f"Modelo {model_name} não reconhecido!")
        return {}
    
    model_data = {}
    
    # Carregar arquivo FLOSS
    try:
        df_floss = pd.read_csv(floss_file)
        for _, row in df_floss.iterrows():
            hash_val = row['hash']
            model_data[hash_val] = {
                'purity_analysis': row['purity_analysis'],
                'llm_analysis': row['llm_analysis']
            }
        print(f"  {model_name} FLOSS: {len(df_floss)} registros")
    except Exception as e:
        print(f"  ERRO ao carregar {model_name} FLOSS: {e}")
        return {}
    
    # Carregar arquivo TRUE
    try:
        df_true = pd.read_csv(true_file)
        for _, row in df_true.iterrows():
            hash_val = row['hash']
            model_data[hash_val] = {
                'purity_analysis': row['purity_analysis'],
                'llm_analysis': row['llm_analysis']
            }
        print(f"  {model_name} TRUE: {len(df_true)} registros")
    except Exception as e:
        print(f"  ERRO ao carregar {model_name} TRUE: {e}")
    
    print(f"  {model_name} TOTAL: {len(model_data)} hashes únicos")
    return model_data

def get_all_unique_hashes(all_models_data):
    """Obtém todos os hashes únicos de todos os modelos"""
    all_hashes = set()
    
    for model_name, model_data in all_models_data.items():
        all_hashes.update(model_data.keys())
    
    return sorted(list(all_hashes))

def generate_complete_unified_analysis(all_models_data, output_file='complete_unified_analysis.csv'):
    """Gera análise completa unificada"""
    print(f"\nGerando análise unificada completa...")
    
    # Obter todos os hashes únicos
    all_hashes = get_all_unique_hashes(all_models_data)
    print(f"Total de hashes únicos encontrados: {len(all_hashes)}")
    
    results = []
    
    for hash_value in all_hashes:
        # Inicializar dados
        result = {'hash': hash_value}
        
        # Obter purity_analysis (deve ser igual em todos os modelos onde existe)
        purity_analysis = None
        for model_name in ['mistral', 'gemma', 'deepseek']:
            if hash_value in all_models_data[model_name]:
                purity_analysis = all_models_data[model_name][hash_value]['purity_analysis']
                break
        
        result['purity'] = str(purity_analysis).lower() if purity_analysis else 'unknown'
        
        # Obter análises dos 3 modelos
        for model_name in ['mistral', 'gemma', 'deepseek']:
            if hash_value in all_models_data[model_name]:
                llm_analysis = all_models_data[model_name][hash_value]['llm_analysis']
                result[model_name] = str(llm_analysis).lower() if llm_analysis else 'not_found'
            else:
                result[model_name] = 'not_found'
        
        results.append(result)
    
    # Criar DataFrame e salvar
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_file, index=False)
    
    print(f"Análise unificada completa salva em: {output_file}")
    return result_df

def show_unified_statistics(df):
    """Mostra estatísticas dos dados unificados"""
    print(f"\n=== ESTATÍSTICAS UNIFICADAS ===")
    print(f"Total de hashes: {len(df)}")
    
    print(f"\n--- Distribuição Purity ---")
    purity_counts = df['purity'].value_counts()
    for purity, count in purity_counts.items():
        print(f"  {purity}: {count} ({count/len(df)*100:.1f}%)")
    
    print(f"\n--- Distribuição Mistral ---")
    mistral_counts = df['mistral'].value_counts()
    for classification, count in mistral_counts.items():
        print(f"  {classification}: {count} ({count/len(df)*100:.1f}%)")
    
    print(f"\n--- Distribuição Gemma ---")
    gemma_counts = df['gemma'].value_counts()
    for classification, count in gemma_counts.items():
        print(f"  {classification}: {count} ({count/len(df)*100:.1f}%)")
    
    print(f"\n--- Distribuição Deepseek ---")
    deepseek_counts = df['deepseek'].value_counts()
    for classification, count in deepseek_counts.items():
        print(f"  {classification}: {count} ({count/len(df)*100:.1f}%)")
    
    # Verificar cobertura
    print(f"\n--- Cobertura por Modelo ---")
    for model in ['mistral', 'gemma', 'deepseek']:
        found = len(df[df[model] != 'not_found'])
        print(f"  {model}: {found} hashes ({found/len(df)*100:.1f}%)")
    
    # Combinações mais frequentes
    print(f"\n--- Top 10 Combinações (Mistral, Gemma, Deepseek) ---")
    combinations = df[['mistral', 'gemma', 'deepseek']].apply(
        lambda x: f"{x['mistral']},{x['gemma']},{x['deepseek']}", axis=1)
    combination_counts = combinations.value_counts().head(10)
    for combo, count in combination_counts.items():
        print(f"  {combo}: {count} casos")

def show_unified_sample_data(df, n=10):
    """Mostra amostra dos dados unificados"""
    print(f"\n=== AMOSTRA DOS DADOS UNIFICADOS (primeiros {n}) ===")
    print("hash,purity,mistral,gemma,deepseek")
    for i in range(min(n, len(df))):
        row = df.iloc[i]
        print(f"{row['hash']},{row['purity']},{row['mistral']},{row['gemma']},{row['deepseek']}")

def main():
    """Função principal"""
    print("=== UNIÃO COMPLETA - FLOSS + TRUE DE TODOS OS MODELOS ===")
    
    # Carregar dados completos de todos os modelos
    all_models_data = {}
    
    for model_name in ['mistral', 'gemma', 'deepseek']:
        model_data = load_model_complete_data(model_name)
        if not model_data:
            print(f"Falha ao carregar dados do {model_name}. Encerrando.")
            sys.exit(1)
        all_models_data[model_name] = model_data
    
    # Gerar análise unificada completa
    result_df = generate_complete_unified_analysis(all_models_data)
    
    # Mostrar estatísticas
    show_unified_statistics(result_df)
    
    # Mostrar amostra
    show_unified_sample_data(result_df)
    
    print(f"\n=== PROCESSO UNIFICADO CONCLUÍDO ===")
    print(f"Arquivo gerado: complete_unified_analysis.csv")
    print(f"Total de hashes processados: {len(result_df)}")

if __name__ == "__main__":
    main()