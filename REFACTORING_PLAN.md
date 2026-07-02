# Plano de Refatoração Arquitetural — Refan

## Contexto

O Refan é uma ferramenta de pesquisa acadêmica que classifica commits Git como refatoração **pure** (puramente estrutural) ou **floss** (mista com mudanças funcionais) usando LLMs locais via Ollama. Foi desenvolvida como TCC na UFCG e agora será evoluída para o mestrado.

O código funciona, mas foi construído incrementalmente durante a pesquisa e acumulou débito técnico significativo: dois sistemas de handlers paralelos com 80% de sobreposição, funções duplicadas em 3 lugares, 15+ valores mágicos hardcoded, nomes de campos inconsistentes, 12MB de falhas JSON rastreadas no Git, e ausência de infraestrutura de testes.

O objetivo é refatorar em fases incrementais, mantendo o projeto funcional a cada passo.

---

## Estratégia de Branches e Commits

### Princípios

1. **Cada fase = uma branch feature** que é mergeada via merge commit na branch de integração
2. **Cada sub-tarefa = um commit atômico** com mensagem descritiva seguindo Conventional Commits
3. **Histórico auditável** — cada commit deve ser compreensível isoladamente para uma banca de pós-graduação
4. **Projeto funcional a cada merge** — a branch de integração nunca fica em estado quebrado

### Hierarquia de Branches

```
main (produção — TCC original, intocada até refatoração completa)
  │
  └── refactor/v2-architecture (branch de integração — recebe merges das fases)
        │
        ├── refactor/phase-0/test-infrastructure
        │     Commits:
        │     ├── build: add pyproject.toml with project metadata and pytest config
        │     ├── test: add conftest.py with shared fixtures
        │     ├── test: add characterization tests for json_parser
        │     ├── test: add characterization tests for classification extraction
        │     ├── test: add characterization tests for git_handler
        │     ├── test: add characterization tests for data_handler
        │     ├── test: add characterization tests for prompt building
        │     ├── refactor: convert test_json_parser from unittest to pytest
        │     ├── chore: remove 5 empty test files
        │     └── chore: move non-test scripts from tests/ to scripts/
        │
        ├── refactor/phase-1/extract-shared-utilities
        │     Commits:
        │     ├── refactor: remove dead extract_json_from_text from llm_handler
        │     ├── refactor: remove duplicate extract_json_from_text from optimized_llm_handler
        │     ├── refactor: remove duplicate _find_json_end_index from both handlers
        │     ├── refactor: remove unused math import from both handlers
        │     ├── feat: create src/utils/classification.py with unified extract_final_classification
        │     ├── refactor: replace _extract_final_classification in both handlers with shared utility
        │     ├── feat: create src/utils/failure_logger.py with consolidated save_json_failure
        │     ├── refactor: replace save_json_failure in both handlers with shared utility
        │     ├── feat: create src/utils/llm_sizing.py with unified token/context utilities
        │     └── refactor: replace inline sizing functions in both handlers with shared utility
        │
        ├── refactor/phase-2/configuration-dataclass
        │     Commits:
        │     ├── feat: create src/core/settings.py with RefanSettings dataclass
        │     ├── refactor: wire config.py to use RefanSettings as backing store
        │     └── refactor: replace 26 hardcoded magic values across 4 handler files
        │
        ├── refactor/phase-3/merge-llm-handlers
        │     Commits:
        │     ├── fix: replace _call_ollama with adapter.complete in retry logic
        │     ├── refactor: merge OllamaAdapter and OptimizedOllamaAdapter into single adapter
        │     ├── refactor: merge LLMHandler and OptimizedLLMHandler into unified handler
        │     ├── refactor: consolidate 3 process_commits functions in main.py into one
        │     ├── refactor: update all imports to use unified handler
        │     └── chore: delete src/handlers/optimized_llm_handler.py
        │
        ├── refactor/phase-4/error-handling-logging
        │     Commits:
        │     ├── fix: replace 6 bare except clauses with specific exception types
        │     ├── refactor: replace os.chdir with subprocess cwd parameter in git_handler
        │     └── feat: add structured logging via src/utils/logging_config.py
        │
        ├── refactor/phase-5/data-models
        │     Commits:
        │     ├── feat: create src/models/commit.py with CommitPair and AnalysisResult dataclasses
        │     ├── feat: create src/models/adapters.py with CSV mapping layer
        │     └── refactor: migrate handlers and analyzer to use canonical data models
        │
        ├── refactor/phase-6/incremental-persistence
        │     Commits:
        │     ├── feat: create src/utils/persistence.py with SessionWriter (JSONL append)
        │     ├── refactor: replace CSV full-rewrite with JSONL incremental persistence
        │     ├── refactor: migrate json_failures to JSONL format with rotation
        │     └── chore: update .gitignore and untrack large generated files
        │
        ├── refactor/phase-7/cli-interface
        │     Commits:
        │     ├── feat: create src/cli.py with argparse-based CLI
        │     ├── refactor: extract reusable analysis functions from menu code
        │     └── refactor: update refan.py entry point to dispatch CLI or interactive
        │
        ├── refactor/phase-8/consolidate-scripts
        │     Commits:
        │     ├── chore: reorganize scripts/ into research/, data/, deprecated/
        │     └── chore: merge 4 recovery scripts into single recover utility
        │
        ├── refactor/phase-9/clean-imports
        │     Commits:
        │     └── refactor: replace wildcard color imports with explicit imports in 9 modules
        │
        └── refactor/phase-10/documentation
              Commits:
              ├── docs: update README.md with new CLI and architecture
              ├── build: create complete pyproject.toml with all metadata
              └── docs: update CLAUDE.md with post-refactoring architecture
```

### Convenção de Commit Messages

