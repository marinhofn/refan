# Funcionalidades de Visualização Interativa

## Visão Geral

O sistema agora inclui funcionalidades completas de visualização interativa dos dados de análise de refatoramento, permitindo gerar gráficos detalhados e dashboards abrangentes.

## Características Principais

### 📊 Dashboard Abrangente
- **Gráfico de Pizza**: Distribuição de tipos de refatoramento (Pure vs Floss)
- **Gráficos de Barras**: Análise por repositório
- **Timeline**: Evolução temporal das análises
- **Histogramas**: Distribuição de tamanhos de diff
- **Top 10**: Repositórios com mais commits analisados
- **Tabela de Estatísticas**: Métricas resumidas

### 💾 Formatos de Saída
- **HTML Interativo**: Gráficos navegáveis com zoom, hover e filtros
- **PNG Estático**: Imagens de alta qualidade para relatórios
- **Exibição Dinâmica**: Visualização direta no navegador

### 📈 Visualizações Específicas
- **Comparação LLM vs Purity**: Gráficos de concordância e matrizes de confusão
- **Análise de Performance**: Estatísticas de classificação
- **Distribuições Detalhadas**: Múltiplas perspectivas dos dados

## Como Usar

### Via Menu Principal
```bash
python main.py
# Escolha opção 7: Gerar visualizações interativas dos dados analisados
# Escolha opção 8: Visualizar comparação LLM vs Purity
```

### Via Scripts Diretos
```bash
# Teste básico
python test_visualization.py

# Demonstração completa
python demo_visualization.py
```

### Via Código
```python
from visualization_handler import VisualizationHandler

# Criar handler
viz = VisualizationHandler()

# Gerar dashboard completo
viz.create_comprehensive_dashboard(save_html=True, save_image=True)

# Obter estatísticas
stats = viz.get_summary_stats()
```

## Dependências

```bash
pip install plotly kaleido
```

**Nota**: Para salvar PNG, é necessário ter Google Chrome instalado.

## Estrutura dos Arquivos Gerados

### Dashboard Principal
- `dashboard_refatoramento_YYYY-MM-DD_HH-MM-SS.html`
- `dashboard_refatoramento_YYYY-MM-DD_HH-MM-SS.png`

### Comparação LLM vs Purity
- `comparacao_llm_purity_YYYY-MM-DD_HH-MM-SS.html`
- `comparacao_llm_purity_YYYY-MM-DD_HH-MM-SS.png`

## Dados Analisados

O sistema automaticamente carrega e combina dados de:
- `analyzed_commits.json`: Arquivo principal de commits analisados
- `analises/analise_*.json`: Arquivos individuais de análise
- Remove duplicatas automaticamente por commit hash

## Estatísticas Incluídas

- Total de commits analisados
- Número de repositórios únicos
- Distribuição Pure vs Floss (quantidade e percentual)
- Repositório com mais commits
- Tamanho médio de diffs (se disponível)
- Níveis de confiança mais comuns (se disponível)

## Recursos Técnicos

### Tecnologias
- **Plotly**: Gráficos interativos de alta qualidade
- **Pandas**: Processamento eficiente de dados
- **Kaleido**: Geração de imagens estáticas
- **Chrome**: Renderização para PNG

### Tratamento de Erros
- Verificação automática de dados disponíveis
- Fallbacks para gráficos alternativos
- Mensagens informativas de erro
- Recuperação graceful de falhas

### Performance
- Carregamento otimizado de grandes volumes de dados
- Remoção automática de duplicatas
- Processamento em lotes para eficiência
- Cache de dados carregados

## Exemplos de Uso

### Análise Rápida
```python
# Carregar e mostrar estatísticas básicas
viz = VisualizationHandler()
print(viz.get_summary_stats())
```

### Dashboard Completo
```python
# Gerar dashboard com todas as opções
viz.create_comprehensive_dashboard(
    save_html=True,    # Arquivo interativo
    save_image=True    # Imagem estática
)
```

### Comparação Específica
```python
# Analisar comparação LLM vs Purity (requer dados de comparação)
viz.create_comparison_chart(comparison_data)
```

---

**Desenvolvido por**: Sistema de Análise de Refatoramento  
**Data**: Agosto 2025  
**Versão**: 1.0
