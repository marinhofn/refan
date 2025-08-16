# 📊 Análise de Commits de Refatoramento

Sistema para análise automatizada de commits de refatoramento, classificando-os em "Pure" ou "Floss" refactoring.

## 🚀 Como Executar

### Aplicação Principal
```bash
python main.py
```

### Testes
Todos os arquivos de teste foram organizados na pasta `tests/`. Para executar:

```bash
# Teste principal (análise completa)
python tests/test_runner.py

# Teste dos contadores (funcionalidade específica)
python tests/test_counter_functionality.py

# Demonstração das melhorias
python tests/test_improvements.py
```

📝 **Consulte o arquivo `tests/README.md` para documentação detalhada dos testes.**

## 📁 Estrutura do Projeto

```
refan/
├── main.py                 # Aplicação principal
├── config.py              # Configurações
├── data_handler.py         # Manipulação de dados
├── git_handler.py          # Operações Git
├── llm_handler.py          # Interface com LLM
├── colors.py              # Cores para interface
├── requirements.txt       # Dependências
├── csv/                   # Dados CSV
├── analises/             # Resultados das análises
├── repositorios/         # Repositórios clonados
└── tests/                # 🧪 Todos os arquivos de teste
    ├── README.md         # Documentação dos testes
    ├── test_runner.py    # Teste principal
    ├── test_counter_functionality.py  # Teste dos contadores
    ├── test_improvements.py           # Demonstração
    ├── test_commits.json             # Dados de teste
    └── ...
```

## ✨ Funcionalidades Recentes

### Sistema de Contadores Melhorado
- ✅ **Consulta atual**: `[1/5], [2/5], [3/5]` - progresso da consulta específica
- ✅ **Sessão total**: `[#1], [#2], [#3]` - total de commits analisados na sessão
- ✅ **Menu informativo**: mostra progresso histórico e da sessão atual

### Interface Otimizada
- ✅ **Prompt único**: mostrado apenas uma vez por consulta
- ✅ **Resumo final**: contagem Pure/Floss ao final de cada análise
- ✅ **Organização**: arquivos de teste organizados em pasta separada

## 🔧 Configurações

Edite o arquivo `config.py` para:
- Alterar modelo LLM
- Configurar host do Ollama  
- Ajustar configurações de debug
- Modificar prompt do sistema
