# Plano de Hardening e Reprodutibilidade — Refan (série v2.1)

## Contexto

A refatoração arquitetural v2.0.0 (Fases 0–10, `REFACTORING_PLAN.md`) e a integração de
persistência cloud (Fase 11, `ARCHITECTURE_PLAN.md`) deixaram o Refan funcionalmente sólido.
Um diagnóstico completo do repositório (junho/2026), porém, identificou lacunas na camada de
**rigor acadêmico** — reprodutibilidade, rastreabilidade, integridade de dados e verificação
contínua — que precisam ser fechadas antes da consolidação dos experimentos do mestrado:

1. **Defeito crítico (P0)**: a variável `is_deepseek` é referenciada sem definição em
   `OllamaAdapter.complete()` (`src/handlers/llm_handler.py:243,252`). O `NameError`
   resultante ocorre em **toda resposta bem-sucedida** do Ollama e é capturado pelo
   `except Exception` genérico do laço de retry, descartando a resposta válida do LLM.
2. **Build quebrado**: `pyproject.toml` declara um build backend inexistente
   (`setuptools.backends._legacy:_Backend`) e um entry point que não resolve
   (`cli:run_cli` em vez de `src.cli:run_cli`) — `pip install -e .` falha.
3. **Reprodutibilidade incompleta**: a flag `use_random_seed` existe mas nunca é consumida;
   timestamps são naive (sem timezone); o SHA256 do prompt não é calculado nem validado
   localmente; a versão da ferramenta não é registrada nos resultados; o baseline do TCC
   (130 MB, 281 arquivos) está fora do controle de versão.
4. **Verificação ausente**: zero CI; zero testes para os módulos novos do mestrado
   (`supabase_client`, `persistence`, `cli`, `settings`, `command_handler`); marcadores
   pytest declarados mas nunca aplicados.
5. **Persistência cloud frágil**: chamadas ao Supabase sem timeout nem retry; falhas
   silenciosas (`return None`); ausência de mecanismo de reconciliação JSONL ↔ cloud.

### Decisões metodológicas registradas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Versionamento do baseline TCC | **Git LFS** | Auditabilidade e recuperabilidade do snapshot de referência; repo permanece leve; integridade complementada por manifesto SHA256 |
| Flag `use_random_seed` | **Implementar seed fixo (42)** | Determinismo por modelo/versão via `options.seed` do Ollama; a diferença metodológica em relação ao baseline TCC (sem seed) é documentada como nova série experimental |
| Escopo | **Completo** | Críticos + qualidade + documentação, em fases priorizadas |

## Estratégia de Branches e Commits

Mesmos princípios do `REFACTORING_PLAN.md`: cada fase é uma branch mergeada com `--no-ff`
na branch de integração; cada sub-tarefa é um commit atômico em Conventional Commits cujo
corpo explica o *porquê*; o projeto permanece funcional (`pytest -m "not slow"` verde) a
cada merge; o histórico deve ser compreensível isoladamente por uma banca de pós-graduação.

A série usa numeração própria (`hardening/phase-N`, tags `v2.1.0-hardening-N`, versão alvo
**v2.1.0**) para não colidir com a Fase 12 (frontend) reservada no `ARCHITECTURE_PLAN.md`.

```
development
  └── hardening/v2.1-integration
        ├── hardening/phase-0/critical-fix
        ├── hardening/phase-1/build-and-dependencies
        ├── hardening/phase-2/test-suite-sanitation
        ├── hardening/phase-3/continuous-integration
        ├── hardening/phase-4/unit-test-coverage
        ├── hardening/phase-5/reproducibility
        ├── hardening/phase-6/supabase-robustness
        ├── hardening/phase-7/baseline-lfs
        ├── hardening/phase-8/code-quality
        └── hardening/phase-9/documentation
```

### Grafo de dependências

