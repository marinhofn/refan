# Refan — Classificação de Refatorações com LLMs

Ferramenta de pesquisa acadêmica (mestrado PPGCC/UFCG) que classifica commits Git como
refatoração **pure** (estritamente estrutural) ou **floss** (misturada a mudanças
funcionais) usando LLMs locais via Ollama, comparando os resultados com o baseline do
**Purity Checker**. Originada no TCC (set/2025) e evoluída para o mestrado.

> Documentos de referência: `EVOLUTION_PLAN.md` (diagnóstico e roadmap vigente),
> `HARDENING_PLAN.md`, `ARCHITECTURE_PLAN.md`, `REFACTORING_PLAN.md` (históricos),
> `docs/PROMPTS.md` e `docs/REPRODUCIBILITY.md` (metodologia), `csv/README.md`
> (dicionário de dados), `CLAUDE.md` (política de rigor acadêmico do repositório).

## Estrutura do Projeto

```
refan/
├── refan.py                      # Entrada unificada (CLI com args | menu sem args)
├── src/
│   ├── cli.py                    # CLI headless: analyze, status, merge-sessions, interactive
│   ├── core/
│   │   ├── config.py             # Paths por modelo, health check Ollama
│   │   ├── settings.py           # RefanSettings: configuração central tipada
│   │   ├── main.py               # Menu interativo completo
│   │   └── menu_analysis.py      # Menu especializado de análise LLM
│   ├── handlers/
│   │   ├── llm_handler.py        # OllamaAdapter, prompts, extração de resposta
│   │   ├── git_handler.py        # Clone/fetch de repositórios, extração de diffs
│   │   ├── data_handler.py       # Leitura/filtragem dos CSVs
│   │   ├── purity_handler.py     # Baseline Purity Checker (consolidação FALSE>TRUE)
│   │   └── *visualization*.py    # Dashboards Plotly
│   ├── analyzers/
│   │   ├── llm_purity_analyzer.py  # Orquestrador principal (sessões JSONL + CSV)
│   │   └── optimized_prompt.py     # Prompt v2.0-mestrado (ver docs/PROMPTS.md)
│   ├── models/                   # CommitPair / AnalysisResult (canônicos) + adapters
│   ├── persistence/              # SupabaseClient (cloud opcional)
│   ├── runner/                   # CommandHandler (controle remoto via command_queue)
│   └── utils/                    # json_parser, persistence JSONL, timeutils, logging...
├── tests/                        # Suíte pytest offline (mocks; sem Ollama/rede)
├── scripts/
│   ├── data/                     # Manifesto do baseline, higiene, reconciliação Supabase
│   ├── research/                 # Análises ad-hoc da pesquisa
│   └── deprecated/               # Legado do TCC (não manter)
├── configs/prompts/              # Artefatos verbatim das versões de prompt (+SHA-256)
├── csv/                          # Dados de entrada e masters (ver csv/README.md)
├── docs/                         # PROMPTS.md, REPRODUCIBILITY.md
├── supabase/migrations/          # Schema SQL versionado do projeto cloud
├── baseline_tcc_2025/            # Snapshot IMUTÁVEL do TCC (Git LFS + MANIFEST.sha256)
└── output/models/<modelo>/       # Resultados por modelo (não versionado)
```

## Ambiente de Desenvolvimento

O projeto requer **Python >= 3.10** (o código usa sintaxe PEP 604, `str | None`).
No macOS, o Python do sistema (3.9.x) não é suficiente — use o 3.12 do Homebrew:

```bash
# Criar e ativar o ambiente virtual
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

# Instalação completa (runtime + dev + json5 + supabase)
pip install -e ".[dev,json5,supabase]"

# Verificar
python -m pytest tests/ -v -m "not slow"   # suíte offline (sem Ollama)
python refan.py --help                      # CLI
python scripts/data/check_repo_hygiene.py   # higiene do repositório
```

Para reprodução exata do ambiente de referência (dependências transitivas
congeladas): `pip install -r requirements-lock.txt`.

> Nota: o entry point instalado `refan` está quebrado no empacotamento atual
> (`EVOLUTION_PLAN.md`, ARQ-3; correção na Fase E5). Use `python refan.py`.

> **Importante**: mantenha o clone **fora** de diretórios sincronizados por
> iCloud/Drive/Dropbox — a sincronização cria cópias de conflito (`nome 2.ext`) e já
> corrompeu a working tree do baseline (incidente registrado em
> `docs/REPRODUCIBILITY.md` §5).

## Pré-requisitos de execução

- **Ollama** rodando localmente em `http://localhost:11434`, com os modelos já
  baixados (`ollama pull mistral`). Ollama é um serviço externo, não uma dependência
  pip.
- Modelo ativo: `--model` na CLI, menu interativo, ou env var `REFAN_LLM_MODEL`
  (default: `mistral`). Qualquer modelo disponível no Ollama local é utilizável; a
  pesquisa já exercitou mistral, deepseek-r1 (1.5b/8b), gemma2:2b, gemma3 (1b/4b) e
  gpt-oss:20b.
- Supabase (opcional, persistência cloud): configure `.env` a partir de
  `.env.example`. Sem `.env`, a ferramenta opera 100% local (JSONL + CSV).

## Como Usar

### CLI headless (recomendado para experimentos)

```bash
python refan.py analyze --model mistral --limit 50 --skip-analyzed
python refan.py analyze --model deepseek-r1:8b --filter TRUE --dry-run
python refan.py status --model mistral
python refan.py merge-sessions --model mistral
python refan.py interactive --menu llm
```

### Menus interativos

```bash
python refan.py            # seleção de modelo + escolha de interface
```

## Saídas e organização por modelo

```
output/models/<modelo>/
├── analises/               # JSONs de sessão + backups de master
│   └── sessions/           # JSONL incremental (1 linha por commit; crash-safe)
├── dashboards/             # Visualizações HTML/PNG
├── comparisons/            # Comparações LLM vs Purity
└── analises_completas/     # CSVs de lotes completos
```

Cada registro carrega `prompt_sha256` e `tool_version`; cada sessão grava um
`config_snapshot` completo — ver `docs/REPRODUCIBILITY.md`.

## Baseline do TCC (Git LFS)

O diretório `baseline_tcc_2025/` é o snapshot **imutável** dos resultados do
TCC (set/2025) — base de comparação dos experimentos do mestrado. Os 281
arquivos (130 MB) são versionados via **Git LFS**; para obtê-los após o clone:

```bash
brew install git-lfs   # uma única vez por máquina
git lfs install
git lfs pull
```

A integridade do snapshot é atestada por `baseline_tcc_2025/MANIFEST.sha256`:

```bash
python scripts/data/generate_baseline_manifest.py --verify
```

**Nunca modifique arquivos deste diretório** (política do projeto — ver
`CLAUDE.md` e `baseline_tcc_2025/README.md`).

## Testes

```bash
python -m pytest tests/ -v              # suíte completa offline (~200 testes, <1s)
python -m pytest tests/ -v -m "not slow"
```

CI (GitHub Actions): higiene do repositório + suíte em Python 3.10/3.11/3.12.
