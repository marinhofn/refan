# csv/ — dicionário e política de dados

> Documento previsto na Fase H9 (`HARDENING_PLAN.md`). Última atualização: 2026-07-01.
> Contagens conferidas nessa data.

Três categorias de arquivo convivem aqui, com políticas distintas:

| Categoria | Política |
|-----------|----------|
| **Insumos oficiais** | Imutáveis. Nunca editar — nem manualmente, nem por código. |
| **Masters de trabalho** | Mutados **apenas** pela ferramenta (coluna `llm_analysis` preenchida pelo `LLMPurityAnalyzer`). Backups automáticos por sessão em `output/models/<modelo>/analises/`. |
| **Derivados** | Reconstruíveis a partir dos anteriores. Datados vivem em `csv/derived/`. |

## Insumos oficiais (imutáveis)

| Arquivo | Linhas | Colunas | Descrição |
|---------|--------|---------|-----------|
| `commits_with_refactoring.csv` | 11.186 | `ind,commit1,commit2,project,project_name` | Dataset base: pares de commits (antes/depois) com refatoração detectada, por projeto. Fonte de todo o pipeline. |
| `puritychecker_detailed_classification.csv` | 49.336 | `id;commit;purity;purity_description;refactoring_type;refactoring_description` (separador `;`) | Saída bruta do Purity Checker: **uma linha por refatoração detectada** — um commit aparece múltiplas vezes, possivelmente com classificações conflitantes. A consolidação por commit (regra FALSE>TRUE) é feita em runtime pelo `purity_handler` — ver `docs/REPRODUCIBILITY.md` §4. |

## Masters de trabalho (mutados pela ferramenta)

Todos com schema `hash,purity_analysis,llm_analysis`; `llm_analysis` começa vazia e é
preenchida (`pure`/`floss`/`FAILED`/`ERROR`) conforme as análises rodam.

| Arquivo | Linhas | Escopo |
|---------|--------|--------|
| `hashes_no_rpt_purity_with_analysis.csv` | 6.821 | Todos os commits únicos (sem repetição) com classificação Purity consolidada (`TRUE`/`FALSE`/`None`). |
| `floss_hashes_no_rpt_purity_with_analysis.csv` | 5.841 | Subconjunto com Purity `FALSE`/`None` — **master default** da pipeline (`LLMPurityAnalyzer`). |
| `true_purity_hashes_with_analysis.csv` | 980 | Subconjunto com Purity `TRUE`. |

(5.841 + 980 = 6.821 — os dois subconjuntos particionam o conjunto total.)

## Derivados

| Arquivo | Linhas | Situação |
|---------|--------|----------|
| `hashes_no_rpt_purity.csv` | 6.821 | Lista de hashes únicos (uma coluna) que originou os masters. Mantido por ser insumo intermediário citado em scripts. |
| `hashes_comuns.csv` | 6.821 | **Mesmo conjunto** de hashes do arquivo acima (verificado por diff em 2026-07-01); redundante, mantido no lugar porque `scripts/compare_hashes.py` e `scripts/research/relatorio_final.py` o referenciam. Candidato à consolidação na Fase E5. |
| `llm_analysis_aggregated.csv` | 11 | Agregado por modelo (contagens e concordância) gerado por `scripts/research/`. Referenciado por 2 scripts; regenerável. |
| `llm_analysis_csv/` | — | Resultados por modelo da era TCC. **Somente leitura histórica**: as cópias canônicas estão em `baseline_tcc_2025/llm_analysis_csv/` (LFS + manifesto). Nota: o diretório consta no `.gitignore` (regra adicionada depois), mas os arquivos permanecem rastreados por antecederem a regra. |
| `derived/` | — | Derivados **datados** (snapshots de comparações e análises pontuais). Nada aqui é insumo de código — verificado por busca de referências antes de cada movimentação. |

Conteúdo atual de `derived/`:

- `complete_unified_analysis_filtered_2025-09-01_11-59-17.csv` — análise unificada filtrada (sessão de 2025-09-01).
- `dual_classification_comparison_2025-08-14_19-50-28.csv` — comparação dual de classificações.
- `purity_llm_comparison_2025-08-14_13-18-24.csv`, `purity_llm_comparison_2025-08-14_14-16-11.csv` — comparações Purity×LLM pontuais.
- `original_hashes_no_rpt_purity_with_analysis.csv` — snapshot pré-análise do master total (estado original preservado à época).

## Regras operacionais

1. **Nunca** editar insumos oficiais. Qualquer correção de dados exige novo arquivo +
   registro da transformação (rastreabilidade fim-a-fim).
2. Masters só mudam via ferramenta; para "zerar" um master, use os backups de sessão
   (nunca sobrescreva à mão).
3. Novos derivados datados nascem em `csv/derived/` (padrão `nome_YYYY-MM-DD_HH-MM-SS.csv`).
4. Encoding UTF-8 em todos os arquivos; atenção ao separador `;` do CSV do Purity.