```
H0 (fix P0) ──→ todas
H1 (build/deps) ──→ H3        H2 (saneamento testes) ──→ H3 (CI)
H4 (testes unitários) ──→ H5, H6, H8
H7 (LFS) independente         H9 (docs) por último (consolida H5–H7)
```

---

## Fase H0 — Plano formal + correção do defeito crítico

**Branch:** `hardening/phase-0/critical-fix`

**Objetivo:** versionar este plano e eliminar o `NameError` que descarta respostas válidas
do Ollama em todas as chamadas bem-sucedidas de `OllamaAdapter.complete()`.

**Mudanças:**
- `HARDENING_PLAN.md` (este documento) na raiz do repositório.
- `src/handlers/llm_handler.py`: definir `is_deepseek = _settings.is_deepseek(self.model)`
  no início de `complete()` e reutilizar a variável no cálculo de `default_num_ctx`
  (que hoje refaz a checagem inline).
- `tests/test_ollama_adapter.py` (novo): testes de regressão com `requests.post` mockado —
  resposta HTTP 200 deve ser retornada na primeira tentativa; ramos DeepSeek
  (monitoramento pós-resposta e reset pós-timeout) cobertos.

**Verificação:** `pytest tests/test_ollama_adapter.py -v` (offline, sem Ollama).

## Fase H1 — Build, empacotamento e pinning de dependências

**Branch:** `hardening/phase-1/build-and-dependencies`

**Objetivo:** tornar `pip install -e ".[dev]"` funcional (pré-requisito da CI) e garantir
ambientes reprodutíveis em Python 3.10–3.12.

**Mudanças:**
- `pyproject.toml`: `build-backend = "setuptools.build_meta"`; descoberta de pacotes
  restrita a `src*`; entry point corrigido para `src.cli:run_cli`.
- Re-pinagem a partir de venv limpo Python 3.12 (`pandas==2.0.3` não possui wheels cp312 —
  atualizar para a série 2.2.x); `pyproject.toml` e `requirements.txt` alinhados com `==`;
  `requirements-lock.txt` gerado via `pip freeze` (dependências transitivas congeladas).
- `README.md`: seção de setup do ambiente com venv 3.12.

**Verificação:** instalação editável em venv limpo + `pytest --collect-only -q`.

## Fase H2 — Saneamento da suíte de testes

**Branch:** `hardening/phase-2/test-suite-sanitation`

**Objetivo:** fazer `pytest -m "not slow"` rodar verde e offline, aplicando os marcadores
declarados em `pyproject.toml` (hoje nunca usados) aos testes legados.

**Mudanças:**
- `pytest.mark.slow` nos testes que requerem Ollama/rede; `pytest.mark.integration` nos que
  dependem dos CSVs reais.
- Arquivos script-style sem asserts movidos para `scripts/deprecated/` (precedente da Fase 0).
- `tests/README.md` reescrito (hoje lista arquivos inexistentes e paths de máquina antiga).

**Verificação:** `pytest -m "not slow" -v` verde sem Ollama em execução.

## Fase H3 — Integração contínua (GitHub Actions)

**Branch:** `hardening/phase-3/continuous-integration` — depende de H1 e H2

**Objetivo:** validação automática em cada push/PR nas versões de Python suportadas.

**Mudanças:** `.github/workflows/ci.yml` com matriz Python 3.10/3.11/3.12, instalação via
`pip install -e ".[dev,json5,supabase]"` e execução de `pytest -m "not slow"`. Nenhum
secret é necessário: todos os testes da CI usam mocks.

**Verificação:** run verde na aba Actions.

## Fase H4 — Bateria de testes unitários faltantes

**Branch:** `hardening/phase-4/unit-test-coverage`

**Objetivo:** cobrir os cinco módulos sem nenhuma cobertura, criando a rede de segurança
para as fases H5/H6/H8.

**Arquivos novos:** `tests/test_settings.py`, `tests/test_persistence.py`,
`tests/test_cli.py`, `tests/test_command_handler.py`, `tests/test_supabase_client.py` —
todos com mocks/`tmp_path`, sem dependências externas reais.

