# Sistema de Visualização e Análise LLM vs Purity

## Resumo das Funcionalidades Implementadas

### ✅ 1. Adaptação da Visualização para Dados LLM
- **Arquivo Principal**: `llm_visualization_handler.py`
- **Funcionalidade**: Sistema completo de visualização adaptado para comparar classificações Purity vs LLM
- **Recursos**:
  - Carregamento automático dos dados de comparação (`purity_llm_comparison_*.csv`)
  - Análise de concordância/discordância entre classificações
  - Matriz de confusão interativa
  - Análise por repositório
  - Distribuição de classificações
  - Timeline das sessões de análise

### ✅ 2. Sistema de Barra de Progresso
- **Arquivo**: `llm_purity_analyzer.py` (classe `ProgressBar`)
- **Funcionalidade**: Barra de progresso em tempo real durante análise LLM
- **Recursos**:
  - Progresso visual com barra ASCII
  - Tempo decorrido e tempo estimado para conclusão
  - Taxa de processamento (commits/tempo)
  - Atualização contínua durante a análise
  - Interface limpa e informativa

### ✅ 3. Funcionalidades de Exportação Avançadas
- **Formatos Suportados**:
  - **CSV**: Dados brutos para análise em planilhas
  - **JSON**: Dados completos com sessões de análise e metadados
  - **Excel**: Workbook multi-sheet com dados e estatísticas
  - **HTML**: Dashboard interativo completo
  - **PNG**: Gráficos individuais para apresentações
- **Recursos**:
  - Exportação individual ou em pacote completo
  - Metadados e estatísticas incluídos
  - README automático com instruções
  - Organização em diretórios estruturados

### ✅ 4. Dashboard Interativo com Filtros
- **Funcionalidade**: Dashboard HTML completo com recursos interativos
- **Filtros Disponíveis**:
  - Por repositório
  - Por tipo de classificação (Purity/LLM)
  - Por status de concordância
  - Combinação múltipla de filtros
- **Recursos Interativos**:
  - Filtros em tempo real
  - Estatísticas dinâmicas
  - Reset de filtros
  - Exportação da view atual
  - Interface responsiva e moderna

## Estrutura de Arquivos Criados

```
📁 Sistema de Visualização LLM
├── 📄 llm_visualization_handler.py      # Handler principal de visualização
├── 📄 demo_llm_visualization.py         # Script de demonstração interativo
├── 📄 llm_purity_analyzer.py           # Analyzer com barra de progresso
└── 📁 Pacotes de Exportação
    ├── 📄 dashboard.html               # Dashboard interativo
    ├── 📄 dados.csv                   # Dados em formato CSV
    ├── 📄 dados.json                  # Dados completos JSON
    ├── 📄 dados.xlsx                  # Workbook Excel
    ├── 📄 README.md                   # Instruções de uso
    └── 📁 charts/                     # Gráficos individuais
        ├── 📄 agreement_overview.html
        ├── 📄 confusion_matrix.html
        ├── 📄 repository_analysis.html
        ├── 📄 classification_distribution.html
        ├── 📄 timeline_analysis.html
        └── 📄 progress_dashboard.html
```

## Tipos de Visualizações Disponíveis

### 1. **Overview de Concordância**
- Gráfico de pizza mostrando % de concordância vs discordância
- Estatísticas de taxa de concordância
- Contadores de total de comparações

### 2. **Matriz de Confusão**
- Heatmap comparando classificações Purity vs LLM
- Valores absolutos e percentuais
- Identificação de padrões de classificação

### 3. **Análise por Repositório**
- Taxa de concordância por repositório
- Número total de commits por repositório
- Scatter plot de classificações PURE
- Tabela detalhada de estatísticas

### 4. **Distribuição de Classificações**
- Gráficos de pizza comparativos (Purity vs LLM)
- Contagem de cada tipo de classificação
- Visualização lado a lado

### 5. **Timeline de Análise**
- Progresso das sessões de análise ao longo do tempo
- Taxa de sucesso por sessão
- Velocidade de processamento
- Progresso cumulativo

### 6. **Dashboard de Progresso**
- Indicador gauge de progresso geral
- Status de análise (analisado vs restante)
- Performance de sessões recentes
- Estimativas de conclusão

## Como Usar o Sistema

### 1. **Demonstração Interativa**
```bash
python demo_llm_visualization.py
```

### 2. **Criar Dashboard Completo**
```python
from llm_visualization_handler import LLMVisualizationHandler
handler = LLMVisualizationHandler()
dashboard_path = handler.create_comprehensive_dashboard()
```

### 3. **Exportar Dados**
```python
# Exportar em formato específico
exported = handler.export_analysis_data("csv")  # ou "json", "excel", "all"

# Criar pacote completo
package_path = handler.create_export_package()
```

### 4. **Análise com Barra de Progresso**
```python
from llm_purity_analyzer import LLMPurityAnalyzer
analyzer = LLMPurityAnalyzer()
results = analyzer.analyze_commits(max_commits=100)
```

## Requisitos e Dependências

### Dependências Principais
- `pandas`: Manipulação de dados
- `plotly`: Visualizações interativas
- `numpy`: Operações numéricas
- `openpyxl`: Exportação Excel (opcional)
- `kaleido`: Exportação PNG (opcional)

### Instalação
```bash
pip install pandas plotly numpy openpyxl kaleido
```

## Dados de Entrada Esperados

### CSV de Comparação
Arquivo: `csv/purity_llm_comparison_*.csv`
```
commit_hash,purity_classification,llm_classification,llm_justification,agreement,repository,commit_message
```

### Sessões de Análise
Diretório: `analises/`
Arquivos: `llm_purity_analysis_*.json`

## Funcionalidades Especiais

### 1. **Filtros Interativos**
- Filtro por repositório
- Filtro por concordância
- Filtro por tipo de classificação
- Combinação múltipla de filtros
- Reset automático

### 2. **Exportação Flexível**
- Múltiplos formatos simultaneamente
- Pacotes organizados com README
- Metadados incluídos
- Compatibilidade com ferramentas externas

### 3. **Progresso em Tempo Real**
- Barra de progresso visual
- Estimativas de tempo
- Taxa de processamento
- Salvamento incremental

### 4. **Interface Moderna**
- Design responsivo
- Gradientes e sombras
- Cores temáticas
- UX intuitiva

## Estatísticas dos Dados Atuais

- **Total de Comparações**: 20 commits
- **Taxa de Concordância**: 5.0%
- **Repositórios Analisados**: 9
- **Sessões de Análise**: 6
- **Classificações Purity**: FLOSS (20)
- **Classificações LLM**: PURE (17), NOT_ANALYZED (2), FLOSS (1)

## Próximos Passos Recomendados

1. **Aumentar Dataset**: Executar mais análises LLM para aumentar o número de comparações
2. **Refinamento de Filtros**: Adicionar filtros por data, tamanho de diff, etc.
3. **Análise Estatística**: Implementar testes estatísticos de significância
4. **Machine Learning**: Usar dados para treinar modelos de classificação
5. **Relatórios Automáticos**: Geração automática de relatórios em PDF

---

**Sistema criado com sucesso e totalmente funcional!** 🎉

Todas as funcionalidades solicitadas foram implementadas:
- ✅ Visualização adaptada para dados LLM
- ✅ Dashboard interativo com filtros
- ✅ Múltiplas opções de exportação
- ✅ Barra de progresso em tempo real
- ✅ Interface moderna e intuitiva
