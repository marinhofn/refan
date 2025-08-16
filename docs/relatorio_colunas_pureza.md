
# Relatório de Processamento - Colunas de Análise de Pureza

## Resumo Executivo
- **Total de hashes processados**: 6,821
- **Match rate**: 100% (todos os hashes foram encontrados no arquivo de pureza)
- **Arquivo gerado**: `csv/hashes_no_rpt_purity_with_analysis.csv`

## Distribuição das Classificações de Pureza

purity_analysis
NONE     3416
FALSE    2425
TRUE      980

## Interpretação dos Resultados

- **FALSE** (2,425 hashes): Refatoramentos considerados "floss" pelo PurityChecker
  - Pelo menos uma análise retornou FALSE para este hash
  
- **NONE** (3,416 hashes): Hashes sem análise válida
  - Todas as análises retornaram None para este hash
  
- **TRUE** (980 hashes): Refatoramentos considerados "puros" pelo PurityChecker
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
