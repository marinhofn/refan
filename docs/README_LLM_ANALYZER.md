# LLM Purity Analyzer

Sistema para análise automática de commits de refatoramento usando LLM, preenchendo a coluna `llm_analysis` no arquivo de análise de pureza.

## ✨ Funcionalidades Implementadas

### ✅ 1. Análise LLM Automatizada
- Busca commits no arquivo `commits_with_refactoring.csv`
- Obtém diffs dos repositórios Git
- Analisa com LLM otimizada (Ollama)
- Classifica como `PURE` ou `FLOSS`
- Preenche coluna `llm_analysis` no CSV

### ✅ 2. Persistência de Dados
- Salva análises no arquivo CSV principal
- Cria backups automáticos antes de modificações
- Gera logs detalhados em JSON (pasta `analises/`)
- Rastreia falhas de JSON para debugging

### ✅ 3. Opções de Execução
- **Número específico**: Analisar N commits
- **Todos os commits**: Análise completa do dataset
- **Filtros por Purity**: TRUE, FALSE, NONE
- **Skip analisados**: Evita reprocessamento

### ✅ 4. Handlers Otimizados
- Usa `optimized_llm_handler.py` com prompt melhorado
- Suporte a diffs grandes via arquivos temporários
- Parser JSON robusto com correção automática
- Tratamento de erros e timeouts

## 🚀 Como Usar

### Modo Interativo (Recomendado)
```bash
cd /home/marinhofn/tcc/refan
python run_llm_analysis.py
```

### Linha de Comando
```bash
# Testar com 1 commit
python run_llm_analysis.py --action test

# Analisar 10 commits
python run_llm_analysis.py --max-commits 10

# Analisar apenas commits FALSE do Purity
python run_llm_analysis.py --purity-filter FALSE

# Ver resumo das análises
python run_llm_analysis.py --action summary

# Analisar todos os commits (cuidado!)
python run_llm_analysis.py --max-commits 0
```

### Scripts Específicos
```bash
# Teste rápido
python test_llm_purity_analyzer.py

# Debug detalhado
python debug_analyzer.py

# Análise direta
python llm_purity_analyzer.py
```

## 📊 Estrutura dos Arquivos

### Entrada
- `csv/hashes_no_rpt_purity_with_analysis.csv` - Arquivo principal com colunas:
  - `hash` - Hash do commit
  - `purity_analysis` - Classificação do PurityChecker (TRUE/FALSE/NONE)
  - `llm_analysis` - Classificação da LLM (PURE/FLOSS/FAILED/ERROR)

### Saída
- Mesmo arquivo CSV atualizado
- `analises/llm_purity_analysis_YYYY-MM-DD_HH-MM-SS.json` - Log da sessão
- Backups automáticos com timestamp

## 🎯 Estatísticas Atuais

```
Total de hashes: 6.821
- FALSE (Purity): 2.425 hashes
- NONE (Purity):  3.416 hashes  
- TRUE (Purity):    980 hashes

Análises LLM realizadas: 1+ (testado e funcionando)
Taxa de sucesso: 100% (nos testes)
```

## 🔧 Configurações

### LLM (Ollama)
- Modelo: Configurado em `config.py`
- Host: localhost padrão
- Timeout: Adaptativo baseado no tamanho do diff
- Contexto: 8192 tokens

### Processamento
- Diff pequeno (<100k chars): Envio direto
- Diff grande: Arquivo temporário
- Parser JSON: Auto-correção de aspas
- Backups: Automáticos a cada salvamento

## 🚨 Considerações Importantes

1. **Performance**: Análise completa pode levar horas
2. **Espaço**: Diffs grandes geram arquivos temporários
3. **Dependências**: Requer Ollama rodando e repositórios clonados
4. **Backup**: Sempre mantém versões anteriores do CSV

## 📈 Próximos Passos

1. Executar análise em lote dos commits FALSE do Purity
2. Comparar resultados LLM vs PurityChecker
3. Gerar relatórios de concordância/discordância
4. Análise estatística dos resultados

## 🛠️ Arquivos Principais

- `llm_purity_analyzer.py` - Classe principal do analisador
- `run_llm_analysis.py` - Interface principal de uso
- `optimized_llm_handler.py` - Handler LLM otimizado
- `optimized_prompt.py` - Prompt especializado
- `test_llm_purity_analyzer.py` - Testes básicos

## ✅ Status

**SISTEMA IMPLEMENTADO E FUNCIONAL** ✨

Pronto para análise em escala dos 6.821 commits de refatoramento!
