#!/usr/bin/env python3
"""
Script para unir todos os hashes com suas análises de purity e dos 3 modelos LLM
Combina dados de todos os arquivos (TRUE, FALSE, NONE) com análises dos 3 modelos
"""

import pandas as pd
import sys
from pathlib import Path

def load_all_purity_data():
    """Carrega e combina dados de todos os arquivos de purity"""
    print("Carregando dados de purity de todos os arquivos...")
    
    # Arquivo principal que já tem todos os hashes
    main_file = 'csv/hashes_no_rpt_purity_with_analysis.csv'
    
    try:
        df = pd.read_csv(main_file)
        print(f"Carregado arquivo principal: {len(df)} registros")
        return df
    except Exception as e:
        print(f"Erro ao carregar arquivo principal {main_file}: {e}")
        return None

def load_all_llm_models():
    """Carrega dados dos 3 modelos LLM"""
    print("\nCarregando dados dos 3 modelos LLM...")
    
    models = {}
    model_files = {
        'mistral': 'csv/llm_analysis_csv/mistral_latest_floss_hashes_no_rpt_purity_with_analysis.csv',
        'gemma': 'csv/llm_analysis_csv/gemma2_2b_floss_hashes_no_rpt_purity_with_analysis.csv',
        'deepseek': 'csv/llm_analysis_csv/deepseek-r1_8b_floss_hashes_no_rpt_purity_with_analysis.csv'
    }
    
    for model_name, file_path in model_files.items():
        try:
            df = pd.read_csv(file_path)
            # Criar dicionário hash -> llm_analysis para busca rápida
            models[model_name] = dict(zip(df['hash'], df['llm_analysis']))
            print(f"  {model_name}: {len(models[model_name])} registros")
        except Exception as e:
            print(f"  ERRO ao carregar {model_name} de {file_path}: {e}")
            models[model_name] = {}
    
    return models

def generate_complete_analysis(df, models, output_file='complete_analysis.csv'):
    """Gera análise completa com todos os hashes e modelos"""
    print(f"\nGerando análise completa para {len(df)} hashes...")
    
    results = []
    
    for _, row in df.iterrows():
        hash_value = row['hash']
        purity_analysis = row['purity_analysis']
        
        # Buscar classificações nos 3 modelos
        mistral_class = models['mistral'].get(hash_value, 'not_found')
        gemma_class = models['gemma'].get(hash_value, 'not_found')
        deepseek_class = models['deepseek'].get(hash_value, 'not_found')
        
        # Normalizar para lowercase
        mistral_class = str(mistral_class).lower() if mistral_class else 'not_found'
        gemma_class = str(gemma_class).lower() if gemma_class else 'not_found'
        deepseek_class = str(deepseek_class).lower() if deepseek_class else 'not_found'
        purity_analysis = str(purity_analysis).lower() if purity_analysis else 'unknown'
        
        results.append({
            'hash': hash_value,
            'purity': purity_analysis,
            'mistral': mistral_class,
            'gemma': gemma_class,
            'deepseek': deepseek_class
        })
    
    # Criar DataFrame e salvar
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_file, index=False)
    
    print(f"Análise completa salva em: {output_file}")
    return result_df

def show_statistics(df):
    """Mostra estatísticas dos dados"""
    print(f"\n=== ESTATÍSTICAS GERAIS ===")
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
    
    # Mostrar combinações mais frequentes
    print(f"\n--- Top 10 Combinações (Mistral, Gemma, Deepseek) ---")
    combinations = df[['mistral', 'gemma', 'deepseek']].apply(lambda x: f"{x['mistral']},{x['gemma']},{x['deepseek']}", axis=1)
    combination_counts = combinations.value_counts().head(10)
    for combo, count in combination_counts.items():
        print(f"  {combo}: {count} casos")

def show_sample_data(df, n=10):
    """Mostra amostra dos dados"""
    print(f"\n=== AMOSTRA DOS DADOS (primeiros {n}) ===")
    print("hash,purity,mistral,gemma,deepseek")
    for i in range(min(n, len(df))):
        row = df.iloc[i]
        print(f"{row['hash']},{row['purity']},{row['mistral']},{row['gemma']},{row['deepseek']}")

def main():
    """Função principal"""
    print("=== UNIÃO COMPLETA DE TODAS AS ANÁLISES ===")
    
    # Carregar dados de purity
    purity_df = load_all_purity_data()
    if purity_df is None:
        print("Falha ao carregar dados de purity. Encerrando.")
        sys.exit(1)
    
    # Carregar dados dos modelos LLM
    models = load_all_llm_models()
    if not models:
        print("Falha ao carregar dados dos modelos LLM. Encerrando.")
        sys.exit(1)
    
    # Gerar análise completa
    result_df = generate_complete_analysis(purity_df, models)
    
    # Mostrar estatísticas
    show_statistics(result_df)
    
    # Mostrar amostra
    show_sample_data(result_df)
    
    print(f"\n=== PROCESSO CONCLUÍDO ===")
    print(f"Arquivo gerado: complete_analysis.csv")
    print(f"Total de hashes processados: {len(result_df)}")

if __name__ == "__main__":
    main()