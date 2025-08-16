# Relatório de Comparação de Hashes

## Resumo Executivo

**RESULTADO PRINCIPAL: 100% dos hashes do arquivo `hashes_no_rpt_purity.csv` estão presentes no arquivo `commits_with_refactoring.csv`**

## Números Detalhados

- **Hashes no arquivo purity**: 6.821
- **Hashes únicos no arquivo refactoring**: 11.188 (considerando commit1 e commit2)
- **Hashes em comum**: 6.821 (100% dos hashes do purity)
- **Porcentagem de cobertura**: 100% dos hashes do purity estão no refactoring
- **Porcentagem reversa**: 60.97% dos hashes do refactoring estão no purity

## Distribuição por Colunas

- **Hashes que aparecem em commit1**: 3.146
- **Hashes que aparecem em commit2**: 6.821
- **Hashes que aparecem em ambas as colunas**: 3.146

## Observações Importantes

1. **Match perfeito**: Todos os hashes filtrados do `puritychecker_detailed_classification.csv` têm correspondência no arquivo de refatorações.

2. **Predominância em commit2**: A maioria dos hashes aparece na coluna `commit2`, sugerindo que os commits analisados pelo PurityChecker são principalmente os commits "depois" das refatorações.

3. **Alguns hashes aparecem múltiplas vezes**: Alguns hashes aparecem tanto como commit1 quanto como commit2, indicando que podem fazer parte de sequências de refatorações.

## Projetos com Mais Matches

- **cassandra**: 4.183 matches
- **BuildCraft**: 1.184 matches
- **AndEngine**: 12 matches

## Arquivos Gerados

- `csv/hashes_comuns.csv`: Contém todos os 6.821 hashes em comum entre os dois arquivos

## Conclusão

O mapeamento entre os arquivos é **perfeito** - todos os hashes que aparecem no `puritychecker_detailed_classification.csv` (e que foram filtrados para o `hashes_no_rpt_purity.csv`) estão presentes no arquivo `commits_with_refactoring.csv`. Isso indica que os dois datasets são completamente compatíveis para análises comparativas.
