#!/usr/bin/env python3
"""
Script para extrair 500 hashes com resultado NONE do puritychecker
e buscar suas classificações nos 3 modelos LLM (mistral, gemma2b, deepseek8b)
"""

import pandas as pd
import sys
from pathlib import Path

def load_purity_data():
    """Carrega dados do arquivo floss_hashes_no_rpt_purity_with_analysis.csv"""
    try:
        df = pd.read_csv('csv/floss_hashes_no_rpt_purity_with_analysis.csv')
        return df
    except Exception as e:
        print(f"Erro ao carregar arquivo floss_hashes: {e}")
        return None

def load_llm_model_data():
    """Carrega dados dos 3 modelos LLM"""
    models = {}
    
    model_files = {
        'mistral': 'csv/llm_analysis_csv/mistral_latest_floss_hashes_no_rpt_purity_with_analysis.csv',
        'gemma': 'csv/llm_analysis_csv/gemma2_2b_floss_hashes_no_rpt_purity_with_analysis.csv',
        'dpsk': 'csv/llm_analysis_csv/deepseek-r1_8b_floss_hashes_no_rpt_purity_with_analysis.csv'
    }
    
    for model_name, file_path in model_files.items():
        try:
            df = pd.read_csv(file_path)
            # Criar dicionário hash -> llm_analysis para busca rápida
            models[model_name] = dict(zip(df['hash'], df['llm_analysis']))
            print(f"Carregado {model_name}: {len(models[model_name])} registros")
        except Exception as e:
            print(f"Erro ao carregar {model_name} de {file_path}: {e}")
            models[model_name] = {}
    
    return models

def extract_none_hashes(df, limit=500):
    """Extrai hashes únicos onde purity_analysis == 'NONE'"""
    # Filtrar onde purity_analysis é 'NONE'
    none_df = df[df['purity_analysis'] == 'NONE']
    
    # Obter hashes únicos
    unique_hashes = none_df['hash'].unique()
    
    print(f"Total de registros com purity_analysis=NONE: {len(none_df)}")
    print(f"Hashes únicos com purity_analysis=NONE: {len(unique_hashes)}")
    
    # Limitar a 500 hashes
    selected_hashes = unique_hashes[:limit]
    print(f"Selecionados para análise: {len(selected_hashes)} hashes")
    
    return selected_hashes

def generate_report(hashes, models, output_file='purity_none_analysis.csv'):
    """Gera relatório no formato solicitado"""
    print(f"\nGenerating report to {output_file}...")
    
    with open(output_file, 'w') as f:
        # Header
        f.write("commit,purity,mistral,gemma,dpsk\n")
        
        for hash_value in hashes:
            # Purity é sempre 'none' para estes hashes
            purity = 'none'
            
            # Buscar classificações nos modelos
            mistral_class = models['mistral'].get(hash_value, 'not_found').lower()
            gemma_class = models['gemma'].get(hash_value, 'not_found').lower() 
            dpsk_class = models['dpsk'].get(hash_value, 'not_found').lower()
            
            f.write(f"{hash_value},{purity},{mistral_class},{gemma_class},{dpsk_class}\n")
    
    print(f"Relatório salvo em {output_file}")
    
    # Mostrar primeiras 10 linhas na tela
    print("\nPrimeiras 10 linhas do relatório:")
    with open(output_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 11:  # Header + 10 linhas
                break
            print(line.strip())

def main():
    """Função principal"""
    print("=== Extração de Hashes com Purity_Analysis=NONE ===")
    
    # Carregar dados do arquivo floss_hashes
    print("Carregando dados do floss_hashes...")
    purity_df = load_purity_data()
    if purity_df is None:
        print("Falha ao carregar dados do floss_hashes. Encerrando.")
        sys.exit(1)
    
    print(f"Dados carregados: {len(purity_df)} registros")
    
    # Carregar dados dos modelos LLM
    print("\nCarregando dados dos modelos LLM...")
    models = load_llm_model_data()
    
    # Extrair hashes com purity_analysis=NONE
    print("\nExtraindo hashes com purity_analysis=NONE...")
    none_hashes = extract_none_hashes(purity_df, limit=500)
    
    if len(none_hashes) == 0:
        print("Nenhum hash encontrado com purity_analysis=NONE")
        sys.exit(1)
    
    # Gerar relatório
    print(f"\nGerando relatório para {len(none_hashes)} hashes...")
    generate_report(none_hashes, models)
    
    print(f"\n=== Relatório concluído ===")

if __name__ == "__main__":
    main()