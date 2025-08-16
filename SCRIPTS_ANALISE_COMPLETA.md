# 📋 SCRIPTS PARA ANÁLISE COMPLETA (OPÇÃO 5)

## ✅ Scripts Disponíveis

### 1. **Script de Teste**: `tests/test_complete_analysis.py`
**Propósito**: Verifica se o sistema está pronto para análise completa
```bash
cd /home/marinhofn/tcc/refan
python tests/test_complete_analysis.py
```

**O que faz**:
- ✅ Verifica estrutura de pastas
- ✅ Confirma existência do arquivo CSV principal
- 📊 Mostra estatísticas atuais (total, analisados, restantes)
- 💡 Dá instruções de como executar

### 2. **Script de Execução**: `scripts/analysis/run_complete_analysis.py`
**Propósito**: Executa análise completa em lotes automáticos
```bash
cd /home/marinhofn/tcc/refan
python scripts/analysis/run_complete_analysis.py
```

**O que faz**:
- 🔄 Executa em lotes de 50 commits
- ⏸️ Pausa 30 segundos entre lotes
- 📊 Mostra estatísticas em tempo real
- 🎯 Pula commits já analisados
- 🛑 Para automaticamente quando termina

### 3. **Opção 5 do Menu**: `src/core/menu_analysis.py`
**Propósito**: Interface interativa para análise completa
```bash
cd /home/marinhofn/tcc/refan/src/core
python3 menu_analysis.py
# Escolher opção 5
```

**O que faz**:
- 🗂️ Cria pasta `analises_completas/`
- 💾 Faz backup do arquivo original
- 🔄 Reseta coluna LLM (força reprocessamento)
- 📦 Executa em lotes de 25 commits
- 📄 Gera relatório completo

## 🚀 Como Testar

### Método 1: Teste Rápido (Verificação)
```bash
cd /home/marinhofn/tcc/refan
python tests/test_complete_analysis.py
```

### Método 2: Execução em Lotes (Recomendado)
```bash
cd /home/marinhofn/tcc/refan
python scripts/analysis/run_complete_analysis.py
```

### Método 3: Interface Completa (Original)
```bash
refan
# Escolher opção 2 (Menu LLM)
# Escolher opção 5 (Análise completa)
```

## ⚙️ Configurações Diferentes

| Script | Tamanho Lote | Pausa | Reset? | Backup? |
|--------|--------------|-------|---------|---------|
| Menu (Opção 5) | 25 commits | 15s | ✅ Sim | ✅ Sim |
| run_complete_analysis.py | 50 commits | 30s | ❌ Não | ❌ Não |
| test_complete_analysis.py | - | - | ❌ Não | ❌ Não |

## 🎯 Recomendação

**Para TESTAR**: Use `test_complete_analysis.py` primeiro
```bash
python tests/test_complete_analysis.py
```

**Para EXECUTAR**: Use `run_complete_analysis.py` 
```bash
python scripts/analysis/run_complete_analysis.py
```

**Para RESET COMPLETO**: Use Opção 5 do menu
```bash
refan → Opção 2 → Opção 5
```

## 📊 Todos os scripts estão funcionais e organizados na nova estrutura!