**Verificação:** pytest dos cinco arquivos + suíte completa offline verde.

## Fase H5 — Reprodutibilidade: seed, UTC, hash do prompt, versão da ferramenta

**Branch:** `hardening/phase-5/reproducibility` — depende de H4

**Mudanças:**
1. **Seed fixo:** `llm_seed: int = 42` em `RefanSettings`; `use_random_seed` passa a
   default `False` e a ser efetivamente consumida — quando seed fixo está ativo, o payload
   do Ollama inclui `options.seed`. O valor entra no `config_snapshot` automaticamente.
2. **UTC:** novo `src/utils/timeutils.py` (`utc_now()`, `utc_now_iso()`); todos os pontos
   de persistência trocam `datetime.now()` naive por timestamps timezone-aware em UTC.
   Dados históricos não são reescritos (descontinuidade documentada na Fase H9).
3. **Hash do prompt:** SHA256 de `OPTIMIZED_LLM_PROMPT` calculado por sessão, gravado no
   snapshot e em cada registro JSONL, e validado contra `prompt_versions` no Supabase —
   divergência gera warning estruturado e campo `prompt_hash_mismatch`, nunca sobrescrita.
4. **Versão da ferramenta:** novo `src/utils/version_info.py` (`git describe --tags
   --always --dirty`, com cache e fallback `"unknown"`); `tool_version` injetado no
   snapshot de sessão e nos resultados.

**Verificação:** suíte offline + `python refan.py analyze --dry-run --limit 2` com inspeção
do JSONL gerado (`prompt_sha256`, `tool_version`, timestamps com offset UTC).

## Fase H6 — Robustez Supabase: retry, timeout, reconciliação, seed idempotente

**Branch:** `hardening/phase-6/supabase-robustness` — depende de H4

**Mudanças:**
1. Novos campos em `RefanSettings`: `supabase_timeout_s`, `supabase_max_retries`,
   `supabase_backoff_base_s`.
2. `SupabaseClient._execute_with_retry()` com backoff exponencial e logging estruturado;
   timeout explícito no client. O contrato externo é mantido (None/False na falha final —
   o fallback JSONL local continua válido), mas a falha torna-se visível e re-tentada.
3. `scripts/data/reconcile_supabase.py` (novo, somente leitura): compara os JSONL locais
   com `analysis_results` no cloud por `(sessão, commit_hash_current)`; reporta registros
   só-locais, só-cloud e divergências de classificação; exit code ≠ 0 em divergência.
4. `scripts/seed_supabase.py`: relatório de falhas parciais e exit code ≠ 0 quando houver;
   idempotência coberta por testes.

**Verificação:** testes unitários com mocks; execução manual da reconciliação com `.env` real.

## Fase H7 — Versionamento do baseline TCC via Git LFS

**Branch:** `hardening/phase-7/baseline-lfs` — independente

**Mudanças:**
- `scripts/data/generate_baseline_manifest.py` (novo): gera e verifica
  `baseline_tcc_2025/MANIFEST.sha256` (hash por arquivo, ordenado) — prova de integridade
  do snapshot independente do LFS.
- `.gitattributes`: rastreamento LFS para os artefatos do baseline (JSON/CSV/HTML/PNG/PDF
  e backups); arquivos Markdown/texto ficam fora do LFS para permanecerem diffáveis.
- `.gitignore`: remoção da entrada `baseline_tcc_2025/` e exceção para o PDF do baseline
  (a regra global `*.pdf` o ignoraria).
- Commits separados: configuração primeiro, dados depois (auditabilidade).

**Verificação:** `git lfs ls-files`, verificação do manifesto, clone fresco + `git lfs pull`.

## Fase H8 — Qualidade: centralização DeepSeek e eliminação de valores mágicos

**Branch:** `hardening/phase-8/code-quality` — depende de H4

**Mudanças:**
- `src/utils/llm_sizing.py`: substituir checagem inline `"deepseek" in model_name.lower()`
  por `settings.is_deepseek(model_name)` (fonte única de verdade).
