#!/usr/bin/env python3
"""
Script para análise detalhada dos hashes em comum
"""

import pandas as pd

def detailed_analysis():
    print("Análise detalhada dos hashes em comum...")
    
    # Carregar dados
    purity_df = pd.read_csv('csv/hashes_no_rpt_purity.csv')
    refactoring_df = pd.read_csv('csv/commits_with_refactoring.csv')
    
    purity_hashes = set(purity_df['hash'].tolist())
    
    # Encontrar alguns exemplos de matches
    print("\n=== EXEMPLOS DE MATCHES ===")
    
    # Pegar os primeiros 5 hashes do purity e ver onde aparecem no refactoring
    sample_hashes = list(purity_hashes)[:5]
    
    for hash_val in sample_hashes:
        print(f"\nHash: {hash_val}")
        
        # Verificar se aparece em commit1
        commit1_matches = refactoring_df[refactoring_df['commit1'] == hash_val]
        if not commit1_matches.empty:
            print(f"  Aparece como commit1 em {len(commit1_matches)} linha(s):")
            for idx, row in commit1_matches.head(3).iterrows():
                print(f"    Linha {row['ind']}: {row['project_name']} - commit1={hash_val}, commit2={row['commit2']}")
        
        # Verificar se aparece em commit2
        commit2_matches = refactoring_df[refactoring_df['commit2'] == hash_val]
        if not commit2_matches.empty:
            print(f"  Aparece como commit2 em {len(commit2_matches)} linha(s):")
            for idx, row in commit2_matches.head(3).iterrows():
                print(f"    Linha {row['ind']}: {row['project_name']} - commit1={row['commit1']}, commit2={hash_val}")
    
    # Estatísticas por projeto
    print("\n=== ESTATÍSTICAS POR PROJETO ===")
    
    # Criar lista de todos os hashes do refactoring com informação da coluna
    refactoring_hashes_info = []
    
    for idx, row in refactoring_df.iterrows():
        refactoring_hashes_info.append({
            'hash': row['commit1'],
            'column': 'commit1',
            'project': row['project_name'],
            'line': row['ind']
        })
        refactoring_hashes_info.append({
            'hash': row['commit2'],
            'column': 'commit2',
            'project': row['project_name'],
            'line': row['ind']
        })
    
    refactoring_info_df = pd.DataFrame(refactoring_hashes_info)
    
    # Filtrar apenas os hashes que estão no purity
    common_info = refactoring_info_df[refactoring_info_df['hash'].isin(purity_hashes)]
    
    # Estatísticas por projeto
    project_stats = common_info.groupby('project').agg({
        'hash': 'count',
        'column': lambda x: f"commit1: {sum(x=='commit1')}, commit2: {sum(x=='commit2')}"
    }).rename(columns={'hash': 'total_matches', 'column': 'distribution'})
    
    print(project_stats.head(10))
    
    print(f"\nTotal de projetos com matches: {len(project_stats)}")
    print(f"Projeto com mais matches: {project_stats['total_matches'].idxmax()} ({project_stats['total_matches'].max()} matches)")

if __name__ == "__main__":
    detailed_analysis()
