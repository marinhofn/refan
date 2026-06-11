# Baseline TCC 2025 — Snapshot de Resultados

Este diretório contm o snapshot completo de todos os resultados produzidos durante o TCC
"Floss ou Pure? Classificando Refatorações com LLMs" (UFCG, Set/2025).

**Objetivo**: Servir como baseline imutável para comparação antes/depois da refatoração
do sistema Refan para o mestrado. Quando as análises forem repetidas com o sistema
refatorado, os resultados poderão ser comparados diretamente contra estes dados.

**Data do snapshot**: 2026-04-11
**Commit base**: af3340b (main)

---

## Estrutura

```
baseline_tcc_2025/
├── README.md                          # Este arquivo
├── TCC-JoseMarinhoFalcaoNeto-*.pdf    # Monografia completa
├── PROMPT_OTIMIZADO_ATUAL.txt         # Prompt usado nas análises
│
├── # === DADOS DE ENTRADA (INPUTS) ===
├── commits_with_refactoring.csv       # Dataset principal (11.186 commits)
├── puritychecker_detailed_classification.csv  # Baseline PurityChecker (~49k rows)
├── hashes_comuns.csv                  # Interseção purity ∩ refactoring (6.822 hashes)
│
├── # === RESULTADOS POR MODELO (CSVs finais) ===
├── llm_analysis_csv/                  # CSVs de resultado por modelo
│   ├── mistral_floss_hashes_*.csv
│   ├── mistral_latest_floss_hashes_*.csv
│   ├── deepseek-r1_8b_floss_hashes_*.csv
│   ├── deepseek-r1_8b_true_purity_*.csv
│   ├── deepseek-r1_1.5b_true_purity_*.csv
│   ├── gemma2_2b_floss_hashes_*.csv
│   ├── gemma2_2b_true_purity_*.csv
│   ├── gemma3_1b_floss_hashes_*.csv
│   ├── gemma3_4b_floss_hashes_*.csv
│   ├── gpt-oss_20b_floss_hashes_*.csv
│   ├── gpt-oss_floss_hashes_*.csv
│   └── mistral_latest_true_purity_*.csv
│
├── # === RESULTADOS CONSOLIDADOS ===
├── hashes_no_rpt_purity_with_analysis.csv      # Master com coluna llm_analysis
├── floss_hashes_no_rpt_purity_with_analysis.csv # Subset FLOSS com análises
├── true_purity_hashes_with_analysis.csv         # Subset TRUE com análises
├── llm_analysis_aggregated.csv                  # Métricas agregadas por modelo
├── complete_unified_analysis.csv                # Análise unificada todos os modelos
├── complete_unified_analysis_filtered_*.csv     # Versão filtrada
│
├── # === OUTPUTS POR MODELO (JSONs de sessão, backups) ===
├── output_models/
│   ├── mistral/analises/              # Session JSONs + CSV backups
│   ├── mistral_latest/analises/
│   ├── deepseek-r1_8b/analises/
│   ├── deepseek-r1_1.5b/analises/
│   ├── gemma2_2b/analises/
│   ├── gemma3_1b/analises/
│   ├── gemma3_4b/analises/
│   └── gpt-oss_20b/analises/
│
├── # === ANÁLISE E DISCUSSÃO (figuras do TCC) ===
├── results-discussion/
│   ├── classification_distribution_models.png   # Fig 6 do TCC
│   ├── 4-venn-complete.png                      # Fig 7 - Venn diagram
│   ├── agreement_heatmap_fixed.png              # Fig 8 - Heatmap concordância
│   ├── consensus_bar.png                        # Fig 9 - Consenso
│   ├── failed_percentages_ultimate.png          # Fig 10 - Taxa de falhas
│   ├── 05_estatisticas_gerais.csv               # Dados estatísticos
│   └── total_agreement_analysis.csv             # Concordância total
│
├── # === RELATÓRIO 3 MODELOS ===
├── analysis_three_models/
│   ├── report.html                    # Relatório HTML interativo
│   └── summary_three_models.csv       # Resumo comparativo
│
└── # === FALHAS DE PARSING JSON ===
    └── json_failures.json             # 12MB de falhas registradas
```

## Modelos Avaliados no TCC

| Modelo | Família | Parâmetros | Analyses FLOSS | Analyses TRUE |
|--------|---------|-----------|----------------|---------------|
| Mistral | Mistral | 7B | Sim | - |
| Mistral (latest) | Mistral | 7B | Sim | Sim |
| DeepSeek-R1:8b | DeepSeek | 8B | Sim | Sim |
| DeepSeek-R1:1.5b | DeepSeek | 1.5B | - | Sim |
| Gemma-2:2b | Google | 2B | Sim | Sim |
| Gemma-3:1b | Google | 1B | Sim | - |
| Gemma-3:4b | Google | 4B | Sim | - |
| GPT-OSS:20b | - | 20B | Sim | - |

## Resultados Principais (Table 2 do TCC)

| Modelo | Total Analisados | PURE | FLOSS | PURE % |
|--------|-----------------|------|-------|--------|
| Purity (baseline) | 2.728 | 978 | 1.750 | 35.85% |
| Mistral | 2.728 | 766 | 1.962 | 28.08% |
| Gemma-2:2b | 2.728 | 561 | 2.167 | 20.56% |
| DeepSeek-R1:8b | 2.728 | 201 | 2.527 | 7.37% |

## Como Usar para Comparação

Quando as análises forem repetidas com o sistema refatorado:

1. Os CSVs em `llm_analysis_csv/` contêm a coluna `llm_analysis` com a classificação final
2. Comparar classificação por classificação (hash a hash) contra os novos resultados
3. As figuras em `results-discussion/` servem como referência visual
4. O `json_failures.json` documenta todos os casos de falha para análise de melhorias
5. O `PROMPT_OTIMIZADO_ATUAL.txt` é o prompt exato usado — comparar com versões futuras

## Importante

- **NÃO modificar** nenhum arquivo neste diretório
- Este snapshot é imutável — qualquer correção deve ser documentada, não aplicada aqui
- Hardware do TCC: Windows 11 + WSL2, RTX 4070 Ti Super 16GB, Ryzen 7 5700X, 32GB DDR4
