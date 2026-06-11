# Testes do Refan

Suíte pytest do projeto. Todos os testes atuais executam **offline** (sem
Ollama, sem rede, sem Supabase) usando mocks e diretórios temporários.

## Requisitos

- Python >= 3.10 (o código de produção usa sintaxe PEP 604, `str | None`;
  em 3.9 a coleta falha — ver seção "Ambiente de Desenvolvimento" no README raiz)
- Dependências de desenvolvimento: `pip install -e ".[dev]"`

## Execução

```bash
# Suíte completa offline (padrão — todos os testes atuais)
python -m pytest tests/ -v

# Excluindo categorias marcadas (relevante quando houver testes marcados)
python -m pytest tests/ -v -m "not slow"
python -m pytest tests/ -v -m "not slow and not integration"
```

## Estrutura atual

| Arquivo | Alvo | Testes |
|---|---|---|
| `test_char_json_parser.py` | `src/utils/json_parser.py` — extração de JSON multi-estratégia | 32 |
| `test_char_classification.py` | `src/utils/classification.py` — padrões FINAL/CLASSIFICATION/RESULTADO | 20 |
| `test_char_git_handler.py` | `src/handlers/git_handler.py` — clone/fetch/diff (subprocess mockado) | 12 |
| `test_char_data_handler.py` | `src/handlers/data_handler.py` — commits analisados, formatos de campo | 4 |
| `test_char_prompt.py` | construção de prompts (`build_commit_prompt` + builder otimizado) | 11 |
| `test_json_parser.py` | casos adicionais de parsing JSON | 6 |
| `test_ollama_adapter.py` | `OllamaAdapter.complete()` — retry, monitoramento DeepSeek (requests mockado) | 6 |

Fixtures compartilhadas em `conftest.py`: `sample_commit_data`,
`sample_csv_dataframe`, `mock_ollama_response_factory`, `tmp_output_dir`.

## Marcadores

Declarados em `pyproject.toml` e reservados para testes que reintroduzam
dependências externas:

- `slow` — testes que requerem Ollama em execução ou rede
- `integration` — testes que dependem dos CSVs reais de `csv/`

## Histórico

Os testes de caracterização (`test_char_*.py`) foram criados na Fase 0 do
`REFACTORING_PLAN.md` para fixar o comportamento antes da refatoração v2.0,
e atualizados na Fase H2 do `HARDENING_PLAN.md` para as APIs unificadas.
Os antigos scripts demonstrativos sem asserções que viviam neste diretório
foram movidos para `scripts/deprecated/` na Fase H2.
