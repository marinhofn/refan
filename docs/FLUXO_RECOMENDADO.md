# Fluxo Recomendado para Análise Completa com Prompt Otimizado

## Visão Geral

Este documento descreve o **fluxo recomendado** para analisar todos os dados utilizando o prompt otimizado e realizar comparações completas com o Purity Checker.

## 🎯 Objetivo

Realizar análise completa e comparação entre:
- **LLM com Prompt Otimizado**: Análises mais precisas com indicadores técnicos
- **Purity Checker**: Ferramenta de referência para classificação de refatoramento
- **Dados sem filtros**: Considerando todos os commits que fazem match

## 📋 Fluxo Recomendado

### Etapa 1: Análise com Prompt Otimizado
```
Opção 5: Analisar quantidade específica com PROMPT OTIMIZADO
```

**Características:**
- Usa `OptimizedLLMHandler` com prompt técnico aprimorado
- Suporte a diffs grandes (acima de 100k chars)
- Indicadores técnicos baseados em padrões do Purity
- Maior precisão na classificação
- Tratamento robusto de erros

**Recomendação:**
- Comece com pequenos lotes (ex: 50-100 commits)
- Use opção "pular commits analisados" para continuar progressivamente
- Monitore a qualidade das análises

### Etapa 2: Comparação LLM vs Purity (SEM FILTROS)
```
Opção 6: Comparar análises LLM com Purity (escolher quantidade)
Opção 7: Comparar análises LLM com Purity (todos os commits)
```

**Características:**
- **REMOVE TODOS OS FILTROS** aplicados anteriormente
- Considera **TODOS** os commits que fazem match nas planilhas
- Inclui commits **floss** e **pure** do Purity
- Permite escolher handler (padrão ou otimizado) para commits faltantes
- Gera estatísticas completas de concordância

### Etapa 3: Visualização e Análise
```
Opção 8: Gerar visualizações interativas dos dados analisados
Opção 9: Visualizar comparação LLM vs Purity
```

## 🔄 Fluxo Detalhado Passo a Passo

### 1. Preparação Inicial
1. Execute `python main.py`
2. Verifique o status no menu (commits já analisados)
3. Decida a estratégia: começar do zero ou continuar análises

### 2. Análise Progressiva com Prompt Otimizado
```bash
# Escolha opção 5
5. Analisar quantidade específica com PROMPT OTIMIZADO

# Exemplo de progressão:
- 1ª execução: 50 commits
- 2ª execução: 100 commits  
- 3ª execução: 200 commits
- Continue até analisar quantidade desejada
```

**Vantagens:**
- Análises de alta qualidade
- Controle fino do progresso
- Possibilidade de interrupção segura
- Recuperação de falhas

### 3. Comparação Abrangente com Purity
```bash
# Para quantidade específica:
6. Comparar análises LLM com Purity (escolher quantidade)
# Digite: quantidade desejada (ex: 500)

# Para análise completa:
7. Comparar análises LLM com Purity (todos os commits)
```

**O que acontece internamente:**
1. Carrega **TODOS** os dados do Purity (sem filtros)
2. Identifica commits **floss** + **pure**
3. Verifica quais já foram analisados pelo LLM
4. Oferece analisar commits faltantes
5. Permite escolher handler (padrão ou otimizado)
6. Gera comparação completa
7. Salva estatísticas detalhadas

### 4. Análise de Resultados
```bash
# Visualização interativa:
8. Gerar visualizações interativas dos dados analisados

# Comparação específica:
9. Visualizar comparação LLM vs Purity
```

## 📊 Dados Gerados

### Arquivos de Análise LLM
- `analise_YYYY-MM-DD_HH-MM-SS.json`: Análises individuais
- `analyzed_commits.json`: Consolidado de todas as análises

### Arquivos de Comparação
- `comparacao_llm_purity_YYYY-MM-DD_HH-MM-SS.json`: Dados de comparação
- Estatísticas de concordância/discordância
- Distribuição por tipo de refatoramento

### Visualizações
- `dashboard_refatoramento_*.html`: Dashboard interativo
- `dashboard_refatoramento_*.png`: Imagem estática
- `comparacao_llm_purity_*.html`: Comparação específica

## ⚡ Funcionalidades Especiais

### 1. Sem Filtros na Comparação Purity
- **Antes**: Apenas commits floss filtrados
- **Agora**: TODOS os commits (floss + pure) que fazem match
- Comparação mais abrangente e realista

### 2. Escolha de Handler Dinâmica
```
Durante a comparação:
"Usar handler otimizado para análise? (s/n)"
```
- **s**: Usa `OptimizedLLMHandler` (recomendado)
- **n**: Usa `LLMHandler` padrão

### 3. Análise Progressiva
- Continue de onde parou
- Pule commits já analisados
- Controle total do progresso

## 🎯 Estratégias Recomendadas

### Para Pesquisa Acadêmica:
1. **Fase 1**: Análise piloto (100-200 commits) com prompt otimizado
2. **Fase 2**: Análise expandida (500-1000 commits)
3. **Fase 3**: Comparação completa com Purity
4. **Fase 4**: Análise de resultados e visualizações

### Para Análise Completa:
1. Use opção 5 para analisar todos os commits disponíveis
2. Use opção 7 para comparação completa com Purity
3. Use opções 8 e 9 para visualizações

### Para Análise Incremental:
1. Defina lotes (ex: 200 commits por vez)
2. Use opção 5 repetidamente
3. Execute comparação Purity periodicamente
4. Monitore qualidade via visualizações

## 🔧 Solução de Problemas

### Se análise for interrompida:
- **Ctrl+C**: Mostra mensagem personalizada
- Dados são preservados automaticamente
- Continue com "pular commits analisados"

### Se houver erros de análise:
- Sistema continua com próximo commit
- Erros são logados
- Estatísticas finais mostram sucesso/falha

### Se comparação Purity falhar:
- Verifique se arquivo Purity CSV existe
- Verifique se há análises LLM disponíveis
- Use modo debug para mais informações

## 📈 Métricas de Qualidade

### Análise LLM:
- Taxa de sucesso por lote
- Distribuição de classificações
- Tempo médio por commit

### Comparação Purity:
- Taxa de concordância
- Distribuição por tipo
- Commits únicos por sistema

---

**Nota**: Este fluxo garante máxima qualidade de análise usando o prompt otimizado e comparação abrangente sem filtros com o Purity Checker.