- `src/handlers/llm_handler.py`: limiar `60000` hardcoded → `settings.max_diff_chars`.
- `src/analyzers/optimized_prompt.py`: `MAX_DIRECT_DIFF_SIZE` passa a ler de
  `settings.max_diff_chars_file` (elimina a dupla fonte do valor 100000).
- Novo `settings.deepseek_reset_interval` (default 8) substituindo o módulo hardcoded,
  com docstring justificando o valor (degradação de contexto observada empiricamente no
  DeepSeek-R1 após análises consecutivas).

**Verificação:** suíte offline + grep confirmando que os valores residem apenas em settings.

## Fase H9 — Documentação metodológica e proveniência de dados

**Branch:** `hardening/phase-9/documentation` — última fase

**Mudanças:**
1. `docs/PROMPTS.md`: versões de prompt (v1.0-tcc, v2.0-mestrado) com SHA256, racional do
   viés conservador ("Default: FLOSS") e sua limitação metodológica. **O prompt não é
   alterado** — qualquer mudança invalidaria a comparabilidade dos resultados.
2. `docs/REPRODUCIBILITY.md`: seed 42 vs baseline TCC sem seed (v2.1+ constitui nova série
   experimental); timestamps UTC vs históricos naive; `tool_version` e `prompt_sha256` nos
   snapshots; procedimento de reprodução de uma sessão; decisão de agregação do
   `purity_handler` (FALSE > TRUE: uma evidência de mudança funcional basta para o commit
   não ser pure — coerente com o critério conservador do prompt).
3. `csv/README.md` + reorganização: inputs oficiais imutáveis vs masters de trabalho vs
   derivados datados (movidos para `csv/derived/` via `git mv`, após verificação de que
   nenhum código os referencia). Nenhum dado bruto é modificado.
4. Docstring no método de resolução de conflitos do `purity_handler.py`.

**Verificação:** suíte offline + dry-run da análise (nenhum path quebrado).

---

## Verificação fim-a-fim (após o merge de H9)

```bash
/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,json5,supabase]"
python -m pytest -m "not slow" -v             # 100% verde, offline
python -m pytest -v                           # com Ollama ativo (inclui slow)
python refan.py analyze --dry-run --limit 5   # JSONL com prompt_sha256, tool_version, UTC
refan status --model mistral                  # entry point instalado
git lfs ls-files | wc -l
python scripts/data/generate_baseline_manifest.py --verify
python scripts/data/reconcile_supabase.py     # com .env configurado
# CI verde em 3.10/3.11/3.12 → tag v2.1.0 → merge --no-ff em development e main
```

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Cota LFS do GitHub (1 GB no plano gratuito) com 130 MB de baseline | Patterns LFS restritos ao baseline; `MANIFEST.sha256` garante integridade mesmo sem LFS; plano B documentado: depósito no Zenodo (DOI — adequado para a dissertação) |
| Seed fixo quebra comparabilidade direta com o baseline TCC | Baseline intocado; v2.1+ é tratada como nova série experimental; `use_random_seed` permanece configurável para replicar o regime antigo; seed registrado em todo `config_snapshot` |
| Atualização do pandas (2.0.3 → 2.2.x) muda comportamento de leitura de CSV | Testes de characterization (Fase 0) + suíte H4 executados antes e depois do bump na mesma branch |
| Mudança naive → UTC desloca timestamps em relação aos dados históricos | Apenas pontos de escrita são alterados; dados antigos não são reescritos; descontinuidade documentada em `docs/REPRODUCIBILITY.md` |
| Mover CSVs derivados quebrar script legado | Busca por referências a cada filename antes do `git mv`; suíte `integration` + dry-run como gate do merge |
| CI sem Ollama esconder regressões nos caminhos `slow` | Execução manual documentada de `pytest -m slow` antes de cada merge de fase que toque o `llm_handler` |