Segue [Conventional Commits](https://www.conventionalcommits.org/) adaptado para contexto acadêmico:

| Prefixo | Uso |
|---------|-----|
| `feat:` | Nova funcionalidade (novo arquivo, nova classe, nova CLI) |
| `fix:` | Correção de bug (ex: `_call_ollama` inexistente) |
| `refactor:` | Reestruturação sem mudança de comportamento |
| `test:` | Adição ou modificação de testes |
| `docs:` | Documentação |
| `build:` | Sistema de build, dependências, configuração |
| `chore:` | Tarefas de manutenção (mover arquivos, limpar) |
| `perf:` | Otimização de performance |

**Formato da mensagem:**
```
<tipo>(<escopo>): <descrição imperativa curta>

<corpo opcional — explica o "porquê", não o "o quê">

<footer opcional — referências a issues, breaking changes>
```

**Exemplo:**
```
refactor(handlers): remove duplicate extract_json_from_text from optimized_llm_handler

The function was defined inline at line 41-63, shadowing the import from
src.utils.json_parser at line 15. The inline version was less robust (4 regex
patterns vs 6 strategies + think block removal + json5 fallback in the
canonical implementation). The bare except: at line 61 was also eliminated.

Refs: REFACTORING_PLAN.md Phase 1.1
```

### Fluxo de Merge

```
1. Criar branch da fase:  git checkout -b refactor/phase-N/nome refactor/v2-architecture
2. Implementar commits:   git commit -m "tipo(escopo): descrição"
3. Verificar testes:      python -m pytest tests/ -v
4. Merge na integração:   git checkout refactor/v2-architecture
                          git merge --no-ff refactor/phase-N/nome
5. Tag de milestone:      git tag -a v2.0.0-phase-N -m "Phase N: descrição"
6. Limpar branch:         git branch -d refactor/phase-N/nome
```

O `--no-ff` garante um merge commit explícito, preservando a história de que aquela fase foi um conjunto coeso de mudanças. Cada merge commit documenta o que a fase inteira realizou.

### Tags de Milestone

| Tag | Fase | Descrição |
|-----|------|-----------|
| `v2.0.0-phase-0` | 0 | Infraestrutura de testes estabelecida |
| `v2.0.0-phase-1` | 1 | Duplicação eliminada, utilitários extraídos |
| `v2.0.0-phase-2` | 2 | Configuração centralizada |
| `v2.0.0-phase-3` | 3 | Handlers unificados |
| `v2.0.0-phase-4` | 4 | Error handling e logging |
| `v2.0.0-phase-5` | 5 | Modelos de dados canônicos |
| `v2.0.0-phase-6` | 6 | Persistência incremental |
| `v2.0.0-phase-7` | 7 | Interface CLI |
| `v2.0.0-phase-8` | 8 | Scripts consolidados |
| `v2.0.0-phase-9` | 9 | Imports limpos |
| `v2.0.0-phase-10` | 10 | Documentação completa |
| `v2.0.0` | — | Refatoração interna completa, merge em main |

Após a tag `v2.0.0`, a branch `refactor/v2-architecture` é mergeada em `main`. As Fases 11-12 (Supabase + Frontend) seguem em branches próprias a partir de `main`.

---

## Diagnóstico Completo do Estado Atual

### Métricas do Código

| Área | Linhas | Arquivos | Observação |
|------|--------|----------|------------|
| `src/` (produção) | ~7.700 | 15 | Core do sistema |
| `scripts/` | ~3.100 | 20 | Scripts utilitários, muitos sobrepostos |
| `tests/` | ~2.600 | 37 | 5 vazios, vários são scripts e não testes |
| Dados CSV | ~19 MB | 14+ | Rastreados no Git |
| `json_failures.json` | 12 MB | 1 | Rastreado no Git, crescimento ilimitado |

### Problemas Identificados

#### 1. Duplicação Massiva de Código

**`extract_json_from_text()` definida em 3 lugares:**
- `src/utils/json_parser.py:88-150` — implementação canônica
- `src/handlers/llm_handler.py:36-46` — fallback que é **imediatamente sobrescrito** pelo import na linha 47 (código morto)
- `src/handlers/optimized_llm_handler.py:41-63` — redefine após import na linha 15

**`_find_json_end_index()` duplicada em 3 lugares:**
- `src/utils/json_parser.py:14-34`
- `src/handlers/llm_handler.py:528-548`
- `src/handlers/optimized_llm_handler.py:885-909`

**`save_json_failure()` quase idêntica em ambos os handlers:**
- `llm_handler.py:192-238` (~46 linhas)
- `optimized_llm_handler.py:355-399` (~44 linhas)

**`_extract_final_classification()` em ambos os handlers:**
- `llm_handler.py:459-483` — 5 padrões regex
- `optimized_llm_handler.py:1036-1070` — 11 padrões regex (superset)

**Estratégias de extração JSON duplicadas entre handlers** com implementações ligeiramente diferentes.

#### 2. Dois Sistemas de Handlers Paralelos

| Feature | `LLMHandler` (660 linhas) | `OptimizedLLMHandler` (1.086 linhas) |
|---------|--------------------------|--------------------------------------|
| Adapter | `OllamaAdapter` | `OptimizedOllamaAdapter` (+ DeepSeek tracking) |
| Prompt | `LLM_PROMPT` (config.py) | `OPTIMIZED_LLM_PROMPT` (optimized_prompt.py) |
| Diff | Truncamento simples (50k) | Per-file line limit + suporte a arquivo (60k) |
| CSV loader | Não | Sim (`CSVDataLoader`) |
| Retry (adapter) | 3 tentativas | 1 tentativa |
| Keep-alive | `"10m"` | `"5m"` / `"30s"` (DeepSeek) |
| Timeout | 120s fixo | 200-300s dinâmico |
| `_process_llm_response()` | Inline em `analyze_commit` | Método dedicado |
| `_retry_analysis_with_simplified_prompt()` | Não | Sim (mas chama `_call_ollama` que **NÃO EXISTE**) |

#### 3. Anti-patterns de Error Handling

**6 bare `except:` que engolem todas as exceções:**
- `optimized_llm_handler.py:61` — na `extract_json_from_text` duplicada
- `optimized_llm_handler.py:840` — no `_attempt_json_repair`
- `llm_handler.py:44` — na `extract_json_from_text` duplicada
- `llm_visualization_handler.py:395`
- `visualization_handler.py:417`
- `visualization_handler.py:433`

**`os.chdir()` em `git_handler.py`** — 4 instâncias, não é thread-safe. Deveria usar `subprocess.run(..., cwd=repo_path)`.

**Falhas silenciosas** — CSV loading falha sem levantar exceção; código continua com `None`.

**Sem logging centralizado** — mistura de `print(error(...))`, `print(warning(...))`, e `warnings.warn()`.

#### 4. Valores Mágicos Hardcoded (15+)

| Valor | Localização 1 | Localização 2 | Localização 3 |
|-------|---------------|---------------|---------------|
| Diff threshold | 50.000 (`llm_handler`) | 60.000 (`optimized_llm_handler`) | 100.000 (`optimized_prompt`) |
| Temperature | 0.1 (`llm_handler:93`) | 0.1 (`optimized_llm_handler:249`) | — |
| Keep-alive | `"10m"` (`llm_handler:90`) | `"5m"` (`optimized_llm_handler:238`) | `"30s"` (DeepSeek) |
| Timeout | 120s (`llm_handler:103`) | 200-300s (`optimized_llm_handler:260`) | — |
| Context window | 2048/4096/6144 | 3072/4096/6144/8192 | — |
| Failures file | `"json_failures.json"` | `"json_failures.json"` | — |

#### 5. Caos de Nomes de Campos

| Conceito | Variante 1 | Variante 2 | Variante 3 |
|----------|-----------|-----------|-----------|
| Hash anterior | `commit1` | `commit_hash_before` | `previous_hash` |
| Hash atual | `commit2` | `commit_hash_current` | `commit_hash` |
| Tipo de refatoração | `refactoring_type` | `classification` | `llm_analysis` |
| Resposta bruta | `llm_response_complete` | `llm_raw_response` | `llm_response_excerpt` |
| Repositório | `repository` | `project` | `project_name` |

#### 6. Problemas de Persistência e Armazenamento

- **`json_failures.json`**: array JSON com read-modify-write a cada falha. 12MB e crescendo. Sem rotação.
- **CSV reescrito inteiro** após CADA commit em `llm_purity_analyzer.py` — ineficiente para 5000+ linhas, risco de corrupção se interrompido durante escrita.
- **Backups com timestamps** espalhados em diretórios de modelos sem limite de retenção.
- **Formatos de armazenamento sobrepostos**: CSV de trabalho + JSON de sessão + JSON de falhas + log de commits analisados — sem coordenação entre eles.

#### 7. Infraestrutura de Testes Inexistente

- Sem `pytest.ini`, `pyproject.toml`, ou `conftest.py`
- 5 arquivos de teste **vazios** documentados no README: `test_runner.py`, `test_counter_functionality.py`, `test_session_counter.py`, `test_system.py`, `fix_imports.py`
- Testes são scripts standalone executados com `python test_*.py` — não são testes pytest
- Sem fixtures comuns; cada arquivo reinventa setup de paths
- Nomes obscuros: `test_option5`, `test_option6_complete`, `test_final_option5`
- Arquivos que não são testes em `tests/`: `unite_all_analysis.py`, `unite_complete_analysis.py`, `filter_csv.py`

#### 8. Higiene de Arquivos

- **12MB** `json_failures.json` rastreado no Git
- **19MB** de CSVs rastreados no Git
- **1.3MB** PDF do TCC rastreado no Git
- `complete_unified_analysis.csv` + `.txt` — mesmo conteúdo em dois formatos
- `.gitignore` tem `# output/` **comentado** — diretório de output deveria ser ignorado
- 200+ repositórios clonados em `repositorios/`

#### 9. Sprawl de Scripts

- 20 scripts em `scripts/` com funcionalidade sobreposta
- 4 scripts de recovery que fazem coisas similares: `recover_llm_analysis.py`, `recover_json_analyses.py`, `recover_complete_backups.py`, `final_consolidation.py`
- 2 scripts de análise sobrepostos em `scripts/analysis/`
- Scripts de demo raramente usados

#### 10. Problemas de Arquitetura

- **Sem interface CLI** — opção 3 no menu está como "não implementado"
- **Tudo via menus interativos** — não é scriptável/automatizável
- **Wildcard import** de colors em 9+ módulos (`from src.utils.colors import *`)
- **Import `math` não utilizado** em `optimized_llm_handler.py:38`

### Bugs Conhecidos

| Bug | Arquivo:Linha | Severidade | Descrição |
|-----|---------------|------------|-----------|
| `_call_ollama()` não existe | `optimized_llm_handler.py:764` | **CRÍTICO** | Método chamado mas nunca definido. Crash em runtime no retry. |
| `extract_json_from_text()` redefinida | `optimized_llm_handler.py:41` | Médio | Sobrescreve o import da linha 15; `except:` bare na linha 61 |
| Código morto | `llm_handler.py:36-46` | Baixo | Define fallback imediatamente sobrescrito pelo import na linha 47 |
| 6 bare `except:` | Vários | Médio | Engole KeyboardInterrupt, SystemExit, etc. |
| `os.chdir()` não thread-safe | `git_handler.py` (4 instâncias) | Médio | Pode causar problemas em execução paralela |

---

## Plano de Refatoração em Fases

### Fase 0: Rede de Segurança — Infraestrutura de Testes

**Objetivo**: Estabelecer testes automatizados para que todas as fases seguintes tenham verificação.

**Risco**: Nenhum — só adiciona arquivos.

#### 0.1 Criar infraestrutura pytest

Atualmente **não existe** `pyproject.toml`, `pytest.ini`, `setup.py`, ou `conftest.py`. Os 33 arquivos em `tests/` totalizam 2.486 linhas, mas **nenhum** usa pytest — todos são scripts standalone com `if __name__ == "__main__"` e funções `def test_*()` que apenas printam no terminal sem assertions.

**Criar `pyproject.toml`** na raiz do projeto:

```toml
[project]
name = "refan"
version = "2.0.0"
description = "Classificação de refatorações com LLMs"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "requests>=2.31",
    "plotly>=5.22",
    "kaleido>=0.2",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov", "pytest-mock"]
json5 = ["json5>=0.9"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: testes que requerem Ollama ou rede",
    "integration: testes de integração com CSVs reais",
]
```

**Criar `tests/conftest.py`** com fixtures comuns — eliminando os 15+ blocos de `sys.path.insert()` espalhados nos testes:

```python
import sys
from pathlib import Path
import pytest
import pandas as pd

# Garantir que src/ é importável
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def sample_commit_data():
    """Dict padrão de commit para testes."""
    return {
        "repository": "https://github.com/test/repo",
        "commit_hash_before": "abc123def456",
        "commit_hash_current": "789ghi012jkl",
        "commit_message": "Refactor: extract method",
        "diff": "diff --git a/Foo.java b/Foo.java\n- old\n+ new",
        "project_name": "test-repo",
    }

@pytest.fixture
def sample_csv_dataframe():
    """DataFrame pequeno simulando commits_with_refactoring.csv."""
    return pd.DataFrame({
        "commit1": ["aaa111", "bbb222"],
        "commit2": ["ccc333", "ddd444"],
        "project": ["https://github.com/a/b", "https://github.com/c/d"],
        "project_name": ["b", "d"],
    })

@pytest.fixture
def mock_ollama_response_factory():
    """Factory para respostas LLM previsíveis."""
    def _make(refactoring_type="floss", justification="Test justification"):
        return (
            f'{{"repository": "test", "commit_hash_before": "abc",'
            f'"commit_hash_current": "def", "refactoring_type": "{refactoring_type}",'
            f'"justification": "{justification}"}}'
        )
    return _make

@pytest.fixture
def tmp_output_dir(tmp_path):
    """Diretório temporário para outputs de teste."""
    out = tmp_path / "output" / "models" / "test-model" / "analises"
    out.mkdir(parents=True)
    return out
```

#### 0.2 Auditar e classificar todos os 33 arquivos de teste existentes

Classificação completa baseada em leitura de cada arquivo:

**VAZIOS (0 linhas) — DELETAR:**

| Arquivo | Linhas | Ação |
|---------|--------|------|
| `tests/test_runner.py` | 0 | Deletar |
| `tests/test_counter_functionality.py` | 0 | Deletar |
| `tests/test_session_counter.py` | 0 | Deletar |
| `tests/test_system.py` | 0 | Deletar |
| `tests/fix_imports.py` | 0 | Deletar |

**NÃO SÃO TESTES — MOVER para `scripts/`:**

| Arquivo | Linhas | Descrição | Destino |
|---------|--------|-----------|---------|
| `tests/unite_all_analysis.py` | 154 | Consolida análises de 3 modelos | `scripts/data/` |
| `tests/unite_complete_analysis.py` | 184 | Consolida análises completas | `scripts/data/` |
| `tests/filter_csv.py` | 51 | Filtra CSV por coluna | `scripts/data/` |
| `tests/fix_script_imports.py` | 108 | Corrige imports em scripts | `scripts/deprecated/` |

**ÚNICO TESTE REAL PYTEST — MANTER e expandir:**

| Arquivo | Linhas | Framework | Assertions |
|---------|--------|-----------|------------|
| `tests/test_json_parser.py` | 32 | `unittest.TestCase` | 4 testes reais com `assertEqual`/`assertIsInstance` |

**SCRIPTS DE TESTE STANDALONE (print-based, sem assertions) — CONVERTER ou DEPRECAR:**

| Arquivo | Linhas | Testa o quê | Requer Ollama/dados | Ação |
|---------|--------|-------------|---------------------|------|
| `test_improvements.py` | 190 | PurityHandler, LLMHandler._extract_json_from_response, field validation | Sim (CSVs reais) | Converter parcialmente: extrair os test cases de `test_llm_json_extraction()` (linhas 63-78) como fixtures de caracterização |
| `test_csv_improvements.py` | 200 | CSVDataLoader, OptimizedLLMHandler, raw response preservation | Sim (CSVs, Ollama) | Converter: `test_json_validation_with_csv()` (linhas 78-119) tem bons casos de teste |
| `test_json_fields.py` | 127 | LLMPurityAnalyzer result structure, OptimizedLLMHandler output fields | Sim (CSVs) | Converter: dry_run mode permite testes sem Ollama |
| `test_fixes.py` | 138 | DataHandler deduplication, save_json_failure | Sim (CSVs) | Converter: `test_json_failure_handling()` (linhas 52-105) é um bom teste de unidade |
| `test_llm_purity_analyzer.py` | 63 | Analyzer summary e análise de 1 commit | Sim (CSVs, Ollama) | Marcar como `@pytest.mark.integration` |
| `test_single_analysis.py` | 116 | Fluxo completo: clone → diff → LLM | Sim (Git, Ollama) | Marcar como `@pytest.mark.slow` |
| `test_json_fix.py` | 69 | JSON parsing de respostas LLM | Não | Converter: bons test cases standalone |
| `test_json_parsing.py` | 38 | json.loads direto | Não | Converter: caso trivial mas útil |
| `test_llm_json_fix.py` | 162 | OptimizedLLMHandler.analyze_commit_refactoring | Sim (Ollama) | Extrair mock test cases |
| `test_purity_fix.py` | 67 | PurityHandler loading | Sim (CSVs) | Converter com CSV fixture |
| `test_visualization.py` | 47 | VisualizationHandler | Sim (CSVs) | Marcar como `@pytest.mark.integration` |
| `test_dashboard.py` | 44 | Dashboard creation | Sim (CSVs) | Marcar como `@pytest.mark.integration` |
| `test_dashboard_complete.py` | 84 | Dashboard com mais opções | Sim (CSVs) | Marcar como `@pytest.mark.integration` |
| `test_complete_analysis.py` | 60 | Análise completa | Sim (CSVs, Ollama) | Marcar como `@pytest.mark.slow` |
| `test_new_json_structure.py` | 77 | Nova estrutura JSON | Sim (CSVs) | Converter parcialmente |
| `test_deepseek_quick.py` | 34 | DeepSeek otimizations | Sim (Ollama) | `@pytest.mark.slow` |
| `test_deepseek_performance.py` | 127 | Performance monitoring | Sim (Ollama) | `@pytest.mark.slow` |
| `test_option2_deepseek.py` | 56 | Opção 2 com DeepSeek | Sim (Ollama) | Deprecar → `scripts/deprecated/` |
| `test_option5.py` | 70 | Opção 5 do menu | Sim (CSVs) | Deprecar → `scripts/deprecated/` |
| `test_final_option5.py` | 73 | Opção 5 final | Sim (CSVs) | Deprecar → `scripts/deprecated/` |
| `test_option6_final.py` | 40 | Opção 6 final | Sim (CSVs) | Deprecar → `scripts/deprecated/` |
| `test_option6_complete.py` | 74 | Opção 6 completa | Sim (CSVs) | Deprecar → `scripts/deprecated/` |

**Import problemático encontrado:** `tests/test_single_analysis.py:21` importa de `src.analyzers.optimized_llm_handler` — caminho errado, deveria ser `src.handlers.optimized_llm_handler`.

#### 0.3 Escrever testes de caracterização (locking tests)

Criar **novos** arquivos de teste pytest que travam o comportamento atual das funções que serão refatoradas:

**`tests/test_char_json_parser.py`** (caracterização de `src/utils/json_parser.py`):

Funções a testar (com line references):
- `extract_json_from_text()` (linhas 88-149) — função principal
- `_strip_think_blocks()` (linhas 152-200) — pré-processamento
- `try_parse_json()` (linhas 61-71) — parse com fallback json5
- `extract_json_candidates()` (linhas 74-85) — regex extraction
- `_find_json_end_index()` (linhas 14-34) — balanceamento de chaves

Casos de teste a implementar (baseados nos 4 testes existentes em `test_json_parser.py` + casos extraídos de `test_improvements.py:63-78`):

```python
# Casos já cobertos pelo test_json_parser.py existente:
1. test_simple_json                          # {"a": 1, "b": "x"}
2. test_json_in_markdown_block               # ```json ... ```
3. test_think_block_removed                  # <think>...</think> + json
4. test_malformed_trailing_comma             # {"a": 1,}

# Novos casos a adicionar:
5. test_json_after_text_analysis             # "This is pure... \n{...}"
6. test_json_without_any_json                # "Only text no json at all"
7. test_json_with_nested_objects             # {"a": {"b": 1}}
8. test_json_with_final_pattern              # "FINAL: PURE\n```json{...}```"
9. test_json_deeply_malformed                # chaves desbalanceadas
10. test_json_multiple_candidates            # texto com 2 JSONs, pegar o primeiro válido
11. test_key_value_fallback                  # "refactoring_type: pure\njustification: ok"
12. test_empty_input                         # ""
13. test_none_like_input                     # apenas whitespace
14. test_json_with_comments                  # {"a": 1, // comment\n "b": 2}
15. test_json_with_single_quotes             # {'a': 1}
```

**`tests/test_char_classification.py`** (caracterização de `_extract_final_classification()`):

Precisa testar as 5 regex do `llm_handler.py:459-483` E as 11 regex do `optimized_llm_handler.py:1036-1070`:

```python
# Padrões do llm_handler.py (5 padrões, linhas 469-477):
1. "FINAL: PURE"
2. "FINAL: FLOSS"  
3. "FINAL: pure"
4. "Final: PURE"
5. "CONCLUSÃO: FLOSS"

# Padrões adicionais do optimized_llm_handler.py (6 extras, linhas 1046-1066):
6. "CONCLUSION: PURE"
7. "CLASSIFICATION: FLOSS"
8. "CLASSIFICAÇÃO: pure"
9. "RESULTADO: PURE"
10. "**FINAL: FLOSS**" (com markdown bold)
11. "FINAL CLASSIFICATION: PURE"

# Edge cases:
12. "No FINAL pattern at all" → None
13. "FINAL: INVALID" → None
14. "final: pure" (lowercase tudo)
15. "FINAL:PURE" (sem espaço)
```

**`tests/test_char_git_handler.py`** (caracterização de `src/handlers/git_handler.py`):

Funções a testar com mock de subprocess:
- `ensure_repo_cloned()` (linha 39) — mock git clone / git fetch
- `get_commit_diff()` (dependendo da assinatura exata) — mock git diff com cwd
- `get_commit_message()` — mock git log
- `commit_exists()` — mock git cat-file

**`tests/test_char_data_handler.py`** (caracterização de `src/handlers/data_handler.py`):

Funções a testar:
- `_load_analyzed_commits()` (linha 26) — com fixture JSON contendo `commit2` e outra com `commit_hash_current`
- `load_data()` (precisa do CSV) — marcar como `@pytest.mark.integration`
- `check_dataset_duplicates()` — com DataFrame fixture

**`tests/test_char_prompt.py`** (caracterização dos prompts):

Funções a testar:
- `build_commit_prompt()` (`llm_handler.py:122-174`) — verificar estrutura do prompt
- `build_optimized_commit_prompt_with_file_support()` (`optimized_prompt.py`) — verificar handling de diff grande vs pequeno
- `reduce_diff_simple()` (`llm_handler.py:62-66`) — verificar truncamento
- `reduce_diff()` (se existir no optimized) — verificar per-file limit

#### 0.4 Limpar diretório de testes

Ações exatas:

```bash
# Deletar 5 arquivos vazios
git rm tests/test_runner.py
git rm tests/test_counter_functionality.py
git rm tests/test_session_counter.py
git rm tests/test_system.py
git rm tests/fix_imports.py

# Mover scripts que não são testes
git mv tests/unite_all_analysis.py scripts/data/unite_all_analysis.py
git mv tests/unite_complete_analysis.py scripts/data/unite_complete_analysis.py
git mv tests/filter_csv.py scripts/data/filter_csv.py
git mv tests/fix_script_imports.py scripts/deprecated/fix_script_imports.py

# Mover testes de "option" que são scripts de exploração
git mv tests/test_option2_deepseek.py scripts/deprecated/test_option2_deepseek.py
git mv tests/test_option5.py scripts/deprecated/test_option5.py
git mv tests/test_final_option5.py scripts/deprecated/test_final_option5.py
git mv tests/test_option6_final.py scripts/deprecated/test_option6_final.py
git mv tests/test_option6_complete.py scripts/deprecated/test_option6_complete.py
```

**Resultado**: tests/ passa de 33 arquivos para ~20, todos com propósito claro.

#### 0.5 Converter `test_json_parser.py` de unittest para pytest

O único teste real existente (`tests/test_json_parser.py`, 32 linhas) usa `unittest.TestCase`. Converter para pytest puro:

```python
# ANTES (unittest):
class TestJSONParser(unittest.TestCase):
    def test_simple_json(self):
        res = extract_json_from_text('{"a": 1}')
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('a'), 1)

# DEPOIS (pytest):
def test_simple_json():
    res = extract_json_from_text('{"a": 1}')
    assert isinstance(res, dict)
    assert res["a"] == 1
```

**Arquivos criados nesta fase**:
- `pyproject.toml` (novo)
- `tests/conftest.py` (novo)
- `tests/test_char_json_parser.py` (novo, ~120 linhas)
- `tests/test_char_classification.py` (novo, ~80 linhas)
- `tests/test_char_git_handler.py` (novo, ~60 linhas)
- `tests/test_char_data_handler.py` (novo, ~50 linhas)
- `tests/test_char_prompt.py` (novo, ~70 linhas)

**Arquivos modificados**: `tests/test_json_parser.py` (converter de unittest para pytest)

**Arquivos deletados/movidos**: 10 arquivos (5 deletados, 5 movidos para scripts/deprecated/)

**Arquivos movidos para scripts/data/**: 3 arquivos

**Verificação**:
```bash
pip install -e ".[dev]"
python -m pytest tests/ -v                    # todos passam
python -m pytest tests/ -v -m "not slow"      # testes rápidos passam
python -m pytest tests/ -v -m "not integration" # testes sem dados reais passam
```

---

### Fase 1: Extrair Utilitários Compartilhados (Eliminar Duplicação)

**Objetivo**: Consolidar lógica idêntica espalhada em 3 lugares para um único source of truth.

**Risco**: Baixo — consolida código idêntico.

#### 1.1 Consolidar extração de JSON em `src/utils/json_parser.py`

A implementação canônica (`src/utils/json_parser.py`, 200 linhas) é significativamente mais robusta que as duplicatas — inclui `_strip_think_blocks()`, `try_parse_json()` com json5 fallback, `extract_json_candidates()`, balanceamento via `_find_matching_closing()`, reparo de trailing commas/comments, e fallback key-value.

**Mapa completo da duplicação:**

| Função | json_parser.py | llm_handler.py | optimized_llm_handler.py |
|--------|---------------|----------------|--------------------------|
| `extract_json_from_text()` | L88-149 (canônica, 62 linhas) | L36-46 (fallback morto, 11 linhas) | L41-63 (inline, 23 linhas) |
| `_find_json_end_index()` | L14-34 (como função) | L528-548 (como método de LLMHandler) | L885-909 (como método de OptimizedLLMHandler) |
| `_find_matching_closing()` | L37-58 (generalizada) | — | — |
| `try_parse_json()` | L61-71 (com json5) | — | — |
| `extract_json_candidates()` | L74-85 | — | — |
| `_strip_think_blocks()` | L152-200 | — | — |

**Ações específicas:**

1. **Deletar** `llm_handler.py:36-46` — é código morto: define `extract_json_from_text()` como fallback, mas a linha 47 (`from src.utils.json_parser import extract_json_from_text`) imediatamente sobrescreve a definição. Contém um `except:` bare na linha 44.

2. **Deletar** `optimized_llm_handler.py:41-63` — shadowing: redefine `extract_json_from_text()` após o import na linha 15 (`from src.utils.json_parser import extract_json_from_text`). Contém `except:` bare na linha 61. Esta versão inline é muito mais primitiva que a canônica (4 regex simples vs 6 estratégias + think block removal + json5).

3. **Deletar** `llm_handler.py:528-548` — método `LLMHandler._find_json_end_index()`. Chamado por `_extract_with_patterns()` na linha 509. Substituir por import: `from src.utils.json_parser import _find_json_end_index`. Alternativamente, chamar `_find_matching_closing(text, start_idx, '{', '}')` que é a versão generalizada já existente.

4. **Deletar** `optimized_llm_handler.py:885-909` — método `OptimizedLLMHandler._find_json_end_index()`. Implementação idêntica byte-a-byte à do llm_handler. Mesmo fix.

5. **Limpar import** em `llm_handler.py:47`: a linha `from src.utils.json_parser import extract_json_from_text` já existe e é correta — apenas remover o bloco L36-46 antes dela.

6. **Limpar import redundante de `json5`**: Definido 3 vezes:
   - `json_parser.py:8-11` — **manter** (canônico)
   - `llm_handler.py:10-13` — manter (usado por `_extract_with_patterns` L501 para `_json5.loads()`)
   - `optimized_llm_handler.py:7-10` — manter (usado em métodos de reparo JSON)

7. **Remover `import math`** — importado mas **nunca usado** em:
   - `llm_handler.py:33`
   - `optimized_llm_handler.py:38`

**Callers que precisam ser atualizados após remoção do método `_find_json_end_index`:**
- `llm_handler.py:509`: `end_idx = self._find_json_end_index(response, start_idx)` → `end_idx = _find_json_end_index(response, start_idx)` (importado de json_parser)
- `optimized_llm_handler.py` (buscar chamadas similares no código de extração)

#### 1.2 Criar `src/utils/classification.py`

**Comparação detalhada das duas versões:**

`llm_handler.py:459-483` — 6 padrões, usa `re.search()`:
```python
patterns = [
    r'FINAL:\s*(PURE|FLOSS)',        # L469
    r'FINAL:\s*(pure|floss)',        # L470
    r'Final:\s*(PURE|FLOSS)',        # L471
    r'Final:\s*(pure|floss)',        # L472
    r'CONCLUSÃO:\s*(PURE|FLOSS)',    # L473
    r'CONCLUSÃO:\s*(pure|floss)'     # L474
]
# Retorna match.group(1).upper()
```

`optimized_llm_handler.py:1036-1070` — 13 padrões, usa `re.findall()`:
```python
patterns = [
    r'FINAL:\s*(PURE|FLOSS)',                                    # L1046
    r'FINAL:\s*(pure|floss)',                                    # L1047
    r'Final:\s*(PURE|FLOSS)',                                    # L1048
    r'Final:\s*(pure|floss)',                                    # L1049
    r'CONCLUSÃO:\s*(PURE|FLOSS)',                                # L1050
    r'CONCLUSÃO:\s*(pure|floss)',                                # L1051
    r'CLASSIFICATION:\s*(PURE|FLOSS)',                           # L1052
    r'CLASSIFICATION:\s*(pure|floss)',                           # L1053
    r'RESULTADO:\s*(PURE|FLOSS)',                                # L1054
    r'RESULTADO:\s*(pure|floss)',                                # L1055
    r'\bFINAL[:\s]+([Pp][Uu][Rr][Ee]|[Ff][Ll][Oo][Ss][Ss])\b', # L1057
    r'\b(PURE|FLOSS)\s*$',                                      # L1058
    r'^\s*(PURE|FLOSS)\s*$',                                    # L1059
]
# Usa findall + loops, retorna match.upper()
```

**Versão unificada proposta** — `src/utils/classification.py`:

```python
"""Constantes e extração de classificação de refatoramento."""
from typing import Optional
import re

# Constantes canônicas
PURE = "pure"
FLOSS = "floss"
VALID_CLASSIFICATIONS = frozenset({PURE, FLOSS})

def extract_final_classification(response: str) -> Optional[str]:
    """Extrai classificação PURE/FLOSS de padrões na resposta LLM.
    
    Consolida padrões de llm_handler.py:459-483 e optimized_llm_handler.py:1036-1070.
    Todos os padrões usam re.IGNORECASE, eliminando as duplicatas upper/lower.
    
    Returns:
        'PURE' ou 'FLOSS' em uppercase, ou None se não encontrado.
    """
    patterns = [
        # Padrões explícitos com prefixo (originalmente em ambos os handlers)
        r'FINAL:\s*(PURE|FLOSS)',
        r'CONCLUSÃO:\s*(PURE|FLOSS)',
        r'CLASSIFICATION:\s*(PURE|FLOSS)',     # apenas no optimized
        r'RESULTADO:\s*(PURE|FLOSS)',          # apenas no optimized
        # Padrão flexível (apenas no optimized, L1057)
        r'\bFINAL[:\s]+(?:PURE|FLOSS)\b',
        # Linha isolada (apenas no optimized, L1058-1059)
        r'^\s*(PURE|FLOSS)\s*$',
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
        if match:
            # group(1) pode não existir no padrão sem grupo de captura
            value = (match.group(1) if match.lastindex else match.group(0)).strip().upper()
            if value in {"PURE", "FLOSS"}:
                return value
    return None
```

**Redução**: de 6+13=19 padrões (com duplicatas upper/lower) para **6 padrões** com `re.IGNORECASE`.

**Callers que precisam ser atualizados:**
- `llm_handler.py:421`: `final_classification = self._extract_final_classification(llm_response)` → `final_classification = extract_final_classification(llm_response)` (importado de `src.utils.classification`)
- `optimized_llm_handler.py:562`: idem
- Remover os métodos `_extract_final_classification` de ambas as classes

**Strings literais "pure"/"floss" espalhadas** (a serem substituídas pelas constantes gradualmente):
- `llm_handler.py:355,358` — `json_result.get("refactoring_type") not in ("pure", "floss")`
- `llm_handler.py:357` — `json_result["refactoring_type"] = "floss"`
- `optimized_llm_handler.py` — múltiplas ocorrências similares
- `llm_purity_analyzer.py:298-299` — default "FLOSS" para fallback
- `config.py:267` — no template do prompt (manter como está, é texto para o LLM)

#### 1.3 Criar `src/utils/failure_logger.py`

**Comparação byte-a-byte das duas versões:**

`LLMHandler.save_json_failure()` — `llm_handler.py:192-238`:
```python
failure_entry = {
    "timestamp": datetime.datetime.now().isoformat(),
    "commit_hash": commit_hash,
    "repository": repository,
    "commit_message": commit_message,
    "error": error_msg,
    "llm_response_complete": raw_response,
    "llm_response_excerpt": raw_response,
    "analysis_attempt": "JSON parsing failed",
    "parse_attempts": 1,               # ← EXCLUSIVO do LLMHandler
    "llm_prompt_excerpt": prompt_excerpt,  # ← campo diferente
    "notes": "Saved by save_json_failure"  # ← EXCLUSIVO do LLMHandler
}
```

`OptimizedLLMHandler.save_json_failure()` — `optimized_llm_handler.py:355-399`:
```python
failure_entry = {
    "timestamp": datetime.datetime.now().isoformat(),
    "commit_hash": commit_hash,
    "repository": repository,
    "commit_message": commit_message,
    "error": error_msg,
    "llm_response_complete": raw_response,
    "llm_response_excerpt": raw_response,
    "analysis_attempt": "JSON parsing failed",
    "prompt_excerpt": prompt_excerpt,       # ← campo diferente
}
```

**Diferenças**: Apenas 3 campos extras no LLMHandler (`parse_attempts`, `llm_prompt_excerpt` vs `prompt_excerpt`, `notes`). O restante da lógica (load existing → append → save) é **idêntico**.

**Versão unificada** — `src/utils/failure_logger.py`:

```python
"""Logging centralizado de falhas de parsing JSON."""
import json
import os
import datetime
from typing import Optional

def save_json_failure(
    failures_file: str,
    commit_hash: str,
    repository: str,
    commit_message: str,
    raw_response: str,
    error_msg: str,
    prompt_excerpt: Optional[str] = None,
    extra_fields: Optional[dict] = None,
) -> None:
    """Salva falha de parsing JSON em arquivo separado.
    
    Consolidado de llm_handler.py:192-238 e optimized_llm_handler.py:355-399.
    
    Args:
        failures_file: Caminho do arquivo de falhas
        extra_fields: Campos adicionais (ex: parse_attempts, notes)
    """
    try:
        failure_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "commit_hash": commit_hash,
            "repository": repository,
            "commit_message": commit_message,
            "error": error_msg,
            "llm_response_complete": raw_response,
            "llm_response_excerpt": raw_response,
            "analysis_attempt": "JSON parsing failed",
            "prompt_excerpt": prompt_excerpt,
        }
        if extra_fields:
            failure_entry.update(extra_fields)
        
        existing_failures = []
        if os.path.exists(failures_file):
            try:
                with open(failures_file, 'r', encoding='utf-8') as f:
                    existing_failures = json.load(f)
            except json.JSONDecodeError:
                existing_failures = []
        
        existing_failures.append(failure_entry)
        
        with open(failures_file, 'w', encoding='utf-8') as f:
            json.dump(existing_failures, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Falha no logger não deve interromper a análise
```

**Callers que precisam ser atualizados (4 sites de chamada):**
- `llm_handler.py:276-283` → `save_json_failure(self.failures_file, ..., extra_fields={"parse_attempts": 1, "notes": "..."})`
- `llm_handler.py:335-342` → idem
- `optimized_llm_handler.py:555` → `save_json_failure(self.failures_file, ...)`
- `optimized_llm_handler.py:620` → idem

**Remover** os métodos `save_json_failure` de ambas as classes (manter apenas como atributo `self.failures_file`).

#### 1.4 Criar `src/utils/llm_sizing.py`

**Comparação das implementações:**

`llm_handler.py:49-66`:
```python
def estimate_token_count(text: str) -> int:   # L49-52
    if not text: return 0
    return max(1, len(text)//4)

def dynamic_num_ctx(diff_text: str) -> int:    # L54-60 — SEM model_name
    tokens = estimate_token_count(diff_text)
    if tokens < 3000: return 2048              # ← valor menor
    if tokens < 6000: return 4096
    return 6144                                 # ← max menor

def reduce_diff_simple(diff_text: str, max_chars: int = 50000) -> tuple[str, dict]:  # L62-66
    if len(diff_text) <= max_chars:
        return diff_text, {"reduced": False}
    truncated = diff_text[:max_chars]
    return truncated + "\n... (truncado)", {"reduced": True, ...}
```

`optimized_llm_handler.py:146-210`:
```python
def estimate_token_count(text: str) -> int:   # L146-150 — IDÊNTICA
    if not text: return 0
    return max(1, len(text) // 4)

def dynamic_num_ctx(diff_text: str, model_name: str = "") -> int:  # L152-173 — COM model_name
    tokens = estimate_token_count(diff_text)
    is_deepseek = "deepseek" in model_name.lower()
    if is_deepseek:
        if tokens < 2000: return 3072
        elif tokens < 4000: return 4096
        else: return 4096                       # DeepSeek capped
    else:
        if tokens < 3000: return 4096           # ← valor maior que llm_handler
        if tokens < 6000: return 6144
        if tokens < 9000: return 8192           # ← tier extra
        return 8192                              # ← max maior

def reduce_diff(diff_text: str, max_chars: int = 60000,    # L175-210
                per_file_line_limit: int = 400) -> tuple[str, dict]:
    # Per-file line limiting + global truncation (mais sofisticado)
```

**Versão unificada** — `src/utils/llm_sizing.py`:

```python
"""Estimativa de tokens, sizing de contexto, e redução de diffs."""
from typing import Optional

def estimate_token_count(text: str) -> int:
    """Estimativa grosseira: ~4 chars/token."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def dynamic_num_ctx(diff_text: str, model_name: str = "") -> int:
    """Calcula num_ctx dinâmico baseado no tamanho do diff.
    
    Merge de llm_handler.py:54-60 e optimized_llm_handler.py:152-173.
    Usa a versão optimized (superset) como base.
    """
    tokens = estimate_token_count(diff_text)
    is_deepseek = "deepseek" in model_name.lower()
    
    if is_deepseek:
        if tokens < 2000: return 3072
        elif tokens < 4000: return 4096
        else: return 4096
    else:
        if tokens < 3000: return 4096
        if tokens < 6000: return 6144
        if tokens < 9000: return 8192
        return 8192

def reduce_diff(
    diff_text: str,
    max_chars: int = 60000,
    per_file_line_limit: int = 400,
) -> tuple[str, dict]:
    """Reduz diff grande com per-file line limit.
    
    Merge de reduce_diff_simple (llm_handler.py:62-66, truncamento simples)
    e reduce_diff (optimized_llm_handler.py:175-210, per-file limit).
    Usa a versão per-file como base (mais robusta).
    """
    # ... implementação do optimized_llm_handler.py:175-210
```

**Nota**: `reduce_diff_simple` (llm_handler) é um subset de `reduce_diff` (optimized) — pode ser completamente substituída.

**Callers que precisam ser atualizados:**
- `llm_handler.py:312-314`: `diff, reduced_meta = reduce_diff_simple(diff)` → `from src.utils.llm_sizing import reduce_diff; diff, meta = reduce_diff(diff)`
- `llm_handler.py:316`: `ctx = dynamic_num_ctx(diff)` → `ctx = dynamic_num_ctx(diff, model_name=self.model)`
- `optimized_llm_handler.py`: já usa as funções module-level — apenas mudar para importar de `llm_sizing`

**Funções removidas dos handlers:**
- `llm_handler.py:49-52` (`estimate_token_count`) — deletar
- `llm_handler.py:54-60` (`dynamic_num_ctx`) — deletar
- `llm_handler.py:62-66` (`reduce_diff_simple`) — deletar
- `optimized_llm_handler.py:146-150` (`estimate_token_count`) — deletar
- `optimized_llm_handler.py:152-173` (`dynamic_num_ctx`) — deletar
- `optimized_llm_handler.py:175-210` (`reduce_diff`) — mover para llm_sizing.py

#### 1.5 Limpeza adicional identificada

**Imports não utilizados** a remover nesta fase:
- `llm_handler.py:33`: `import math` — nunca usado (grep confirma: 0 ocorrências de `math.`)
- `optimized_llm_handler.py:38`: `import math` — nunca usado

**Imports redundantes de json5** (3 cópias do mesmo try/except):
- `json_parser.py:8-11` — **manter** (canônico)
- `llm_handler.py:10-13` — manter (usado por `_extract_with_patterns` que faz `_json5.loads()`)
- `optimized_llm_handler.py:7-10` — manter (usado em métodos de reparo JSON)

Na Fase 3 (merge dos handlers), os imports redundantes serão naturalmente eliminados.

#### Resumo de impacto da Fase 1

| Ação | Linhas removidas | Linhas adicionadas | Local |
|------|------------------|--------------------|-------|
| Deletar extract_json_from_text duplicado #1 | 11 | 0 | llm_handler.py:36-46 |
| Deletar extract_json_from_text duplicado #2 | 23 | 0 | optimized_llm_handler.py:41-63 |
| Deletar _find_json_end_index método #1 | 21 | 1 (import) | llm_handler.py:528-548 |
| Deletar _find_json_end_index método #2 | 25 | 1 (import) | optimized_llm_handler.py:885-909 |
| Deletar _extract_final_classification #1 | 25 | 1 (import) | llm_handler.py:459-483 |
| Deletar _extract_final_classification #2 | 35 | 1 (import) | optimized_llm_handler.py:1036-1070 |
| Deletar save_json_failure #1 | 47 | 2 (import+call) | llm_handler.py:192-238 |
| Deletar save_json_failure #2 | 45 | 2 (import+call) | optimized_llm_handler.py:355-399 |
| Deletar estimate/dynamic/reduce #1 | 18 | 3 (imports) | llm_handler.py:49-66 |
| Mover estimate/dynamic/reduce #2 | 65 | 3 (imports) | optimized_llm_handler.py:146-210 |
| Remover `import math` x2 | 2 | 0 | ambos handlers |
| **Criar** classification.py | 0 | ~40 | novo arquivo |
| **Criar** failure_logger.py | 0 | ~45 | novo arquivo |
| **Criar** llm_sizing.py | 0 | ~55 | novo arquivo |
| **TOTAL** | **~317** | **~154** | **redução líquida: ~163 linhas** |

**Arquivos afetados**:
- `src/utils/json_parser.py` — sem mudanças (já é canônico)
- Novo `src/utils/classification.py` (~40 linhas)
- Novo `src/utils/failure_logger.py` (~45 linhas)
- Novo `src/utils/llm_sizing.py` (~55 linhas)
- `src/handlers/llm_handler.py` — remoção de ~124 linhas, adição de ~8 linhas de imports
- `src/handlers/optimized_llm_handler.py` — remoção de ~193 linhas, adição de ~8 linhas de imports

**Verificação**:
```bash
# Testes de caracterização da Fase 0 devem continuar passando
python -m pytest tests/test_char_json_parser.py tests/test_char_classification.py -v

# Verificar que cada função existe em exatamente um lugar
grep -rn "def extract_json_from_text" src/   # → 1 resultado (json_parser.py:88)
grep -rn "def _find_json_end_index" src/     # → 1 resultado (json_parser.py:14)
grep -rn "def extract_final_classification" src/  # → 1 resultado (classification.py)
grep -rn "def save_json_failure" src/        # → 1 resultado (failure_logger.py)
grep -rn "def estimate_token_count" src/     # → 1 resultado (llm_sizing.py)
grep -rn "def dynamic_num_ctx" src/          # → 1 resultado (llm_sizing.py)
grep -rn "def reduce_diff" src/              # → 1 resultado (llm_sizing.py)
grep -rn "import math" src/                  # → 0 resultados

# Novos testes unitários
python -m pytest tests/test_classification.py tests/test_failure_logger.py tests/test_llm_sizing.py -v
```

---

### Fase 2: Dataclass de Configuração

**Objetivo**: Substituir 21 valores mágicos hardcoded (contagem exata confirmada) por uma configuração tipada, documentada e centralizada.

**Risco**: Baixo — substitui literais por constantes.

#### 2.0 Inventário completo de magic values com locais exatos

| # | Valor | Significado | Local(is) exato(s) | Conflito? |
|---|-------|-------------|--------------------|----|
| 1 | `"http://localhost:11434/api/generate"` | Ollama host | `config.py:28` | Não |
| 2 | `"mistral"` | Modelo default | `config.py:31` | Não |
| 3 | `0.1` | Temperature | `llm_handler.py:93`, `optimized_llm_handler.py:249` | Não (igual) |
| 4 | `20000` | num_predict | `llm_handler.py:94` | **SIM** |
| 5 | `50000` | num_predict | `optimized_llm_handler.py:250` | **SIM** (20k vs 50k) |
| 6 | `4096` | num_ctx default | `llm_handler.py:92`, `optimized_llm_handler.py:239,248` | Não (igual) |
| 7 | `"10m"` | keep_alive | `llm_handler.py:90` | **SIM** |
| 8 | `"5m"` | keep_alive | `optimized_llm_handler.py:238` | **SIM** (10m vs 5m) |
| 9 | `"30s"` | keep_alive DeepSeek | `optimized_llm_handler.py:238` | N/A (DeepSeek only) |
| 10 | `120` | timeout (s) | `llm_handler.py:103` | **SIM** |
| 11 | `200` | timeout base (s) | `optimized_llm_handler.py:265,267` | **SIM** (120 vs 200) |
| 12 | `300` | timeout large (s) | `optimized_llm_handler.py:261,263` | N/A |
| 13 | `3` | retry attempts | `llm_handler.py:84` | **SIM** |
| 14 | `1` | retry attempts | `optimized_llm_handler.py:233` | **SIM** (3 vs 1) |
| 15 | `50000` | max_diff_chars | `llm_handler.py:62` | **SIM** |
| 16 | `60000` | max_diff_chars | `optimized_llm_handler.py:175` | **SIM** (50k vs 60k) |
| 17 | `100000` | max_direct_diff_size | `optimized_prompt.py:12` | N/A (file mode threshold) |
| 18 | `400` | per_file_line_limit | `optimized_llm_handler.py:175` | N/A |
| 19 | `"json_failures.json"` | failures file | `llm_handler.py:186`, `optimized_llm_handler.py:347` | Não (igual) |
| 20 | `True` / `2000` | debug flags | `config.py:124-125` | Não (já em config.py) |
| 21 | `"temp_diffs"` | temp diff dir | `optimized_prompt.py:13` | N/A |

**7 conflitos diretos** entre os dois handlers que precisam de resolução:

| Parâmetro | LLMHandler | OptimizedLLMHandler | **Valor unificado proposto** | Justificativa |
|-----------|-----------|-------------------|--------------------------|--------------|
| num_predict | 20.000 | 50.000 | **50.000** | Respostas longas são mais confiáveis |
| keep_alive | `"10m"` | `"5m"` | **`"5m"`** | Menor consumo de VRAM; 10m não traz benefício |
| timeout | 120s fixo | 200-300s dinâmico | **200s base / 300s large** | Dinâmico é mais robusto para diffs grandes |
| max_retries | 3 | 1 | **2** | Compromisso: 1 é pouco, 3 é lento para modelos lentos |
| max_diff_chars | 50.000 | 60.000 | **60.000** | O optimized usa 60k; truncar mais cedo perde informação |

#### 2.1 Criar `src/core/settings.py`

```python
"""Configuração centralizada do Refan — substitui todos os magic values."""
from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Optional

@dataclass
class RefanSettings:
    """Configuração global do sistema.
    
    Todos os valores que antes eram hardcoded nos handlers estão aqui.
    Cada campo documenta o valor anterior e a justificativa do default.
    """
    
    # === Conexão LLM ===
    # Fonte original: config.py:28
    ollama_host: str = "http://localhost:11434/api/generate"
    # Fonte: config.py:31, env REFAN_LLM_MODEL
    llm_model: str = field(
        default_factory=lambda: os.environ.get("REFAN_LLM_MODEL", "mistral")
    )
    
    # === Parâmetros de geração ===
    # Fonte: llm_handler.py:93, optimized_llm_handler.py:249 (ambos 0.1)
    temperature: float = 0.1
    # Fonte: llm_handler.py:94 (20k) vs optimized_llm_handler.py:250 (50k) → unificado para 50k
    num_predict: int = 50000
    # Fonte: llm_handler.py:90 ("10m") vs optimized_llm_handler.py:238 ("5m") → "5m"
    keep_alive: str = "5m"
    # Fonte: optimized_llm_handler.py:238 ("30s" se DeepSeek)
    keep_alive_deepseek: str = "30s"
    # Fonte: llm_handler.py:92, optimized_llm_handler.py:239,248
    default_num_ctx: int = 4096
    
    # === Retry e timeout ===
    # Fonte: llm_handler.py:84 (3) vs optimized_llm_handler.py:233 (1) → 2
    max_retries: int = 2
    # Fonte: llm_handler.py:103 (120) vs optimized_llm_handler.py:265 (200) → 200
    timeout_base_s: int = 200
    # Fonte: optimized_llm_handler.py:261 (300)
    timeout_large_s: int = 300
    # Threshold para timeout_large (chars de prompt)
    timeout_large_threshold: int = 50000
    
    # === Diff handling ===
    # Fonte: llm_handler.py:62 (50k) vs optimized_llm_handler.py:175 (60k) → 60k
    max_diff_chars: int = 60000
    # Fonte: optimized_prompt.py:12 (100k)
    max_diff_chars_file: int = 100000
    # Fonte: optimized_llm_handler.py:175
    per_file_line_limit: int = 400
    # Fonte: optimized_prompt.py:13
    temp_diff_dir: str = "temp_diffs"
    
    # === Debug ===
    # Fonte: config.py:124
    show_prompt: bool = True
    # Fonte: config.py:125
    max_prompt_display_length: int = 2000
    # Fonte: config.py:128
    reset_model_context: bool = True
    # Fonte: config.py:129
    use_random_seed: bool = True
    
    # === GPU ===
    # Fonte: config.py:141-145
    num_gpu_layers: Optional[int] = field(
        default_factory=lambda: (
            int(v) if (v := os.environ.get("REFAN_NUM_GPU_LAYERS")) else None
        )
    )
    
    # === Paths ===
    project_root: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent
    )
    
    # === Failure tracking ===
    # Fonte: llm_handler.py:186, optimized_llm_handler.py:347
    failures_file: str = "json_failures.json"
    
    def to_dict(self) -> dict:
        """Serializa para logging de reprodutibilidade."""
        return {
            k: str(v) if isinstance(v, Path) else v
            for k, v in self.__dict__.items()
        }
    
    def get_timeout(self, prompt_size: int) -> int:
        """Retorna timeout dinâmico baseado no tamanho do prompt."""
        if prompt_size > self.timeout_large_threshold:
            return self.timeout_large_s
        return self.timeout_base_s
    
    def get_keep_alive(self, model_name: str = "") -> str:
        """Retorna keep_alive baseado no modelo."""
        if "deepseek" in model_name.lower():
            return self.keep_alive_deepseek
        return self.keep_alive
```

#### 2.2 Migrar `src/core/config.py`

O `config.py` atual (278 linhas) define 15 constantes module-level + 7 funções. A migração deve:

1. **Criar instância singleton** no topo do módulo:
   ```python
   from src.core.settings import RefanSettings
   settings = RefanSettings()
   ```

2. **Manter aliases de compatibilidade** para evitar quebrar todos os 20+ import sites de uma vez:
   ```python
   # Aliases legados — remover gradualmente nas fases seguintes
   LLM_HOST = settings.ollama_host
   LLM_MODEL = settings.llm_model
   LLM_PROMPT = ...  # manter — é texto longo, não um magic value
   DEBUG_SHOW_PROMPT = settings.show_prompt
   DEBUG_MAX_PROMPT_LENGTH = settings.max_prompt_display_length
   RESET_MODEL_CONTEXT = settings.reset_model_context
   USE_RANDOM_SEED = settings.use_random_seed
   JSON_STRUCTURE = ...  # manter — é uma estrutura, não config
   ```

3. **Migrar `set_llm_model()` / `get_current_llm_model()`** para delegar a settings:
   ```python
   def set_llm_model(model_name: str):
       settings.llm_model = model_name
       # recalcular paths...
   
   def get_current_llm_model() -> str:
       return settings.llm_model
   ```

4. **Mover `get_model_paths()`** para ser método de settings (já planejado acima).

5. **Migrar `get_generation_base_options()`** — atualmente em `config.py:147-156`, usa `NUM_GPU_LAYERS`:
   ```python
   def get_generation_base_options():
       opts = {}
       if settings.num_gpu_layers and settings.num_gpu_layers > 0:
           opts["num_gpu_layers"] = settings.num_gpu_layers
       return opts
   ```

**Constantes que NÃO migram para settings** (são dados, não configuração):
- `CSV_PATH`, `PURITY_CSV_PATH`, `REPO_DIR` — derivados de `project_root`
- `LLM_PROMPT` — texto longo do prompt, não um parâmetro numérico
- `JSON_STRUCTURE` — template de saída

#### 2.3 Mapa de substituição nos handlers

**`src/handlers/llm_handler.py`** — 8 substituições:

| Linha | Antes | Depois |
|-------|-------|--------|
| L84 | `attempts: int = 3` | `attempts: int = settings.max_retries` |
| L90 | `keep_alive ... "10m"` | `settings.get_keep_alive(self.model)` |
| L92 | `"num_ctx": num_ctx or 4096` | `"num_ctx": num_ctx or settings.default_num_ctx` |
| L93 | `"temperature": 0.1` | `"temperature": settings.temperature` |
| L94 | `"num_predict": 20000` | `"num_predict": settings.num_predict` |
| L103 | `timeout=120` | `timeout=settings.get_timeout(len(prompt))` |
| L186 | `self.failures_file = "json_failures.json"` | `self.failures_file = settings.failures_file` |
| L62 | `max_chars: int = 50000` | removido (Fase 1 já migrou para `llm_sizing.py`) |

**`src/handlers/optimized_llm_handler.py`** — 11 substituições:

| Linha | Antes | Depois |
|-------|-------|--------|
| L233 | `attempts: int = 1` | `attempts: int = settings.max_retries` |
| L238 | `"30s" if is_deepseek else "5m"` | `settings.get_keep_alive(self.model)` |
| L239 | `4096 if is_deepseek else (num_ctx or 4096)` | `num_ctx or settings.default_num_ctx` |
| L249 | `"temperature": 0.1` | `"temperature": settings.temperature` |
| L250 | `"num_predict": 50000` | `"num_predict": settings.num_predict` |
| L261 | `timeout = 300` | `timeout = settings.get_timeout(prompt_size)` |
| L263 | `timeout = 300` | (coberto pelo acima) |
| L265 | `timeout = 200` | (coberto pelo acima) |
| L267 | `timeout = 200` | (coberto pelo acima) |
| L347 | `self.failures_file = "json_failures.json"` | `self.failures_file = settings.failures_file` |
| L175 | `max_chars: int = 60000, per_file_line_limit: int = 400` | removido (Fase 1 já migrou) |

**`src/analyzers/optimized_prompt.py`** — 2 substituições:

| Linha | Antes | Depois |
|-------|-------|--------|
| L12 | `MAX_DIRECT_DIFF_SIZE = 100000` | `MAX_DIRECT_DIFF_SIZE = settings.max_diff_chars_file` |
| L13 | `TEMP_DIFF_DIR = "temp_diffs"` | `TEMP_DIFF_DIR = settings.temp_diff_dir` |

**`src/core/config.py`** — 5 substituições (migrar para settings):

| Linha | Antes | Depois |
|-------|-------|--------|
| L28 | `LLM_HOST = "http://..."` | `LLM_HOST = settings.ollama_host` |
| L124 | `DEBUG_SHOW_PROMPT = True` | `DEBUG_SHOW_PROMPT = settings.show_prompt` |
| L125 | `DEBUG_MAX_PROMPT_LENGTH = 2000` | `DEBUG_MAX_PROMPT_LENGTH = settings.max_prompt_display_length` |
| L128 | `RESET_MODEL_CONTEXT = True` | `RESET_MODEL_CONTEXT = settings.reset_model_context` |
| L129 | `USE_RANDOM_SEED = True` | `USE_RANDOM_SEED = settings.use_random_seed` |

**Total: 26 substituições** em 4 arquivos.

#### 2.4 Edge case: import circular

**Risco**: `settings.py` importa `Path` e `os`. O `config.py` importa `settings`. Se algum módulo importar de `config.py` no nível de módulo e `settings.py` também importar algo de `config.py`, há risco de circular import.

**Mitigação**: `settings.py` **não importa nada de `src/`** — é self-contained com apenas `dataclasses`, `pathlib`, `os`, `typing`. Isso garante que não há risco de circular import.

**Arquivos afetados**:
- Novo `src/core/settings.py` (~100 linhas)
- Modificado `src/core/config.py` (~20 linhas alteradas)
- Modificado `src/handlers/llm_handler.py` (8 substituições)
- Modificado `src/handlers/optimized_llm_handler.py` (11 substituições)
- Modificado `src/analyzers/optimized_prompt.py` (2 substituições)

**Verificação**:
```bash
# Magic values não devem existir fora de settings.py
grep -rn '"10m"\|"5m"\|"30s"' src/handlers/ src/analyzers/  # → 0 resultados
grep -rn 'timeout=120\|timeout=200\|timeout=300' src/       # → 0 resultados
grep -rn '"json_failures.json"' src/                         # → 0 resultados
grep -rn 'temperature.*0\.1' src/handlers/                   # → 0 resultados
grep -rn 'num_predict.*20000\|num_predict.*50000' src/handlers/  # → 0 resultados
grep -rn 'attempts.*=.*[13],' src/handlers/                  # → 0 resultados (exceto assinaturas que usam settings)

# Teste unitário
python -m pytest tests/test_settings.py -v  # verifica defaults, to_dict(), get_timeout(), get_keep_alive()

# Import smoke test
python -c "from src.core.settings import RefanSettings; s = RefanSettings(); print(s.to_dict())"
```

---

### Fase 3: Fundir os Dois LLM Handlers

**Objetivo**: Eliminar o sistema paralelo de handlers, criando um único `LLMHandler` com o superset de funcionalidades.

**Risco**: **Alto** — diferenças sutis em edge cases. Mitigação: testes de caracterização da Fase 0.

#### 3.1 Inventário completo de métodos em cada handler (pós Fases 1-2)

**`LLMHandler`** (`llm_handler.py`) — após remoções da Fase 1, resta:

| Método | Linhas | Presente no Optimized? | Decisão |
|--------|--------|----------------------|---------|
| `__init__` | L182-190 | Sim (L342-353) | Merge: aceitar prompt_template como parâmetro |
| `analyze_commit()` | L288-360 | Sim (L401-480) + `analyze_commit_refactoring()` (L482-535) | Usar optimized (mais completo, 2 entry points) |
| `_attempt_multiple_extractions()` | L240-286 | Não | Manter — útil como fallback extra |
| `_ensure_required_fields()` | L362-385 | Sim (parcial via `_validate_and_fix_json_fields` L911-1012) | Merge: optimized é superset |
| `print_prompt()` | L387-399 | Sim (L1013-1034) | Idênticos — manter um |
| `_extract_json_from_response()` | L401-457 | Equivalente via `_process_llm_response()` (L537-654) | Usar `_process_llm_response` (mais robusto) |
| `_extract_with_patterns()` | L485-526 | Parcialmente em `_attempt_json_repair` (L782-883) | Merge |
| `_extract_with_line_parsing()` | L550-577 | Absorvido por `_extract_analysis_from_raw_text` (L656-730) | Usar optimized |
| `_extract_with_field_extraction()` | L579-602 | Absorvido acima | Usar optimized |
| `_validate_basic_structure()` | L604-610 | Sim (similar) | Manter |
| `_create_fallback_result()` | L612-658 | Sim (similar em `_process_llm_response`) | Merge |

**`OptimizedLLMHandler`** (`optimized_llm_handler.py`) — métodos únicos a manter:

| Método | Linhas | Descrição | Decisão |
|--------|--------|-----------|---------|
| `CSVDataLoader` (classe) | L69-141 | Carrega CSVs para autopreenchimento | Manter como dependência injetável |
| `OptimizedOllamaAdapter._track_deepseek_performance()` | L300-317 | Tracking de performance DeepSeek | Manter como opt-in |
| `OptimizedOllamaAdapter._reset_deepseek_context()` | L319-337 | Reset em timeout | Manter |
| `analyze_commit_refactoring()` | L482-535 | Entry point usado pelo `LLMPurityAnalyzer` | **Manter** — é o principal entry point |
| `_process_llm_response()` | L537-654 | Pipeline completo de processamento | **Adotar** como método principal |
| `_extract_analysis_from_raw_text()` | L656-730 | Extração textual quando JSON falha | Manter |
| `_retry_analysis_with_simplified_prompt()` | L731-780 | Retry com prompt simplificado | **Corrigir bug L764** e manter |
| `_attempt_json_repair()` | L782-883 | Reparo de JSON malformado | Manter |
| `_fix_quotes_in_json()` | L848-883 | Fix de aspas quebradas | Manter |
| `_validate_and_fix_json_fields()` | L911-1012 | Validação com dados CSV | Manter (superset do `_ensure_required_fields`) |
| `get_stats()` | L1072-1086 | Estatísticas de config | Manter |

#### 3.2 Criar handler unificado

O handler unificado em `src/handlers/llm_handler.py` combina:

```python
from src.core.settings import RefanSettings
from src.analyzers.optimized_prompt import (
    OPTIMIZED_LLM_PROMPT, build_optimized_commit_prompt_with_file_support,
    cleanup_temp_diff_file
)
from src.utils.json_parser import extract_json_from_text, _find_json_end_index
from src.utils.classification import extract_final_classification, PURE, FLOSS
from src.utils.failure_logger import save_json_failure
from src.utils.llm_sizing import estimate_token_count, dynamic_num_ctx, reduce_diff

class OllamaAdapter:
    """Adaptador unificado — merge de OllamaAdapter + OptimizedOllamaAdapter."""
    
    def __init__(self, host: str, model: str, settings: RefanSettings):
        self.host = host
        self.model = model
        self.settings = settings
        self._deepseek_stats = []  # opt-in tracking
    
    def complete(self, prompt: str, attempts: int | None = None, 
                 num_ctx: int | None = None) -> Optional[str]:
        attempts = attempts or self.settings.max_retries
        keep_alive = self.settings.get_keep_alive(self.model)
        timeout = self.settings.get_timeout(len(prompt))
        # ... lógica do optimized adapter (L233-297) com settings
    
    # DeepSeek-specific (opt-in, do optimized L300-337)
    def _track_deepseek_performance(self, duration, prompt_size): ...
    def _reset_deepseek_context(self): ...

class CSVDataLoader:
    """Carregador de dados CSV — movido do optimized handler (L69-141)."""
    ...

class LLMHandler:
    """Handler unificado — merge de LLMHandler + OptimizedLLMHandler."""
    
    def __init__(self, model=None, host=None, prompt_template=None,
                 settings=None, csv_dir="csv"):
        self.settings = settings or get_default_settings()
        self.model = model or self.settings.llm_model
        self.host = host or self.settings.ollama_host
        self.prompt_template = prompt_template or OPTIMIZED_LLM_PROMPT
        self.failures_file = self.settings.failures_file
        self.csv_loader = CSVDataLoader(csv_dir)
        self.adapter = OllamaAdapter(self.host, self.model, self.settings)
    
    # === Entry points ===
    def analyze_commit(self, ...):  # do LLMHandler original
    def analyze_commit_refactoring(self, ...):  # do OptimizedLLMHandler
    
    # === Response processing (do optimized) ===
    def _process_llm_response(self, ...):  # L537-654 do optimized
    def _extract_analysis_from_raw_text(self, ...):  # L656-730
    def _retry_analysis_with_simplified_prompt(self, ...):  # L731-780 (com fix L764)
    
    # === JSON repair (do optimized) ===
    def _attempt_json_repair(self, ...):  # L782-883
    def _fix_quotes_in_json(self, ...):  # L848-883
    
    # === Validation (merge) ===
    def _validate_and_fix_json_fields(self, ...):  # L911-1012 do optimized
    def _validate_basic_structure(self, ...):  # L604-610 do LLMHandler
    
    # === Fallbacks (do LLMHandler) ===
    def _attempt_multiple_extractions(self, ...):  # L240-286
    def _create_fallback_result(self, ...):  # L612-658
    
    # === Utilities ===
    def print_prompt(self, ...):  # qualquer versão
    def get_stats(self):  # L1072-1086 do optimized
```

#### 3.3 Corrigir o bug `_call_ollama` (CRÍTICO)

```python
# ANTES (optimized_llm_handler.py:764):
response = self._call_ollama(simplified_prompt, model=self.model, attempts=2)
# ↑ _call_ollama NÃO EXISTE na classe — crash em runtime!

# DEPOIS:
response = self.adapter.complete(simplified_prompt, attempts=2)
```

#### 3.4 Simplificar `src/core/main.py`

`main.py` tem 2 funções de processamento quase idênticas:
- `process_commits()` (L132-232) — usa `LLMHandler`
- `process_commits_optimized()` (L234-?) — usa `OptimizedLLMHandler`

Ambas fazem: loop commits → clone repo → get diff → call handler → save result.
Diferença: apenas qual handler instanciam.

**Ação**: Fundir em uma única `process_commits(handler: LLMHandler, commits_data, ...)`. O menu escolhe qual prompt_template passar ao criar o handler.

#### 3.5 Atualizar todos os imports

Sites que importam `OptimizedLLMHandler` e precisam ser atualizados:

| Arquivo | Linha | Import atual | Novo import |
|---------|-------|-------------|-------------|
| `llm_purity_analyzer.py` | L7 | `from src.handlers.optimized_llm_handler import OptimizedLLMHandler` | `from src.handlers.llm_handler import LLMHandler` |
| `main.py` | L23 | `from src.handlers.optimized_llm_handler import OptimizedLLMHandler` | remover |
| `test_csv_improvements.py` | L18,62,83,126 | `from src.handlers.optimized_llm_handler import ...` | atualizar |
| `test_fixes.py` | L16 | `from src.handlers.optimized_llm_handler import OptimizedLLMHandler` | atualizar |
| `test_json_fields.py` | L19 | `from src.handlers.optimized_llm_handler import OptimizedLLMHandler` | atualizar |
| `test_single_analysis.py` | L21 | `from src.analyzers.optimized_llm_handler import OptimizedLLMHandler` | **BUG** — caminho errado, corrigir |

#### 3.6 Deletar `src/handlers/optimized_llm_handler.py`

Após merge, o arquivo de 1.086 linhas é completamente absorvido pelo handler unificado.

**Estimativa de tamanho do handler unificado**: ~550-600 linhas (vs 660 + 1086 = 1746 atuais).

**Arquivos afetados**:
- `src/handlers/llm_handler.py` — reescrito (~600 linhas, era 660)
- **Deletar** `src/handlers/optimized_llm_handler.py` (1.086 linhas)
- `src/core/main.py` — 2 funções → 1 (~100 linhas removidas)
- `src/analyzers/llm_purity_analyzer.py` — atualizar import
- `src/core/menu_analysis.py` — atualizar import
- 4+ arquivos de teste — atualizar imports

**Verificação**:
```bash
python -m pytest tests/ -v -m "not slow"  # Testes de caracterização passam
grep -rn "OptimizedLLMHandler\|optimized_llm_handler" src/  # → 0 resultados
grep -rn "_call_ollama" src/  # → 0 resultados (bug corrigido)
python -c "from src.handlers.llm_handler import LLMHandler; h = LLMHandler(); print(h.get_stats())"
```

---

### Fase 4: Corrigir Error Handling e Logging

**Objetivo**: Eliminar anti-patterns de error handling e introduzir logging estruturado.

**Risco**: Baixo — correções pontuais.

#### 4.1 Inventário de bare `except:` com contexto exato

**Total confirmado: 6 instâncias** (3 serão eliminadas pela Fase 1, restam 3 pós-merge):

| # | Arquivo | Linha | Contexto | Exceção correta | Status pós-Fase 1 |
|---|---------|-------|----------|----------------|-------------------|
| 1 | `llm_handler.py` | L44 | `json.loads()` em extract_json morto | `json.JSONDecodeError` | **Eliminado** (Fase 1 deleta L36-46) |
| 2 | `optimized_llm_handler.py` | L61 | `json.loads()` em extract_json duplicado | `json.JSONDecodeError` | **Eliminado** (Fase 1 deleta L41-63) |
| 3 | `optimized_llm_handler.py` | L840 | `json.loads()` em `_attempt_json_repair` | `json.JSONDecodeError` | **Migra** para handler unificado — corrigir |
| 4 | `llm_visualization_handler.py` | L395 | Estimativa de `total_commits` | `Exception` | Corrigir |
| 5 | `visualization_handler.py` | L417 | `fig.write_image()` (kaleido) | `Exception` (ou `ImportError, OSError`) | Corrigir |
| 6 | `visualization_handler.py` | L433 | `repo_url.split('/')` | `(AttributeError, IndexError)` | Corrigir |

**Ações para os 3 restantes pós-Fases 1-3:**

```python
# #3 — handler unificado (ex-optimized L840):
# ANTES:
except:
    continue
# DEPOIS:
except (json.JSONDecodeError, ValueError):
    continue

# #4 — llm_visualization_handler.py:395:
# ANTES:
except:
    total_commits = 10000
# DEPOIS:
except (ValueError, KeyError, TypeError):
    total_commits = 10000

# #5 — visualization_handler.py:417:
# ANTES:
except:
    print(warning("Erro ao salvar PNG (instale kaleido: pip install kaleido)"))
# DEPOIS:
except Exception as e:
    print(warning(f"Erro ao salvar PNG: {e} (instale kaleido: pip install kaleido)"))

# #6 — visualization_handler.py:433:
# ANTES:
except:
    return 'Unknown'
# DEPOIS:
except (AttributeError, IndexError):
    return 'Unknown'
```

#### 4.2 Inventário completo de `os.chdir()` em `git_handler.py`

**13 instâncias** de `os.chdir()` em 4 métodos (confirmado por grep):

| Método | Linhas | Pattern | Instâncias de chdir |
|--------|--------|---------|-------------------|
| `ensure_repo_cloned()` | L39-96 | chdir→fetch→chdir back | L58, L70 (2) |
| `commit_exists()` | L98-130 | chdir→cat-file→chdir back (+except) | L112, L123, L129 (3) |
| `get_commit_diff()` | L132-185 | chdir→diff→chdir back (+2 excepts) | L147, L158, L179, L184 (4) |
| `get_commit_message()` | L187-225 | chdir→log→chdir back (+2 excepts) | L201, L213, L219, L224 (4) |

**Transformação para cada método** (exemplo `ensure_repo_cloned`):

```python
# ANTES (L57-70):
original_dir = os.getcwd()
os.chdir(repo_path)
result = subprocess.run(["git", "fetch", "--all"], ...)
os.chdir(original_dir)

# DEPOIS:
result = subprocess.run(["git", "fetch", "--all"], ..., cwd=repo_path)
```

**Para `get_commit_diff`** — caso especial: usa `subprocess.PIPE` sem `text=True` e decodifica manualmente (L150-173). O parâmetro `cwd` funciona com `PIPE` sem problemas.

**Nota**: `ensure_repo_cloned` usa `git clone` (L78-84) que **não** precisa de cwd (já recebe repo_path como argumento). Apenas o `git fetch` precisa.

**Redução**: ~40 linhas removidas (13 chdir calls + 4 `original_dir = os.getcwd()` + padrões de restore em excepts).

#### 4.3 Introduzir logging estruturado

Criar `src/utils/logging_config.py`:

```python
"""Configuração centralizada de logging para o Refan."""
import logging
import sys

_configured = False

def get_logger(name: str) -> logging.Logger:
    """Retorna logger configurado para o módulo."""
    global _configured
    logger = logging.getLogger(f"refan.{name}")
    
    if not _configured:
        root = logging.getLogger("refan")
        root.setLevel(logging.INFO)
        
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        ))
        root.addHandler(handler)
        _configured = True
    
    return logger
```

**Migração gradual** — prioridade para handlers (onde os problemas são mais graves):

1. `git_handler.py` — substituir `print(error(...))` por `logger.error(...)` (6 chamadas)
2. Handler unificado — substituir print calls nos métodos de processamento
3. Visualization handlers — substituir nos métodos de geração
4. Core (main.py, menu_analysis.py) — **não migrar** nesta fase (são UI, print é intencional)

**Arquivos afetados**:
- `src/handlers/git_handler.py` — remover 13 `os.chdir`, ~40 linhas a menos
- Handler unificado — corrigir bare except #3
- `src/handlers/visualization_handler.py` — corrigir bare except #5, #6
- `src/handlers/llm_visualization_handler.py` — corrigir bare except #4
- Novo `src/utils/logging_config.py` (~25 linhas)

**Verificação**:
```bash
grep -rn "os\.chdir" src/              # → 0 resultados
grep -Prn "^\s+except:\s*$" src/       # → 0 resultados (bare except)
python -c "from src.utils.logging_config import get_logger; l = get_logger('test'); l.info('ok')"
python -m pytest tests/test_char_git_handler.py -v  # cwd kwarg verificado
```

---

### Fase 5: Padronizar Modelo de Dados

**Objetivo**: Eliminar o caos de nomes de campos definindo estruturas canônicas com camada de adaptação.

**Risco**: Médio — muda fluxo de dados. Mitigação: camada de adaptação preserva compatibilidade com CSVs existentes.

#### 5.1 Criar `src/models/__init__.py` e `src/models/commit.py`

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CommitPair:
    """Par de commits para análise de refatoração."""
    repository: str
    commit_hash_before: str     # canônico (era: commit1)
    commit_hash_current: str    # canônico (era: commit2)
    project_name: str = ""
    commit_message: str = ""

@dataclass
class AnalysisResult:
    """Resultado de uma análise LLM de refatoração."""
    repository: str
    commit_hash_before: str
    commit_hash_current: str
    refactoring_type: str       # canônico: "pure" ou "floss"
    justification: str
    confidence_level: str = "medium"
    technical_evidence: str = ""
    llm_raw_response: str = ""  # canônico (era: llm_response_complete, llm_response_excerpt)
    extraction_method: str = ""
    diff_size_chars: int = 0
    diff_lines: int = 0
    processing_method: str = "direct"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True
```

#### 5.2 Criar `src/models/adapters.py`

```python
def commit_from_csv_row(row: pd.Series) -> CommitPair:
    """Mapeia nomes de colunas do CSV para CommitPair."""
    return CommitPair(
        repository=row.get('project', row.get('repository', '')),
        commit_hash_before=row.get('commit1', row.get('commit_hash_before', '')),
        commit_hash_current=row.get('commit2', row.get('commit_hash_current', '')),
        project_name=row.get('project_name', ''),
    )

def analysis_to_csv_dict(result: AnalysisResult) -> dict:
    """Mapeia AnalysisResult de volta para formato CSV."""
    ...

def analysis_from_llm_response(raw_dict: dict, commit: CommitPair) -> AnalysisResult:
    """Normaliza variantes de nomes de campos do LLM."""
    ...
```

#### 5.3 Migrar código para usar dataclasses

**Mapa de ocorrências de nomes legados no `data_handler.py`** (confirmado por grep):
- `commit2` aparece em **16 linhas** (L40, 71, 105, 118, 119, 127, 155, 181, 213, 247, 288, 304, 315, 316, 320, 340)
- `commit_hash_current` aparece em **1 linha** (L40, como fallback)
- `commit1` aparece em **0 linhas** (data_handler não trabalha com hash anterior)

**Migração gradual** — a camada de adaptação permite adoção incremental:

1. **`DataHandler`** — converter `load_data()` para retornar DataFrame com colunas renomeadas via adapters; OU retornar list de `CommitPair`. A segunda opção é mais clean mas requer mudanças maiores nos callers.

2. **`LLMHandler.analyze_commit()`** — atualmente retorna `dict`. Converter para retornar `AnalysisResult` com `asdict()` disponível para backward compat.

3. **`LLMPurityAnalyzer._analyze_single_commit()`** (`llm_purity_analyzer.py:238-365`) — trabalha com dicts. Converter para `CommitPair` na entrada e `AnalysisResult` na saída.

4. **`_save_csv_data()`** (`llm_purity_analyzer.py:163-181`) — usa `df.to_csv()`. O adapter `analysis_to_csv_dict()` garante que os nomes de colunas no CSV não mudam.

**Arquivos afetados**: Novos `src/models/__init__.py`, `src/models/commit.py`, `src/models/adapters.py`; modificados `data_handler.py`, handler unificado, `llm_purity_analyzer.py`.
**Verificação**: Teste round-trip: CSV row → `CommitPair` → análise mockada → `AnalysisResult` → CSV dict → verificar nomes das colunas. Testes de caracterização passam.

---

### Fase 6: Persistência e Armazenamento

**Objetivo**: Parar de reescrever CSV inteiro a cada commit, implementar persistência incremental, limpar tracking no Git.

**Risco**: Médio — muda como dados são salvos. Mitigação: formato JSONL é mais robusto que o atual.

#### 6.1 Persistência incremental com JSONL

**Problema atual confirmado**: `_save_csv_data()` é chamado em **3 locais** do `llm_purity_analyzer.py`:
- L543: dentro do loop, após cada commit (reescreve CSV inteiro de 5000+ linhas)
- L559: no handler de CTRL+C
- L567: no final da sessão

Cada chamada faz `df.to_csv(self.csv_file_path, index=False)` — I/O proporcional ao tamanho total do dataset, não ao incremento.

**Solução — persistência incremental com JSONL:**

```
Sessão ativa:
  → Cada resultado → append em output/models/<model>/sessions/<timestamp>.jsonl
  → 1 linha JSON por commit analisado
  → open(file, 'a') — atomic append, sem leitura

Fim da sessão (ou CTRL+C gracioso):
  → Merge JSONL → CSV master (uma única reescrita)
  → Mover JSONL para sessions/completed/
```

Implementar em `src/utils/persistence.py`:
```python
class SessionWriter:
    """Escritor incremental de resultados de sessão."""
    def __init__(self, model_name: str, settings: RefanSettings):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_file = settings.project_root / "output" / "models" / model_name / "sessions" / f"{timestamp}.jsonl"
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
    
    def append(self, result: dict) -> None:
        with open(self.session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    def merge_to_csv(self, csv_path: str) -> int:
        """Lê JSONL e atualiza CSV master. Retorna contagem de merges."""
        ...
```

Comando `refan merge-sessions` para recuperação manual de sessões abandonadas.

#### 6.2 Melhorar failure tracking

**Problema atual confirmado**: `json_failures.json` tem **12MB** (confirmado por `du -sh`). Cada chamada a `save_json_failure()` faz: ler 12MB → parse JSON → append 1 entry → reescrever 12MB. Com ~500+ falhas, isso é O(n) por operação.

- **Migrar** `json_failures.json` (array JSON, read-modify-write) → `json_failures.jsonl` (append-only, O(1) por operação)
- **Rotação** automática quando > 5MB: renomear para `json_failures_<timestamp>.jsonl` e iniciar novo
- **Mover** para `output/models/<model>/failures/` (scoped por modelo)

**Nota**: a mudança no `failure_logger.py` (Fase 1.3) já prepara para isso — basta mudar de `json.dump(list)` para `f.write(json_line + '\n')`.

#### 6.3 Limpar `.gitignore`

Adicionar:
```gitignore
# Resultados e outputs (regeneráveis)
output/
json_failures.json
json_failures.jsonl

# Repositórios clonados (regeneráveis)
repositorios/

# Dados derivados
complete_unified_analysis.*
csv/llm_analysis_csv/
csv/*.backup_*

# Arquivos grandes
*.pdf
```

Usar `git rm --cached` para destrackear (tamanhos confirmados via `du -sh`):
```bash
git rm --cached json_failures.json                        # 12 MB
git rm --cached TCC-JoseMarinhoFalcaoNeto-*.pdf           #  1.3 MB
git rm --cached complete_unified_analysis.csv              #  428 KB
git rm --cached complete_unified_analysis.txt              #  428 KB (duplicado do .csv)
git rm --cached complete_unified_analysis_filtered_*.csv   #  173 KB
git rm --cached csv/hashes_no_rpt_purity_with_analysis.csv.backup_*
```
**Total liberado**: ~14.3 MB do repositório Git.

**Manter rastreados** (são inputs de pesquisa):
- `csv/commits_with_refactoring.csv`
- `csv/puritychecker_detailed_classification.csv`

#### 6.4 Estratégia de backups

- Um backup por sessão
- Max 5 retidos em `output/models/<model>/backups/`
- Auto-prune dos mais antigos

**Arquivos afetados**: `src/analyzers/llm_purity_analyzer.py`, novo `src/utils/persistence.py`, `.gitignore`.
**Verificação**: Rodar sessão mockada → JSONL cresce incrementalmente. Kill mid-session → JSONL consistente. Merge → CSV correto. `git status` mostra arquivos grandes removidos do tracking.

---

### Fase 7: Interface CLI

**Objetivo**: Tornar a ferramenta scriptável e automatizável — essencial para reprodutibilidade acadêmica.

**Risco**: Baixo — aditivo, não altera código existente.

#### 7.1 Implementar CLI com argparse

Criar `src/cli.py`:

```bash
# Analisar commits
python refan.py analyze --model mistral --limit 50 --skip-analyzed
python refan.py analyze --model deepseek-r1:8b --filter purity:TRUE --limit 100
python refan.py analyze --dry-run  # simula sem chamar LLM

# Ver progresso
python refan.py status --model mistral    # X/Y commits analisados

# Comparar com Purity
python refan.py compare --model mistral --output report.html

# Recuperar sessões
python refan.py merge-sessions --model mistral

# Menu interativo (backward compatible)
python refan.py interactive
python refan.py interactive --menu llm
```

#### 7.2 Backward compatibility

`python refan.py` sem argumentos → menu interativo (comportamento atual preservado).

#### 7.3 Integração com settings

Flags CLI sobrescrevem settings:
```bash
python refan.py analyze --temperature 0.2 --max-retries 3 --timeout 300
```

**Arquivos afetados**: Novo `src/cli.py`, modificado `refan.py`.
**Verificação**: `python refan.py analyze --model mistral --limit 1 --dry-run` completa sem erros. `python refan.py` mostra menu interativo.

---

### Fase 8: Consolidar Scripts

**Objetivo**: Reduzir 20 scripts para um conjunto organizado e mantido.

**Risco**: Nenhum — reorganização de diretórios.

#### 8.1 Nova estrutura

```
scripts/
  research/              # Scripts únicos de pesquisa (claramente rotulados)
    generate_three_model_report.py
    relatorio_final.py
    collect_llm_purity_stats.py
    improvements_summary.py
    focus_analysis.py
    detailed_hash_analysis.py
  data/                  # Utilitários de dados (mantidos)
    add_purity_columns.py
    validate_classifications.py
    compare_hashes.py
  deprecated/            # Referência apenas (não mantidos)
    recover_llm_analysis.py      # substituído por `refan merge-sessions`
    recover_json_analyses.py
    recover_complete_backups.py
    final_consolidation.py
    debug_analyzer.py
    demos/
```

#### 8.2 Substituir scripts de recovery

Os 4 scripts de recovery viram o comando `refan recover` (Fase 7).

#### 8.3 Limpar `tests/`

Após mover scripts que não são testes (Fase 0.3), renomear testes com nomes obscuros:
- `test_option5.py` → nome descritivo baseado no que testa
- `test_option6_complete.py` → nome descritivo

**Verificação**: Cada script retido importa sem erros.

---

### Fase 9: Limpar Imports de Colors

**Objetivo**: Eliminar wildcard imports e reduzir poluição de namespace.

**Risco**: Nenhum — mudança mecânica.

#### 9.1 Substituir `from src.utils.colors import *`

**9 módulos confirmados** com wildcard import (pós-Fase 3, 8 após deletar optimized_llm_handler):

| # | Arquivo | Linha |
|---|---------|-------|
| 1 | `src/handlers/git_handler.py` | L10 |
| 2 | `src/handlers/llm_handler.py` | L32 (handler unificado) |
| 3 | `src/handlers/data_handler.py` | L11 |
| 4 | `src/handlers/purity_handler.py` | L11 |
| 5 | `src/handlers/visualization_handler.py` | L14 |
| 6 | `src/handlers/llm_visualization_handler.py` | (buscar linha exata) |
| 7 | `src/analyzers/llm_purity_analyzer.py` | L19 |
| 8 | `src/core/menu_analysis.py` | L20 |
| 9 | `src/core/main.py` | L27 |

O `colors.py` exporta **12 funções**: `success`, `error`, `warning`, `info`, `bold`, `cyan`, `magenta`, `dim`, `highlight`, `header`, `progress`, `commit_info`.

Substituir em cada módulo por imports explícitos das funções realmente usadas:
```python
from src.utils.colors import success, error, warning, info, dim, header, progress, bold, cyan
```

**Mudança mecânica**: em cada arquivo, listar quais funções de colors são realmente chamadas e importar apenas essas.

#### 9.2 (Opcional) Adotar biblioteca `rich`

Benefícios:
- Progress bars profissionais (substituiria a classe manual `ProgressBar` em `llm_purity_analyzer.py:22-75`, 54 linhas)
- Tabelas formatadas para estatísticas
- Logging integrado com cores automáticas
- Painéis e markdown no terminal

**Verificação**: `grep "from src.utils.colors import \*" src/` → zero resultados.

---

### Fase 10: Documentação e Reprodutibilidade

**Objetivo**: Preparar o projeto para publicação acadêmica como parte da dissertação.

#### 10.1 `pyproject.toml` completo

```toml
[project]
name = "refan"
version = "2.0.0"
description = "Classificação de refatorações com LLMs"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "requests>=2.31",
    "plotly>=5.22",
    "kaleido>=0.2",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov"]
rich = ["rich>=13.0"]
json5 = ["json5>=0.9"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

#### 10.2 Atualizar `README.md`

- Interface CLI documentada
- Sistema de settings explicado
- Seção "Reproduzindo Resultados" para a dissertação
- Remover referências a features "não implementadas"

#### 10.3 Atualizar `CLAUDE.md`

Refletir a nova arquitetura pós-refatoração.

#### 10.4 Documentação de migração

- O que mudou entre versão TCC e versão mestrado
- Compatibilidade de formatos de dados
- Como re-executar análises do TCC com a nova ferramenta
- Valores harmonizados (quais magic values foram unificados e para qual valor)

---

## Grafo de Dependências entre Fases

```
Fase 0 (Testes) ────────────── pré-requisito de tudo
  │
Fase 1 (De-duplicar) ────────── depende de 0
  │
Fase 2 (Settings) ──────────── depende de 0
  │
Fase 3 (Merge handlers) ────── depende de 1 + 2
  │
Fase 4 (Error handling) ────── pode ser paralela com 3
  │
Fase 5 (Data models) ───────── depende de 3
  │
Fase 6 (Persistência) ──────── depende de 5
  │
Fase 7 (CLI) ───────────────── depende de 3 + 5
  │
Fase 8 (Scripts) ───────────── depende de 7
  │
Fase 9 (Colors) ────────────── independente, qualquer momento após 0
  │
Fase 10 (Docs) ─────────────── após todas as outras
```

**Parallelização possível**: Fases 4 e 9 podem rodar em paralelo com Fase 3.

---

## Avaliação de Risco

| Fase | Risco | Motivo | Mitigação |
|------|-------|--------|-----------|
| 0 (Testes) | Nenhum | Só adiciona arquivos | — |
| 1 (Utilitários) | Baixo | Consolida código idêntico | Testes de caracterização |
| 2 (Settings) | Baixo | Substitui literais | Verificação via grep |
| 3 (Merge handlers) | **Alto** | Diferenças sutis em edge cases | Testes extensivos + comparação de outputs |
| 4 (Error handling) | Baixo | Correções pontuais | Testes existentes |
| 5 (Data models) | Médio | Muda fluxo de dados | Camada de adaptação |
| 6 (Persistência) | Médio | Muda como dados são salvos | JSONL é mais robusto |
| 7 (CLI) | Baixo | Aditivo | Backward compatible |
| 8 (Scripts) | Nenhum | Reorganização | — |
| 9 (Colors) | Nenhum | Mecânico | — |
| 10 (Docs) | Nenhum | Documentação | — |

---

## Estimativa de Escopo

| Fase | Arquivos novos | Arquivos modificados | Arquivos deletados |
|------|---------------|---------------------|-------------------|
| 0 | 3-4 | 0 | 5-9 |
| 1 | 3 | 2 | 0 |
| 2 | 1 | 3 | 0 |
| 3 | 0 | 4 | 1 |
| 4 | 1 | 4 | 0 |
| 5 | 2 | 3 | 0 |
| 6 | 1 | 2 | 0 |
| 7 | 1 | 1 | 0 |
| 8 | 0 | 0 | 0 (reorganização) |
| 9 | 0 | 9+ | 0 |
| 10 | 1-2 | 2-3 | 0 |

---

## Nova Estrutura Proposta (Pós-Refatoração)

```
refan/
├── refan.py                      # Entry point (CLI dispatcher)
├── pyproject.toml                # Metadata, deps, tool config
├── CLAUDE.md
├── README.md
├── src/
│   ├── cli.py                    # Interface CLI (argparse)
│   ├── core/
│   │   ├── config.py             # Inicialização e compatibilidade
│   │   ├── settings.py           # RefanSettings dataclass
│   │   ├── main.py               # Menu interativo
│   │   └── menu_analysis.py      # Menu LLM
│   ├── models/
│   │   ├── commit.py             # CommitPair, AnalysisResult
│   │   └── adapters.py           # CSV ↔ dataclass mapping
│   ├── handlers/
│   │   ├── llm_handler.py        # Handler unificado + OllamaAdapter
│   │   ├── git_handler.py        # Operações Git (sem os.chdir)
│   │   ├── data_handler.py       # CSV loading/filtering
│   │   ├── purity_handler.py     # Baseline do Purity Checker
│   │   ├── visualization_handler.py
│   │   └── llm_visualization_handler.py
│   ├── analyzers/
│   │   ├── llm_purity_analyzer.py
│   │   └── optimized_prompt.py
│   └── utils/
│       ├── colors.py
│       ├── json_parser.py        # Extração JSON consolidada
│       ├── classification.py     # Constantes + extract_final_classification
│       ├── failure_logger.py     # Logging de falhas consolidado
│       ├── llm_sizing.py         # Token estimation + context sizing
│       ├── logging_config.py     # Logging estruturado
│       └── persistence.py        # JSONL sessions + merge
├── tests/
│   ├── conftest.py               # Fixtures comuns
│   ├── test_json_parser.py
│   ├── test_classification.py
│   ├── test_llm_handler.py
│   ├── test_git_handler.py
│   ├── test_data_handler.py
│   └── ...
├── scripts/
│   ├── research/
│   ├── data/
│   └── deprecated/
├── csv/                          # Dados de entrada (rastreados)
├── configs/
├── output/                       # Resultados (NÃO rastreados)
└── repositorios/                 # Repos clonados (NÃO rastreados)
```
