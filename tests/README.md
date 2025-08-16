# 🧪 Testes da Aplicação de Análise de Refatoramento

Esta pasta contém todos os arquivos de teste para a aplicação de análise de commits de refatoramento.

## 📁 Estrutura dos Testes

### Arquivos de Teste

| Arquivo | Descrição |
|---------|-----------|
| `test_runner.py` | **Teste principal** - Executa análises usando casos de teste específicos |
| `test_counter_functionality.py` | **Teste dos contadores** - Testa especificamente a funcionalidade dos contadores de sessão |
| `test_improvements.py` | **Demonstração** - Mostra as melhorias implementadas no sistema |
| `test_session_counter.py` | **Teste do contador** - Simulação básica do contador de sessão |

### Dados de Teste

| Arquivo | Descrição |
|---------|-----------|
| `test_commits.json` | **Dados de teste** - Contém commits de exemplo para testes |

## 🚀 Como Executar os Testes

### 1. Teste Principal (Análise Completa)
```bash
cd /home/marinhofn/tcc/refan
python tests/test_runner.py
```
**O que faz**: Executa análises completas usando commits de teste reais.

### 2. Teste dos Contadores (Funcionalidade Específica)
```bash
cd /home/marinhofn/tcc/refan
python tests/test_counter_functionality.py
```
**O que faz**: Testa especificamente a funcionalidade dos contadores de sessão sem executar análises reais.

### 3. Demonstração das Melhorias
```bash
cd /home/marinhofn/tcc/refan
python tests/test_improvements.py
```
**O que faz**: Mostra uma demonstração das melhorias implementadas.

### 4. Teste Básico do Contador
```bash
cd /home/marinhofn/tcc/refan
python tests/test_session_counter.py
```
**O que faz**: Simulação básica para verificar a lógica do contador.

## ✅ Funcionalidades Testadas

### Sistema de Contadores
- ✅ Contador de consulta atual: `[1/5], [2/5], [3/5]`
- ✅ Contador de sessão total: `[#1], [#2], [#3]`
- ✅ Continuidade entre consultas múltiplas

### Interface do Usuário
- ✅ Prompt mostrado apenas uma vez por consulta
- ✅ Resumo final com contagem Pure/Floss
- ✅ Menu melhorado com informações de sessão

### Análise de Commits
- ✅ Processamento de commits mock
- ✅ Classificação Pure/Floss simulada
- ✅ Tratamento de erros

## 🎯 Recomendações de Uso

1. **Para desenvolvimento**: Use `test_counter_functionality.py` para testar rapidamente mudanças nos contadores
2. **Para demonstração**: Use `test_improvements.py` para mostrar as funcionalidades
3. **Para testes completos**: Use `test_runner.py` quando quiser testar com dados reais

## 📝 Notas

- Todos os testes são executados a partir da raiz do projeto (`/home/marinhofn/tcc/refan`)
- Os testes usam as mesmas funções de cores e formatação da aplicação principal
- Os dados de teste estão em `test_commits.json` e podem ser modificados conforme necessário
