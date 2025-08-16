# Sistema de Análise de Refatoramento

Sistema reorganizado para análise de commits de refatoramento usando LLMs (Large Language Models) com comparação aos resultados do Purity Checker.

## Estrutura do Projeto

```
refan/
├── src/                          # Código principal do sistema
│   ├── core/                     # Módulos fundamentais
│   │   ├── config.py             # Configurações do sistema
│   │   ├── main.py               # Interface principal completa
│   │   └── menu_analysis.py      # Interface LLM especializada
│   ├── handlers/                 # Manipuladores de dados
│   │   ├── data_handler.py       # Manipulação de CSV
│   │   ├── git_handler.py        # Operações Git
│   │   ├── llm_handler.py        # Comunicação com LLM
│   │   ├── purity_handler.py     # Dados do Purity Checker
│   │   ├── visualization_handler.py  # Visualizações
│   │   └── llm_visualization_handler.py  # Visualizações LLM
│   ├── analyzers/                # Analisadores especializados
│   │   ├── llm_purity_analyzer.py    # Analisador LLM principal
│   │   ├── optimized_llm_handler.py  # Handler otimizado
│   │   └── optimized_prompt.py       # Prompts otimizados
│   └── utils/                    # Utilitários
│       └── colors.py             # Formatação de cores
├── scripts/                      # Scripts utilitários
│   ├── demos/                    # Scripts de demonstração
│   │   ├── demo_visualization.py
│   │   └── demo_llm_visualization.py
│   ├── analysis/                 # Scripts de análise
│   │   ├── run_complete_analysis.py
│   │   ├── run_llm_analysis.py
│   │   ├── analyze_existing_classifications.py
│   │   └── analyze_dual_classifications.py
│   └── *.py                      # Outros utilitários
├── tests/                        # Testes do sistema
├── output/                       # Resultados organizados por modelo
│   ├── models/
│   │   └── mistral/              # Modelo Mistral (padrão)
│   │       ├── analyses/         # Análises JSON/CSV
│   │       ├── dashboards/       # Dashboards HTML/PNG
│   │       ├── comparisons/      # Comparações LLM vs Purity
│   │       ├── analises/         # Análises individuais
│   │       └── analises_completas/  # Análises completas
│   └── temp/                     # Arquivos temporários
├── configs/                      # Arquivos de configuração
├── docs/                         # Documentação
├── csv/                          # Dados de entrada
├── repositorios/                 # Repositórios clonados
└── refan.py                      # Script de entrada unificado
```

## Como Usar

### 1. Entrada Unificada (Recomendado)

```bash
python refan.py
```

O script de entrada oferece três opções:
1. **Menu interativo completo** - Interface principal com todas as funcionalidades
2. **Menu de análise LLM** - Interface especializada para análises LLM
3. **Linha de comando** - Modo direto (em desenvolvimento)

### 2. Execução Direta

Se preferir executar diretamente:

```bash
# Interface principal
python -m src.core.main

# Interface LLM
python -m src.core.menu_analysis
```

## Organização por Modelo LLM

O sistema agora organiza automaticamente os resultados por modelo LLM:

```
output/models/{modelo}/
├── analyses/          # Análises individuais (.json)
├── dashboards/        # Visualizações (.html, .png)
├── comparisons/       # Comparações com Purity (.json)
├── analises/          # Análises em lote
└── analises_completas/  # Análises completas
```

### Modelos Suportados

- **mistral** (padrão) - Mistral via Ollama
- Facilmente extensível para GPT, Claude, etc.

## Configuração

### Alterando o Modelo LLM

Edite `src/core/config.py`:

```python
LLM_MODEL = "gpt-4"  # Altere aqui
```

O sistema criará automaticamente as pastas para o novo modelo.

### Caminhos Dinâmicos

O sistema usa caminhos dinâmicos baseados no modelo atual:

```python
from src.core.config import get_model_paths

# Obter caminhos para modelo específico
paths = get_model_paths("gpt-4")
analises_dir = paths["ANALISES_DIR"]
```

## Funcionalidades Principais

### Interface Principal (`main.py`)
- Análise de commits individuais ou em lote
- Comparação com resultados do Purity
- Visualizações interativas
- Análise com handler otimizado
- Verificação de duplicatas

### Interface LLM (`menu_analysis.py`)
- Análise rápida (10 commits)
- Análise de lote (50 commits)
- Filtros por Purity
- Análise completa automática
- Estatísticas detalhadas

## Requisitos

```bash
pip install -r requirements.txt
```

- pandas
- requests
- plotly
- ollama (para Mistral local)

## Estrutura de Dados

### Entrada
- `csv/commits_with_refactoring.csv` - Dataset principal
- `csv/puritychecker_detailed_classification.csv` - Dados do Purity

### Saída
- Análises JSON com estrutura padronizada
- Dashboards HTML interativos
- Relatórios de comparação
- Logs de commits analisados

## Migração da Versão Anterior

O sistema foi completamente reorganizado. Scripts de migração automática foram executados para:

1. ✅ Mover arquivos para estrutura modular
2. ✅ Corrigir imports automaticamente
3. ✅ Reorganizar resultados por modelo
4. ✅ Criar sistema de entrada unificado

## Extensibilidade

### Adicionando Novo Modelo LLM

1. Configure o modelo em `config.py`
2. O sistema criará automaticamente as pastas
3. Implemente adapter em `llm_handler.py` se necessário

### Adicionando Nova Análise

1. Crie novo analisador em `src/analyzers/`
2. Registre no sistema de configuração
3. Adicione ao menu principal

## Desenvolvimento

### Executando Testes

```bash
# Executar todos os testes
python -m pytest tests/

# Teste específico
python tests/test_specific.py
```

### Debug

O sistema inclui logs detalhados e modo debug configurável em `config.py`.

## Contribuição

1. Mantenha a estrutura modular
2. Use imports relativos corretos
3. Organize resultados por modelo
4. Documente mudanças significativas
