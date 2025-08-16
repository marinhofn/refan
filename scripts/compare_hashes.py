#!/usr/bin/env python3
"""
Script para comparar os hashes entre hashes_no_rpt_purity.csv e commits_with_refactoring.csv
"""

import pandas as pd
import csv

def compare_hashes():
    print("Carregando arquivos...")
    
    # Carregar hashes do purity
    purity_df = pd.read_csv('csv/hashes_no_rpt_purity.csv')
    purity_hashes = set(purity_df['hash'].tolist())
    print(f"Hashes no arquivo purity: {len(purity_hashes)}")
    
    # Carregar commits do refactoring
    refactoring_df = pd.read_csv('csv/commits_with_refactoring.csv')
    
    # Criar conjunto com todos os hashes do refactoring (commit1 e commit2)
    refactoring_hashes = set()
    refactoring_hashes.update(refactoring_df['commit1'].tolist())
    refactoring_hashes.update(refactoring_df['commit2'].tolist())
    print(f"Hashes únicos no arquivo refactoring: {len(refactoring_hashes)}")
    
    # Encontrar interseção
    common_hashes = purity_hashes.intersection(refactoring_hashes)
    print(f"\nHashes em comum: {len(common_hashes)}")
    print(f"Porcentagem dos hashes purity que estão no refactoring: {len(common_hashes)/len(purity_hashes)*100:.2f}%")
    print(f"Porcentagem dos hashes refactoring que estão no purity: {len(common_hashes)/len(refactoring_hashes)*100:.2f}%")
    
    # Verificar especificamente quais hashes do purity estão em commit1 e commit2
    commit1_matches = purity_hashes.intersection(set(refactoring_df['commit1'].tolist()))
    commit2_matches = purity_hashes.intersection(set(refactoring_df['commit2'].tolist()))
    
    print(f"\nDetalhamento:")
    print(f"Hashes purity que aparecem em commit1: {len(commit1_matches)}")
    print(f"Hashes purity que aparecem em commit2: {len(commit2_matches)}")
    print(f"Hashes purity que aparecem em ambas as colunas: {len(commit1_matches.intersection(commit2_matches))}")
    
    # Salvar os hashes em comum em um arquivo
    if common_hashes:
        with open('csv/hashes_comuns.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['hash'])
            for hash_value in sorted(common_hashes):
                writer.writerow([hash_value])
        print(f"\nHashes em comum salvos em: csv/hashes_comuns.csv")
    
    # Análise adicional: mostrar alguns exemplos
    if common_hashes:
        print(f"\nPrimeiros 10 hashes em comum:")
        for i, hash_value in enumerate(sorted(common_hashes)[:10]):
            print(f"  {i+1}. {hash_value}")
    
    return {
        'purity_total': len(purity_hashes),
        'refactoring_total': len(refactoring_hashes),
        'common_total': len(common_hashes),
        'commit1_matches': len(commit1_matches),
        'commit2_matches': len(commit2_matches),
        'both_columns_matches': len(commit1_matches.intersection(commit2_matches))
    }

if __name__ == "__main__":
    results = compare_hashes()
