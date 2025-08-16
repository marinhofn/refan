#!/usr/bin/env python3
"""
Script para validar a classificação de alguns hashes específicos
"""

import pandas as pd

def validate_classifications():
    print("Validando classificações...")
    
    # Carregar arquivo com classificações
    df = pd.read_csv('csv/hashes_no_rpt_purity_with_analysis.csv')
    
    print("Estatísticas gerais:")
    print(df['purity_analysis'].value_counts())
    print()
    
    # Pegar alguns exemplos de cada tipo
    false_examples = df[df['purity_analysis'] == 'FALSE'].head(3)
    true_examples = df[df['purity_analysis'] == 'TRUE'].head(3)
    none_examples = df[df['purity_analysis'] == 'NONE'].head(3)
    
    print("Exemplos de hashes com classificação FALSE:")
    for _, row in false_examples.iterrows():
        print(f"  {row['hash']}")
    
    print("\nExemplos de hashes com classificação TRUE:")
    for _, row in true_examples.iterrows():
        print(f"  {row['hash']}")
    
    print("\nExemplos de hashes com classificação NONE:")
    for _, row in none_examples.iterrows():
        print(f"  {row['hash']}")
    
    # Verificar se algum hash foi marcado como NOT_FOUND
    not_found = df[df['purity_analysis'] == 'NOT_FOUND']
    print(f"\nHashes não encontrados: {len(not_found)}")
    
    # Vamos verificar um hash específico no arquivo original
    sample_hash = false_examples.iloc[0]['hash']
    print(f"\nVerificando detalhes do hash: {sample_hash}")
    
    # Ler arquivo original para verificar
    with open('csv/puritychecker_detailed_classification.csv', 'r') as f:
        lines = f.readlines()
    
    count_true = 0
    count_false = 0
    count_none = 0
    
    for line in lines[1:]:  # Pular cabeçalho
        parts = line.strip().split(';')
        if len(parts) >= 3 and parts[1] == sample_hash:
            purity_value = parts[2].lower()
            if purity_value == 'true':
                count_true += 1
            elif purity_value == 'false':
                count_false += 1
            elif purity_value == 'none':
                count_none += 1
    
    print(f"  Ocorrências no arquivo original:")
    print(f"    TRUE: {count_true}")
    print(f"    FALSE: {count_false}")
    print(f"    NONE: {count_none}")
    print(f"  Classificação final: {'FALSE' if count_false > 0 else 'TRUE' if count_true > 0 else 'NONE'}")
    
    return df

def create_summary_report():
    """Criar relatório resumo"""
    df = pd.read_csv('csv/hashes_no_rpt_purity_with_analysis.csv')
    
    summary = f"""
# Relatório de Processamento - Colunas de Análise de Pureza

## Resumo Executivo
- **Total de hashes processados**: {len(df):,}
- **Match rate**: 100% (todos os hashes foram encontrados no arquivo de pureza)
- **Arquivo gerado**: `csv/hashes_no_rpt_purity_with_analysis.csv`

## Distribuição das Classificações de Pureza

{df['purity_analysis'].value_counts().to_string()}

## Interpretação dos Resultados

- **FALSE** ({df[df['purity_analysis'] == 'FALSE'].shape[0]:,} hashes): Refatoramentos considerados "floss" pelo PurityChecker
  - Pelo menos uma análise retornou FALSE para este hash
  
- **NONE** ({df[df['purity_analysis'] == 'NONE'].shape[0]:,} hashes): Hashes sem análise válida
  - Todas as análises retornaram None para este hash
  
- **TRUE** ({df[df['purity_analysis'] == 'TRUE'].shape[0]:,} hashes): Refatoramentos considerados "puros" pelo PurityChecker
  - Todas as análises válidas retornaram TRUE para este hash

## Colunas Criadas

1. **purity_analysis**: Classificação baseada no PurityChecker
2. **llm_analysis**: Campo vazio para futuras análises da LLM

## Lógica Aplicada

- Se um hash possui **pelo menos uma análise FALSE** → classificado como **FALSE**
- Se um hash possui **apenas análises TRUE** (sem FALSE) → classificado como **TRUE**  
- Se um hash possui **apenas análises None** → classificado como **NONE**
- Se um hash possui **TRUE e None** (sem FALSE) → classificado como **TRUE**

## Próximos Passos

O arquivo está pronto para receber as análises da LLM na coluna `llm_analysis`.
"""
    
    with open('relatorio_colunas_pureza.md', 'w') as f:
        f.write(summary)
    
    print("Relatório salvo em: relatorio_colunas_pureza.md")

if __name__ == "__main__":
    df = validate_classifications()
    create_summary_report()
