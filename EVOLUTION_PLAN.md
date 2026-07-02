# Plano de Correção e Evolução — Refan série v2.2

> **Proveniência deste documento**: diagnóstico completo do repositório realizado em
> 2026-07-01 sobre o commit `c966cee` (branch `hardening/phase-9/documentation`).
> Método: leitura integral dos 26 módulos de `src/`, dos testes, scripts, CI, schema
> Supabase e documentos de planejamento, em quatro frentes de análise independentes
> (orquestração/CLI; handlers; analisadores/persistência/reprodutibilidade;
> testes/CI/higiene), com verificação empírica dos achados críticos (execução da suíte,
> verificação do manifesto do baseline, inspeção do estado git e confirmação manual de
> cada bug crítico no código-fonte). Todas as referências `arquivo:linha` valem para o
> commit `c966cee`; cada correção deve começar reproduzindo o defeito com um teste que
> falha (isso revalida o diagnóstico antes de alterar código).

## 1. Contexto

As séries anteriores deixaram o Refan estruturalmente organizado:

- **v2.0.0** (`REFACTORING_PLAN.md`, Fases 0–10): deduplicação, settings central,
  fusão dos handlers LLM, modelos canônicos, persistência JSONL, CLI.
- **Fase 11** (`ARCHITECTURE_PLAN.md`): persistência cloud Supabase + runner remoto.
- **v2.1 hardening** (`HARDENING_PLAN.md`, H0–H8 concluídas): correção do P0
  `is_deepseek`, build/CI, 193 testes offline, seed fixo, UTC, prompt hash,
  `tool_version`, retry Supabase, baseline em Git LFS. **H9 (documentação) pendente.**

O diagnóstico de julho/2026, porém, revelou uma camada de problemas que as séries
anteriores não alcançaram — e que atinge diretamente o que a ferramenta tem de mais
crítico como instrumento de pesquisa: **a validade dos dados que ela produz**. Em
resumo, há hoje:

1. **Emergência de integridade** — o snapshot imutável do TCC está violado na working
   tree (5 arquivos deletados, 67 intrusos; `MANIFEST.sha256 --verify` FALHA) e a causa
   raiz (iCloud sincronizando `~/Documents`) continua ativa; 107 commits de hardening
   não estão em `main` nem no remoto.
2. **Bugs que corrompem dados de pesquisa** — métrica de convergência sempre zero;
   classificações fabricadas por heurística de palavras-chave gravadas como se fossem
   do LLM; `confidence_level`/`technical_evidence` constantes artificiais; proveniência
   de prompt sobrescrevível; sync cloud que apaga o baseline Purity.
3. **Furos de reprodutibilidade** — digest do modelo Ollama nunca capturado (tags são
   mutáveis), `num_ctx` efetivo e prompt real enviados não são registrados, tempo de
   processamento sempre 0.
4. **Dívidas de robustez e arquitetura** — persistência não-atômica, dois motores de
   análise paralelos, comandos remotos inertes que reportam sucesso, entry point
   instalado quebrado.
5. **Lacunas de qualidade** — 11 de 26 módulos sem nenhum teste (incluindo o
   orquestrador central), zero lint/type-check, CI sem gates.

Este plano organiza a resposta em **nove fases (E0–E8)**, priorizadas por risco ao
trabalho acadêmico. A série usa numeração própria (`evolution/phase-N`, tags
`v2.2.0-evolution-N`, versão alvo **v2.2.0**).

## 2. Diagnóstico consolidado

### 2.1 Tabela mestre de achados

Severidade: **P0** = ameaça imediata a dados/trabalho; **ALTA** = corrompe resultados ou
bloqueia uso; **MÉDIA** = fragilidade real com gatilho plausível; **BAIXA** = dívida.

#### INT — Integridade do repositório e dos dados

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| INT-1 | P0 | Baseline imutável violado na working tree: 5 arquivos deletados em `baseline_tcc_2025/output_models/deepseek-r1_8b/analises/` + 67 arquivos intrusos `" 2"`; `generate_baseline_manifest.py --verify` retorna ERRO (exit 1) | `git status` + execução do verify |
| INT-2 | P0 | Causa raiz ativa: repo dentro de `~/Documents` sincronizado pelo iCloud → 95 arquivos duplicados `" 2"` (byte-idênticos, confirmado por `diff`) espalhados até em `src/utils/` (`timeutils 2.py`, `version_info 2.py`) e `tests/` (8 cópias, 1 delas **obsoleta**: `test_supabase_client 2.py` testa contrato pré-H6 e adiciona 9,3s de backoff real à suíte) | `find`, `diff`, `pytest --durations` |
| INT-3 | P0 | 107 commits (todo o hardening v2.1 + Fase 11) **não mergeados em `main`** e branches de hardening **sem remoto** — um disco perdido = trabalho perdido | `git log main..HEAD` = 107; `git branch -a` |
| INT-4 | MÉDIA | `.gitignore` sem proteção contra os artefatos `" 2*"` do iCloud (um `git add -A` os commitaria); ignora `ARCHITECTURE_PLAN.md` e `REFACTORING_PLAN.md` (planos citados por commits ficam fora do versionamento — fura a rastreabilidade) | `.gitignore` |
| INT-5 | BAIXA | Clutter: worktree `.claude/worktrees/charming-burnell-ec604b` (152 MB, branch sem commits únicos), `hardening/v2.1-integration` e `phase-9` apontando para o mesmo commit, arquivos soltos na raiz (`new_model.modelfile`, `extract_purity_none_analysis.py`, `complete_unified_analysis_filtered_2025-09-01_11-59-17.csv`), diretório `.github/workflows 2/` vazio | `git worktree list`, `git ls-files` |

#### VAL — Validade dos dados de pesquisa (bugs confirmados no código)

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| VAL-1 | ALTA | Métrica de convergência LLM×Purity **sempre 0 agree / N disagree**: compara `llm_class == 'TRUE'/'FALSE'` quando `llm_class ∈ {PURE, FLOSS}` — o mapeamento correto (TRUE↔PURE, FALSE↔FLOSS) existe apenas na view SQL | `src/analyzers/llm_purity_analyzer.py:409-410` vs `supabase/migrations/001_initial_schema.sql:191-192` |
| VAL-2 | ALTA | Falha de parse **fabrica classificação** por contagem de palavras-chave (`_extract_analysis_from_raw_text`) e a grava sem `extraction_method` e sem log de falha — o bloco `if not json_result` + `save_json_failure` fica inalcançável porque a heurística sempre retorna dict preenchido (default `floss`) | `src/handlers/llm_handler.py:524-562, 596-669` |
| VAL-3 | ALTA | No caminho de extração **dominante** (`FINAL:`), o dict retornado não contém `confidence_level` nem `technical_evidence` → adapters preenchem `"medium"` e `""` — duas variáveis de pesquisa persistidas são **constantes artificiais**; `justification` recebe a resposta bruta inteira | `src/handlers/llm_handler.py:501-516` + `src/models/adapters.py:61-64` |
| VAL-4 | ALTA | Proveniência de prompt violável: `get_or_create_prompt_version` faz `upsert` com `system_prompt`/`sha256_hash` no payload → reutilizar a tag após editar o prompt **sobrescreve** o registro histórico; o analisador detecta o mismatch, avisa ("nunca sobrescrever") e **chama o upsert mesmo assim** | `src/persistence/supabase_client.py:211-219`; `src/analyzers/llm_purity_analyzer.py:504-521` |
| VAL-5 | ALTA | `sync_local_jsonl` chama `upsert_commit` sem `purity_analysis` → payload inclui `"purity_analysis": None` e **zera o baseline Purity** de commits já existentes no cloud (variável independente da pesquisa apagada na reconexão offline→online) | `src/persistence/supabase_client.py:509-514` + `:118-127` |
| VAL-6 | ALTA | `FAILED`/`ERROR` em limbo: nunca são reanalisados (filtro de pendentes só re-inclui `NaN/''/'None'`), não aparecem em `completed` nem `pending` do status, não geram linha no cloud; `record_failure` **nunca é chamado** (zero registro de falhas no Supabase) | `src/analyzers/llm_purity_analyzer.py:465-469, 623-632, 713-722`; `src/persistence/supabase_client.py:347` |
| VAL-7 | ALTA | Truncamento silencioso de contexto: `num_predict=50000` ≫ `num_ctx` (4096–8192); diff de até 60 000 chars (~15k tokens) não cabe em 8192 tokens → Ollama corta o prompt e o modelo classifica **sem ver o diff inteiro**, sem qualquer registro disso | `src/handlers/llm_handler.py:227-229`; `src/core/settings.py:46,65-67`; `src/utils/llm_sizing.py:47-61` |
| VAL-8 | MÉDIA | Parser JSON com estratégias de recall alto/precisão baixa: fallback `key: value` livre pode devolver dict sem `refactoring_type` → vira FLOSS silencioso via default; estratégia de arrays pode retornar `list` (comportamento indefinido a jusante); `_strip_think_blocks` é transformação destrutiva pré-parse; disponibilidade opcional do `json5` cria comportamento dependente de ambiente | `src/utils/json_parser.py:139-147, 107-114, 186-198, 8-11` |
| VAL-9 | MÉDIA | Duas definições incompatíveis de "agreement" no `purity_handler` (uma exige ambos floss, outra igualdade de classes) — estatísticas divergem conforme o caminho de código | `src/handlers/purity_handler.py:299` vs `:595-597` |
| VAL-10 | MÉDIA | Prompt real contradiz a si mesmo ("Start with your brief analysis" vs "DO NOT explain. Return JSON ONLY") e tem um único exemplo few-shot (PURE, nenhum FLOSS) — aumenta variância entre modelos; viés "default FLOSS" aplicado em múltiplas camadas independentes (prompt, parser, adapters, analisador) sem registro de qual camada decidiu | `src/analyzers/optimized_prompt.py:115, 158, 161, 120-135`; `src/models/adapters.py:61`; `src/analyzers/llm_purity_analyzer.py:322-339` |

#### REP — Reprodutibilidade e rastreabilidade

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| REP-1 | ALTA | **Digest do modelo Ollama nunca é capturado** — só nome/tag, e tags são mutáveis (`ollama pull mistral` em datas diferentes = pesos diferentes). Irreprodutibilidade indetectável a posteriori. Nenhuma chamada a `/api/show` ou `/api/tags` no repositório | grep global; `src/core/settings.py:39-41` |
| REP-2 | MÉDIA | Por análise, não são registrados: `num_ctx` efetivo calculado, seed efetivo no regime aleatório, hash/tamanho do prompt **realmente enviado** (o hash cobre só o template; o diff embutido e a redução aplicada não são auditáveis no caminho de sucesso) | `src/utils/llm_sizing.py:27-61`; `src/analyzers/llm_purity_analyzer.py:113`; `src/handlers/llm_handler.py:237-238` |
| REP-3 | MÉDIA | Hardware fora do snapshot: `REFAN_NUM_GPU_LAYERS` vive em `config.py:142-157` (fora de `RefanSettings` → fora do `config_snapshot`); colunas `gpu_utilization_pct`/`memory_used_mb` de `runner_status` nunca são preenchidas | `src/core/config.py:142-157`; `src/persistence/supabase_client.py:382-419` |
| REP-4 | MÉDIA | `processing_time_ms` sempre 0 (nunca atribuído) → `AVG(processing_time_ms)` da materialized view não significa nada | `src/models/commit.py:60` |
| REP-5 | ALTA | `configs/PROMPT_OTIMIZADO_ATUAL.txt` é **órfão** (nenhum código o lê) e **divergente** do prompt real (`OPTIMIZED_LLM_PROMPT`): formato de saída diferente (3 campos vs 8 + `FINAL:`), instrução sobre commit message oposta. Um arquivo chamado "ATUAAL" que não é o atual é armadilha de citação em contexto acadêmico | `configs/PROMPT_OTIMIZADO_ATUAL.txt` vs `src/analyzers/optimized_prompt.py:20-164` |
| REP-6 | BAIXA | `data_handler.get_random_commit` usa `random` sem seed — em tensão com o regime determinístico | `src/handlers/data_handler.py:188-191` |

#### ROB — Robustez de persistência e operação

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| ROB-1 | ALTA | CSV master só é escrito **ao final da sessão** (loop atualiza `df` em memória); mensagem `"💾 Progress saved"` a cada iteração é **falsa**; SIGKILL/queda de energia perde todas as atualizações de CSV (JSONL sobrevive). Escrita final não-atômica (`to_csv` in-place, sem temp+rename), sem lock (multi-runner = last-writer-wins) | `src/analyzers/llm_purity_analyzer.py:573-641, 627, 201-207`; `src/utils/persistence.py:125-142` |
| ROB-2 | ALTA | `save_analyzed_commits`: read-modify-write não-atômico e sem lock em `analyzed_commits.json`; crash no meio do `json.dump` corrompe o arquivo e `_load_analyzed_commits` volta `set()` **silenciosamente** (histórico de análise "esquecido") | `src/handlers/data_handler.py:33-47, 49-81` |
| ROB-3 | MÉDIA | JSONL: linha truncada por crash é descartada sem aviso no merge/leitura (`except JSONDecodeError: continue`); sem `fsync` (queda de energia perde cauda do buffer) | `src/utils/persistence.py:56-60, 71-75, 117-120` |
| ROB-4 | MÉDIA | Git: clone **completo** de cada repositório, sem `--filter`/shallow; `git fetch --all` a cada execução mesmo com commits já locais; **nenhuma** limpeza (`repositorios/` cresce sem limite); colisão de basename (`a/log4j` e `b/log4j` → mesmo diretório → diff do repo errado); clone parcial/falho não é detectado nem removido; sem separador `--` nos comandos (argument injection); `commit_exists` engole exceções (erro transitório ≡ commit ausente → pulado silenciosamente) | `src/handlers/git_handler.py:26-31, 44-51, 56-62, 79, 86-88, 98, 135` |
| ROB-5 | ALTA | Runner remoto: `change_model` e `reanalyze_commit` são **aceitos, marcados como "Executed" no Supabase e não fazem nada** (fila/flag nunca consumidas); `pause` sem `resume` bloqueia para sempre (sem timeout); payloads (`commit_hash`, `model_name`) sem validação; comando que lança exceção fica preso em `acknowledged` para sempre (perdido silenciosamente) | `src/runner/command_handler.py:65-72, 79-80, 101-110, 114-122, 128-132` |
| ROB-6 | MÉDIA | Cloud: materialized view `model_metrics` **nunca é refreshed** (nenhum `REFRESH` no código → métricas estagnadas); RLS habilitado em só 4 de 9 tabelas (`commits`, `llm_models`, `prompt_versions`, `analysis_failures`, `purity_checker_results` expostas ao role `anon` conforme grants default) | `supabase/migrations/001_initial_schema.sql:182, 205-217` |
| ROB-7 | BAIXA | Log de falhas: caminho relativo ao CWD (`json_failures.json` se dispersa pelo filesystem), arquivo `.json` que contém JSONL, campo `llm_response_excerpt` grava a resposta **inteira**, exceções do próprio logger engolidas | `src/core/settings.py:84`; `src/handlers/llm_handler.py:320-321`; `src/utils/failure_logger.py:52-53, 66-71` |

#### ARQ — Arquitetura e interface

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| ARQ-1 | ALTA | **Dois motores de análise paralelos e incompatíveis**: Motor A (`main.py`, 3 loops quase idênticos de ~100 linhas cada — `process_commits`, `process_commits_optimized`, `process_specific_commits_optimized` — rastreando por `analyzed_commits.json`) e Motor B (`LLMPurityAnalyzer`, rastreando por coluna `llm_analysis` do CSV). Um não enxerga o trabalho do outro | `src/core/main.py:131-500` vs `src/analyzers/llm_purity_analyzer.py` |
| ARQ-2 | ALTA | Duas fontes de verdade para configuração: globais mutáveis de `config.py` (`_CURRENT_LLM_MODEL`, `MODEL_PATHS`, `LLM_HOST`...) vs singleton `settings` — `set_llm_model()` **não atualiza** `settings.llm_model` (estado divergente após troca de modelo); host Ollama duplicado (`config.py:28` e `settings.py:38`) | `src/core/config.py:28, 39-56` vs `src/core/settings.py:38-41` |
| ARQ-3 | ALTA | Entry point instalado **quebrado**: `refan --help` → `ModuleNotFoundError: No module named 'src'` (anti-padrão de empacotar `src` como pacote top-level; funciona só via `python refan.py` a partir da raiz) | `pyproject.toml:52-53`; teste empírico |
| ARQ-4 | MÉDIA | Menus com bugs: `NameError: pd` na opção 4 do menu LLM quando importado (import de pandas está dentro do `__main__`); opção 6 chama `scripts/demos/demo_llm_visualization.py` (não existe) e falha silenciosamente; `int()` sem try na opção 3 derruba a aplicação; `backup_file` possivelmente indefinido; menu diz "1-11" com 12 opções | `src/core/menu_analysis.py:238 vs 460, 284, 300-301, 61 vs 185`; `src/core/main.py:897, 1040` |
| ARQ-5 | MÉDIA | `signal_handler` imprime "Estado preservado com sucesso" **sem persistir nada** (resultados locais dos loops são inacessíveis ao handler) — Ctrl+C no Motor A perde o lote com mensagem tranquilizadora; a função que faria isso certo (`safe_processing_loop`) existe e está **morta** | `src/core/main.py:44-53, 80-119` |
| ARQ-6 | MÉDIA | CLI: `--skip-analyzed` é inerte (`store_true` + `default=True` — impossível desligar por ela; o controle real é `--no-skip`); paths de CSV relativos ao CWD espalhados (quebram fora da raiz) | `src/cli.py:52-57, 131, 194`; `src/core/menu_analysis.py:43, 355, 418`; `src/analyzers/llm_purity_analyzer.py:105`; `src/handlers/llm_handler.py:69` |
| ARQ-7 | MÉDIA | Seleção de modelo reimplementada 3×; opções 8 e 9 do menu LLM ~95% idênticas; dispatch de interface duplicado entre `refan.py` e `cli.py` | `refan.py:33-57`; `src/core/main.py:1007-1033`; `src/core/menu_analysis.py:303-326, 328-455` |
| ARQ-8 | MÉDIA | Deriva de nomes de campos entre camadas: `commit1/commit2` vs `commit_hash_before/current`, `project` vs `project_name` vs `repository`, `PURE/FLOSS` vs `pure/floss`, `diff_source` vs `processing_method`, rename `diff_size_chars`→`diff_size` reacoplado por string | `src/handlers/llm_handler.py:571-579`; `src/models/adapters.py:86`; `src/handlers/llm_visualization_handler.py:55-56` |

#### QUA — Qualidade de engenharia

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| QUA-1 | ALTA | Zero lint, zero formatação automática, zero type-check (sem ruff/black/mypy em deps ou config); CI roda apenas pytest (sem cobertura, sem gates, sem verificação de manifesto) | `pyproject.toml`; `.github/workflows/ci.yml` |
| QUA-2 | ALTA | 11 de 26 módulos de `src/` **sem nenhum teste**, incluindo os dois de maior valor científico: `llm_purity_analyzer.py` (orquestrador central) e `purity_handler.py` (baseline). Demais: `main.py`, `menu_analysis.py`, os 2 visualization handlers, `adapters.py`, `colors.py`, `failure_logger.py`, `llm_sizing.py`, `logging_config.py` | inventário cruzado tests×src |
| QUA-3 | MÉDIA | Marcadores `slow`/`integration` declarados no `pyproject.toml` e documentados, mas **0 usos** — `pytest -m "not slow"` ≡ suíte completa (a CI não testa o que acredita testar) | grep `pytest.mark` |
| QUA-4 | MÉDIA | Código morto extenso (inventário no Apêndice A): reparo de JSON duplicado e inerte no `llm_handler`, `safe_processing_loop`, `llm_visualization_handler` órfão do app (1042 linhas), subsistema file-based diff inalcançável, imports mortos, `reduce_diff` O(n²) com branch inalcançável | Apêndice A |
| QUA-5 | MÉDIA | Observabilidade: nenhum handler usa `logging` (tudo `print` colorido com emoji — não silenciável, sem níveis, inutilizável em runner headless); `except Exception` genérico imprimindo em stdout sem traceback em ≥10 pontos; idioma PT/EN misturado na mesma operação (`command_handler`: log PT, `result_message` no banco EN) | `src/handlers/*`, `src/core/main.py:749, 862`; `src/runner/command_handler.py:70-92` |
| QUA-6 | BAIXA | `filter_data` documenta "cinco primeiros commits por projeto" mas executa `.tail(12)`; docstrings de `llm_handler` prometem reparo de JSON que não é usado | `src/handlers/data_handler.py:104, 116` |

#### DOC — Documentação

| ID | Sev | Achado | Evidência |
|----|-----|--------|-----------|
| DOC-1 | ALTA | `README.md` mistura seções atuais (setup, LFS) com conteúdo obsoleto: CLI descrita como "em desenvolvimento" (existe e é testada), árvore cita `scripts/demos/`, `optimized_llm_handler.py` (não existem), `ollama` listado como dependência pip, não documenta o comando `refan` nem os subcomandos | `README.md:23-24, 30-36, 107, 178-187` |
| DOC-2 | MÉDIA | `tests/README.md` lista 7 arquivos (~91 testes) e omite os 8 mais novos (193 testes reais) | `tests/README.md` |
| DOC-3 | MÉDIA | Fase H9 inteira pendente: não existem `docs/PROMPTS.md`, `docs/REPRODUCIBILITY.md`, `csv/README.md` (o diretório `docs/` está vazio); decisão FALSE>TRUE do purity_handler sem docstring | `HARDENING_PLAN.md:218-236` |
| DOC-4 | BAIXA | `.env.example` ok, mas `settings.prompt_version_tag` default `"v2.0-mestrado"` convive com narrativa "v2.1+" nos comentários — tags de série desalinhadas | `src/core/settings.py:78-79, 97` |

### 2.2 O que está sólido (não retrabalhar)

Para calibrar o esforço: a fundação das séries anteriores é boa e deve ser preservada.

- `RefanSettings` tipada e documentada, com service key excluída do snapshot
  (`settings.py:130-138`).
- Cadeia UTC (`timeutils.py`), `tool_version` via `git describe --dirty`,
  `prompt_sha256` por registro (`llm_purity_analyzer.py:576-577`).
- Resiliência Supabase: timeout explícito, retry com backoff exponencial, tentativa
  única deliberada para operações periódicas (`supabase_client.py:61-97`).
- `SessionWriter` JSONL incremental como fonte durável real (sobrevive a Ctrl+C).
- Suíte de testes existente de **alta qualidade** (docstrings citando fase e defeito,
  mocks apropriados, zero rede): 193 testes, 0,27s.
- CI com matriz 3.10/3.11/3.12 funcionando; deps pinadas com `==` + lock transitivo.
- `seed_supabase.py` e `reconcile_supabase.py` bem escritos (idempotência, exit codes).
- Schema SQL versionado em `supabase/migrations/001_initial_schema.sql` com CHECKs e
  UNIQUE corretos.

## 3. Princípios de execução

1. **Dados históricos são intocáveis.** Nenhuma correção reescreve JSONL/CSV/cloud já
   produzidos. Onde um bug afetou dados passados, a resposta é: (a) quantificar o
   impacto com script de auditoria read-only; (b) documentar a descontinuidade em
   `docs/REPRODUCIBILITY.md`; (c) quando possível, **recomputar métricas derivadas** a
   partir dos dados brutos preservados (ex.: VAL-1 é recomputável — as classificações
   por commit estão corretas; só o agregado estava errado).
2. **Toda correção nasce de um teste que falha.** Reproduz o defeito, corrige, o teste
   vira regressão permanente. Isso também revalida o diagnóstico deste plano.
3. **Mudanças que alteram a condição experimental** (prompt, parâmetros de geração,
   formato de saída) são **novas séries experimentais**, nunca substituições silenciosas:
   ganham tag de prompt/config própria, registro em `prompt_versions` e documentação da
   diferença. O prompt v2.0-mestrado **não é alterado** durante E2–E6.
4. **Commits atômicos em Conventional Commits**, corpo explicando o porquê, fases
   mergeadas com `--no-ff`, suíte offline verde em cada merge (mesma disciplina das
   séries anteriores).
5. **Nada de auto-atribuição de IA** em commits/PRs (política do `CLAUDE.md`).

## 4. Estratégia de branches

```
main ←── development ←── hardening/v2.1-integration ←── hardening/phase-9/documentation   (fechamento v2.1)
main ←── development ←── evolution/v2.2-integration
                            ├── evolution/phase-2/research-validity
                            ├── evolution/phase-3/full-reproducibility
                            ├── evolution/phase-4/persistence-robustness
                            ├── evolution/phase-5/single-engine
                            ├── evolution/phase-6/quality-gates
                            ├── evolution/phase-7/statistical-instrumentation
                            └── evolution/phase-8/documentation-release
```

E0 (emergência) e E1 (fechamento v2.1) acontecem **antes** da criação da série v2.2.
Tags: `v2.1.0` ao final de E1; `v2.2.0-evolution-N` por fase; `v2.2.0` ao final.

---

## 5. Fase E0 — Emergência: integridade e backup (executar HOJE, sem código)

**Objetivo:** parar a hemorragia. Nenhuma linha de código de produto muda nesta fase.

**Justificativa:** INT-1/2/3 ameaçam o ativo mais valioso do projeto (baseline + 107
commits de trabalho). Cada dia com o repo dentro do iCloud é um dia de roleta.

**Ações (ordem exata):**

1. **Backup imediato do estado atual antes de qualquer limpeza**:
   `git push origin hardening/v2.1-integration hardening/phase-9/documentation development`
   (os 107 commits passam a existir fora da máquina). Publicar também as tags:
   `git push origin --tags`.
2. **Restaurar os 5 arquivos deletados do baseline** (estão no LFS):
   `git restore -- baseline_tcc_2025/` e conferir com `git status`.
3. **Remover os 95 intrusos `" 2"`** (são cópias byte-idênticas confirmadas; a única
   exceção — `tests/test_supabase_client 2.py`, versão obsoleta — também é lixo):
   `find . -name "* 2*" -not -path "./.git/*" -not -path "./.venv/*" -not -path "./.claude/*" -delete`
   seguido de conferência manual do `git status` (nenhum arquivo rastreado pode sumir).
4. **Reverificar integridade**: `python scripts/data/generate_baseline_manifest.py --verify`
   deve retornar OK (0 faltando, 0 não listados, 0 divergentes) e
   `python -m pytest tests/ -q` deve reportar exatamente **193 passed** em <1s.
5. **Eliminar a causa raiz**: mover o repositório para fora do escopo do iCloud
   (ex.: `~/dev/refan` ou desativar "Desktop & Documents" no iCloud Drive). Registrar a
   decisão no README (seção ambiente). Enquanto a mudança não ocorrer, tratar todo
   `git status` sujo como suspeito. *Nota: mover o diretório invalida o venv
   (`.venv` tem paths absolutos) — recriar com `pip install -e ".[dev,json5,supabase]"`.*
6. **Blindar o repo contra recorrência**:
   - `.gitignore`: adicionar padrões `* 2`, `* 2.*`, `"* 2/"` (artefatos de conflito
     do iCloud/Finder).
   - Novo passo na CI (e script local `scripts/data/check_repo_hygiene.py`): falhar se
     `find` detectar arquivos `" 2"` rastreáveis ou se o manifesto do baseline divergir
     em arquivos **rastreados** (a verificação completa do manifesto requer LFS pull —
     documentar).
7. **Limpar clutter git**: `git worktree remove .claude/worktrees/charming-burnell-ec604b`
   e `git branch -D claude/charming-burnell-ec604b` (sem commits únicos — verificado);
   remover o diretório vazio `".github/workflows 2"`.
8. **Decidir destino dos arquivos soltos da raiz** (rastreados):
   `extract_purity_none_analysis.py` → `scripts/research/`; `new_model.modelfile` →
   `configs/` ou remoção; `complete_unified_analysis_filtered_*.csv` → `csv/derived/`
   (antecipa parte do H9). Fazer via `git mv` para preservar história.

**Verificação:** manifesto verde; 193 testes; `git status` limpo; branches no remoto;
repo fora do iCloud.

**Impacto metodológico:** nenhum — só restauração de estado. Registrar o incidente
(datas, arquivos afetados, causa) em `docs/REPRODUCIBILITY.md` (E8) como evidência de
que o baseline foi verificado e restaurado por manifesto.

## 6. Fase E1 — Fechamento da série v2.1 (H9 + merges + tag)

**Branch:** `hardening/phase-9/documentation` (já existe, vazia)

**Objetivo:** executar a Fase H9 exatamente como especificada no `HARDENING_PLAN.md`
(que já está aprovado e é parte do registro metodológico) e fechar a série v2.1 com
merge e tag, antes de abrir a v2.2.

**Mudanças (do plano H9, com dois acréscimos):**

1. `docs/PROMPTS.md` — versões de prompt com SHA256, racional do viés conservador
   "default FLOSS" e sua limitação metodológica.
2. `docs/REPRODUCIBILITY.md` — seed 42 vs TCC sem seed; UTC vs timestamps naive
   históricos; procedimento de reprodução de sessão; decisão FALSE>TRUE do
   `purity_handler` (com docstring no método).
3. `csv/README.md` + reorganização (inputs imutáveis vs masters vs derivados datados →
   `csv/derived/` via `git mv`, após grep de referências).
4. **Acréscimo 1 — resolver REP-5 já aqui** (é documentação): substituir
   `configs/PROMPT_OTIMIZADO_ATUAL.txt` por `configs/prompts/v1.0-tcc.txt` e
   `configs/prompts/v2.0-mestrado.txt` contendo os textos **reais** (o segundo extraído
   verbatim de `OPTIMIZED_LLM_PROMPT`), cada um com SHA256 registrado em
   `docs/PROMPTS.md`. O código passa a ser validado contra o arquivo por um teste
   (`sha256(arquivo) == sha256(constante)`) — a migração do código para *carregar* do
   arquivo fica para E3 (evita mudança de comportamento numa fase de docs).
5. **Acréscimo 2 — versionar os planos**: remover `ARCHITECTURE_PLAN.md` e
   `REFACTORING_PLAN.md` do `.gitignore` e commitá-los (com nota de que refletem o
   estado de planejamento nas datas respectivas). Commits do histórico os citam;
   deixá-los fora do versionamento fura a auditabilidade que eles mesmos pregam.
6. `README.md` — corrigir apenas o factualmente errado (DOC-1): CLI existente, árvore
   real, remoção da seção de migração v1. Reescrita completa fica para E8.

**Fechamento da série:** merge `--no-ff` em `hardening/v2.1-integration` → merge em
`development` → merge em `main` → tag `v2.1.0` → push de tudo. A partir daqui `main`
volta a ser o retrato fiel do estado da ferramenta.

**Verificação:** a lista de verificação fim-a-fim do `HARDENING_PLAN.md` (seção final),
exceto o item do entry point `refan` (quebrado — ARQ-3, corrigido em E5; documentar a
exceção no PR de merge).

## 7. Fase E2 — Validade dos dados de pesquisa

**Branch:** `evolution/phase-2/research-validity`

**Objetivo:** eliminar os defeitos que fazem a ferramenta gravar dados falsos ou
destruir dados verdadeiros. É a fase de maior valor acadêmico do plano: enquanto ela
não estiver concluída, **nenhum resultado novo deve ser usado na dissertação**.

**Mudanças (cada item = 1+ commit com teste de regressão):**

1. **VAL-1 — Corrigir a métrica de convergência.**
   `llm_purity_analyzer.py:409-410`: mapear explicitamente
   `{'TRUE': 'PURE', 'FALSE': 'FLOSS'}` antes de comparar; `NONE`/ausente vira categoria
   própria `not_comparable` (não entra em agree nem disagree). Extrair para função pura
   `compare_purity_llm(purity: str, llm: str) -> Literal["agree","disagree","not_comparable"]`
   em `src/utils/classification.py` (única fonte de verdade, espelhando a view SQL) e
   testar as 9 combinações. *Auditoria retroativa:* script read-only
   `scripts/research/recompute_convergence.py` que recalcula a convergência de todos os
   JSONs de sessão existentes a partir dos registros por-commit (que estão corretos) e
   emite tabela antes/depois — os JSONs históricos não são editados.

2. **VAL-2 — Fim da classificação fabricada.**
   `llm_handler.py:524-562`: a heurística de palavras-chave deixa de produzir resultado
   "normal". Novo comportamento: se `FINAL:` ausente **e** JSON ausente → resultado
   `FAILED` com `error_type="unparseable_response"`, resposta bruta preservada,
   `save_json_failure` **sempre** chamado (hoje inalcançável) e falha registrada no
   cloud (item 6). Se a heurística for mantida como *sinal* (opcional), o resultado
   deve carregar `extraction_method="keyword_heuristic"` e ser **excluído por default**
   das métricas (filtro por extraction_method nos relatórios). Decisão recomendada:
   remover a heurística — em instrumento de medição, "não sei" é um resultado válido;
   um chute rotulado não é.
   *Auditoria retroativa:* como `extraction_method` não foi persistido no JSONL
   (VAL-3/adapters) mas `llm_raw_response` foi, criar
   `scripts/research/audit_extraction_methods.py`: re-executa o pipeline de extração
   (offline, sem LLM) sobre cada `llm_raw_response` armazenado e classifica cada
   registro histórico em `final_pattern` / `json` / `keyword_heuristic` /
   `unparseable`. Relatório por modelo/sessão quantifica quantos rótulos históricos são
   heurísticos → tabela para o capítulo de ameaças à validade.

3. **VAL-3 — Capturar `confidence_level` e `technical_evidence` reais.**
   No caminho `FINAL:` (`llm_handler.py:501-516`): após extrair a classificação, ainda
   tentar `extract_json_from_text` para recuperar os demais campos; usar a classificação
   do `FINAL:` como autoridade, mas preencher confidence/evidence/justification do JSON
   quando presente. Quando ausentes, gravar `None`/vazio explícito (**nunca** um default
   que simula resposta) — mudar defaults em `adapters.py:63-64` de `"medium"`/`""` para
   `None`, e propagar `extraction_method` no `analysis_to_session_dict`
   (`adapters.py:76-94`) e no `record_result` (`llm_purity_analyzer.py:595-607`).
   `justification` deixa de receber a resposta bruta inteira (a resposta já vai em
   `llm_raw_response`).
   *Nota metodológica:* documentar que `confidence_level` das sessões anteriores é
   constante artificial e não pode ser usado como variável.

4. **VAL-4 — Proveniência de prompt imutável.**
   `supabase_client.py:211-219`: substituir upsert por **get-then-insert**: se a tag
   existe com o mesmo `sha256_hash`, retorna id; se existe com hash diferente, **erro
   fatal** instruindo a criar nova tag (`REFAN_PROMPT_VERSION`); nunca UPDATE.
   Remover a chamada pós-warning em `llm_purity_analyzer.py:519-521` (o warning passa a
   abortar a sessão). Complemento no banco: trigger `BEFORE UPDATE` em
   `prompt_versions` que rejeita alteração de `system_prompt`/`sha256_hash` (migration
   `002_prompt_immutability.sql`) — defesa em profundidade.

5. **VAL-5 — Sync não destrói o baseline Purity.**
   `supabase_client.py:118-127`: `upsert_commit` monta o payload **omitindo** chaves com
   valor `None` (ou upsert com `ignoreDuplicates`/`defaultToNull=false` conforme
   suporte do postgrest-py); teste com mock verificando que `purity_analysis` não
   aparece no payload quando não fornecido. Adicionar ao `reconcile_supabase.py` uma
   checagem específica: commits no cloud com `purity_analysis IS NULL` que têm valor no
   CSV local (detecção de dano já causado + relatório para correção pontual via seed).

6. **VAL-6 — Falhas são dados.**
   (a) `record_failure` passa a ser chamado em todo `FAILED`/`ERROR`
   (`llm_purity_analyzer.py:623-632`) com `error_type` tipado
   (`json_parse`/`timeout`/`ollama_error`/`git_error`/`unparseable_response`);
   (b) `refan analyze --retry-failed`: novo filtro que re-inclui `FAILED`/`ERROR`
   (`:465-469`); (c) `get_analysis_summary` ganha contagem explícita `failed`
   (`:713-722`) e o `refan status` a exibe.

7. **VAL-7 — Fim do truncamento silencioso.**
   Regra única em `llm_sizing.py`: `num_ctx` dimensionado pela estimativa de tokens do
   prompt **real** (com margem para saída), respeitando teto por modelo/VRAM
   configurável (`settings.context_max_by_model`); `num_predict` limitado ao espaço
   restante (não os 50 000 atuais); se o prompt estimado exceder o teto → reduzir o
   diff **antes** (já existe `reduce_diff`) e **registrar** `diff_truncated=True` +
   `original_diff_size` no resultado. Testes com tamanhos sintéticos cobrindo os três
   regimes (cabe / reduz / impossível).

8. **VAL-8 — Parser com precisão sobre recall.**
   `json_parser.py`: (a) remover a estratégia 3 `simple_kv` (`:139-147`) — recall às
   custas de rótulos lixo; (b) estratégia de arrays retorna dict ou nada (nunca list)
   (`:107-114`); (c) resultado do parser passa por validação de schema mínimo
   (`refactoring_type ∈ {pure,floss}` obrigatório) antes de ser aceito — objetos sem o
   campo são falha de parse, não FLOSS default; (d) `json5` vira dependência
   **obrigatória** do grupo runtime (elimina comportamento dependente de ambiente);
   (e) registrar sempre qual estratégia extraiu (`extraction_method` granular:
   `direct_json`/`fenced_json`/`balanced_scan`/`json5`).
   Junto: eliminar o default `"floss"` em `adapters.py:61` (ausência de
   `refactoring_type` = falha explícita, consistente com VAL-2) e a duplicata de
   fallback conservador em `llm_purity_analyzer.py:322-339`. O viés conservador
   documentado ("uncertain → FLOSS") passa a existir **apenas no prompt** — decisão do
   modelo, registrada; nunca decisão do parser.

9. **VAL-9 — Uma única definição de agreement no `purity_handler`.**
   Unificar `:299` e `:595-597` na função de `classification.py` do item 1; teste
   garantindo que ambos os caminhos produzem estatísticas idênticas para o mesmo input.

**Verificação da fase:** suíte offline verde; dry-run + sessão real curta (5 commits,
mistral) inspecionando JSONL: nenhum registro com confidence fabricada, falhas com
`error_type`, `extraction_method` presente; scripts de auditoria retroativa executados
e relatórios salvos em `output/audits/` (fora do baseline!).

**Impacto metodológico:** VAL-2/3/8 alteram o **pipeline de medição** (não o prompt):
resultados pós-E2 constituem série de medição v2.2, documentada em
`docs/REPRODUCIBILITY.md`. As auditorias retroativas quantificam o quanto os dados do
TCC/v2.1 foram afetados — insumo direto para a seção de ameaças à validade da
dissertação.

## 8. Fase E3 — Reprodutibilidade total

**Branch:** `evolution/phase-3/full-reproducibility`

**Objetivo:** fechar a lacuna entre "temos snapshot de config" e "qualquer resultado é
reconstituível bit a bit anos depois" — a exigência da banca.

**Mudanças:**

1. **REP-1 — Digest do modelo (o item mais importante da fase).**
   Novo `OllamaAdapter.get_model_info(model)` chamando `POST /api/show`: captura
   `digest`, `modified_at`, família, parâmetros, quantização, e `ollama --version`.
   Gravado: no `config_snapshot` da sessão (local + cloud), em cada registro JSONL
   (`model_digest`), e em `llm_models` (nova coluna `digest`, migration
   `003_model_digest.sql`). Sessão aborta com erro claro se o Ollama não responder o
   show (sem digest = sem rastreabilidade). Teste com mock.
2. **REP-2 — Registro por análise do contexto efetivo.**
   Cada resultado ganha: `num_ctx_effective`, `num_predict_effective`, `seed_effective`
   (inclusive no regime aleatório — sortear o seed **no cliente** e enviá-lo, para que
   "aleatório" seja reprodutível), `prompt_chars`, `prompt_sha256_effective` (hash do
   prompt completo enviado, template+contexto+diff), `diff_sha256`. O prompt completo
   não precisa ser armazenado (grande); o hash + parâmetros de redução permitem
   reconstruí-lo determinística e verificavelmente a partir do git.
3. **REP-3 — Hardware no snapshot.**
   Mover `REFAN_NUM_GPU_LAYERS` de `config.py:142-157` para `RefanSettings`; coletar
   (best-effort, com fallback `unknown`): GPU (nome/VRAM via `nvidia-smi`/`system_profiler`),
   driver, SO, CPU, RAM. Preencher os campos já existentes de `runner_status`
   (`gpu_utilization_pct`, `memory_used_mb`) no heartbeat — colunas mortas hoje.
4. **REP-4 — `processing_time_ms` real** medido em torno da chamada ao adapter
   (`time.monotonic()`), gravado no resultado local e cloud. A materialized view volta
   a significar algo.
5. **REP-5 (conclusão) — Prompt carregado do arquivo versionado.**
   `optimized_prompt.py` passa a carregar o template de
   `configs/prompts/v2.0-mestrado.txt` (fonte única criada em E1); a constante vira
   leitura com cache; o hash de sessão passa a ser o hash do arquivo. Teste de
   igualdade com o hash registrado em `docs/PROMPTS.md`.
6. **REP-6** — `get_random_commit` recebe `random.Random(settings.llm_seed)` injetável.
7. **`refan doctor`** (novo subcomando): valida em um comando tudo que uma sessão
   reprodutível exige — Ollama up + versão, modelo presente + digest, `.env` completo,
   Supabase acessível (opcional), LFS ok, manifesto do baseline ok, espaço em disco,
   suíte offline verde. Exit code ≠ 0 com relatório do que falta. Vira o passo 1 do
   protocolo experimental.
8. **`refan reproduce <session.jsonl>`** (novo subcomando, esqueleto): lê o
   `config_snapshot` de uma sessão, confere digest do modelo local vs registrado,
   re-executa N commits da sessão e reporta divergências de classificação — a
   "prova de reprodutibilidade" executável para a defesa.

**Verificação:** sessão real curta; JSONL contém digest/num_ctx/seed/tempos; `refan
doctor` verde na máquina de desenvolvimento; `refan reproduce` de uma sessão nova
retorna 100% de concordância consigo mesma (com seed fixo).

**Impacto metodológico:** nenhum na condição experimental; apenas enriquecimento de
metadados. Registrar em `docs/REPRODUCIBILITY.md` que sessões anteriores a v2.2 não
têm digest (limitação histórica documentada).

## 9. Fase E4 — Robustez de persistência e operação

**Branch:** `evolution/phase-4/persistence-robustness`

**Objetivo:** garantir que horas de GPU nunca sejam perdidas por crash, concorrência ou
crescimento descontrolado de disco.

**Mudanças:**

1. **ROB-1 — Escrita atômica universal.**
   Novo utilitário `src/utils/atomic_io.py`: `atomic_write(path, data)` via
   temp+`os.replace` no mesmo diretório, e `file_lock(path)` (advisory `fcntl`/lockfile)
   para os masters compartilhados. Aplicar em: `_save_csv_data`
   (`llm_purity_analyzer.py:201-207`), `merge_jsonl_to_csv` (`persistence.py:125-142`),
   `save_analyzed_commits` (`data_handler.py:49-81`), `_save_session_analysis`, e no
   JSON de sessão. Corrigir a mensagem enganosa `"💾 Progress saved"`
   (`llm_purity_analyzer.py:627`) para refletir o que realmente aconteceu (JSONL) — ou
   implementar flush periódico do CSV (a cada N commits, configurável), decidindo
   explicitamente e documentando.
2. **ROB-2 — `_load_analyzed_commits` não silencia corrupção**: JSON inválido →
   renomear o corrompido para `.corrupt-<timestamp>` com warning alto, não `set()`
   silencioso.
3. **ROB-3 — JSONL honesto**: linha truncada detectada no merge/read gera warning
   estruturado com número da linha (não `continue` mudo); `SessionWriter.append` ganha
   `flush + os.fsync` opcional (`settings.jsonl_fsync`, default True — o custo é
   irrisório perto de uma inferência LLM).
4. **ROB-4 — Git handler eficiente e correto**:
   - Clone com `--filter=blob:none` (partial clone; blobs sob demanda no diff) —
     justificativa: a análise usa apenas `git diff h1 h2` de dois commits; histórico
     completo de blobs é desperdício de rede/disco. Fallback automático para clone
     completo se o servidor não suportar filter.
   - Path local `owner__repo` (elimina colisão de basename, `git_handler.py:26-31`).
   - Validação de repo são (`git rev-parse --git-dir`) com re-clone automático de
     diretório corrompido/parcial.
   - `fetch` somente quando um dos hashes não existe localmente (elimina `fetch --all`
     incondicional, `:44-51`).
   - Separador `--` em todos os comandos com args externos; validação de formato de
     hash (`^[0-9a-f]{7,40}$`) antes de qualquer subprocess.
   - `commit_exists` distingue "não existe" de "erro de git" (`:86-88`) — erros
     transitórios não viram skip silencioso.
   - Limpeza: `refan clean-repos` (novo subcomando) com orçamento de disco
     (`settings.repo_cache_max_gb`, LRU por último uso) + relatório.
5. **ROB-5 — Runner remoto honesto e seguro**:
   - `change_model`/`reanalyze_commit`: **implementar de fato** (consumo do
     `get_model_change_request` e da `reanalyze_queue` no loop do analisador) **ou
     remover** da fila de comandos aceitos — decisão recomendada: implementar
     `reanalyze` (barato: é um append na lista de trabalho) e remover `change_model`
     (troca de modelo mid-run muda a condição experimental da sessão — melhor exigir
     nova sessão). Comandos não suportados → `failed` com `result_message` explicativo,
     nunca "Executed".
   - Validação de payload (hash regex, modelo ∈ modelos registrados).
   - `pause` com timeout máximo (`settings.max_pause_s`, default 1h) → auto-resume com
     log; heartbeat continua durante pausa (hoje o runner pausado fica mudo).
   - Comando que lança exceção → marcar `failed` no cloud (hoje fica `acknowledged`
     eternamente, `command_handler.py:79-80`).
6. **ROB-6 — Cloud**: `REFRESH MATERIALIZED VIEW CONCURRENTLY model_metrics` ao
   finalizar cada sessão (com fallback logado); migration `004_rls_all_tables.sql`
   habilitando RLS + policies de leitura autenticada nas 5 tabelas restantes;
   **executar `get_advisors` (security + performance) no projeto Supabase real do
   refan** e tratar os apontamentos (o MCP configurado nesta máquina aponta para outro
   projeto — corrigir a configuração ou rodar pelo dashboard).
7. **ROB-7 — Logging de falhas**: `json_failures` vira `failures.jsonl` dentro de
   `get_model_paths()["ANALISES_DIR"]` (por modelo, não por CWD); excerpt real
   (`failure_logger.py:52-53`); exceções do logger logadas (não engolidas).

**Verificação:** teste de tortura — sessão de 20 commits com `kill -9` no meio →
reinício retoma sem perda além do commit em voo e sem arquivo corrompido; dois
processos concorrentes no mesmo CSV não perdem escrita (lock); `du` de `repositorios/`
respeita orçamento após `clean-repos`.

## 10. Fase E5 — Unificação arquitetural e CLI

**Branch:** `evolution/phase-5/single-engine`

**Objetivo:** um único motor de análise, uma única fonte de configuração, uma CLI
instalável — eliminar as classes inteiras de bugs "duas verdades" (ARQ-1/2) em vez de
remendar cada instância.

**Mudanças:**

1. **ARQ-1 — Motor único.** `LLMPurityAnalyzer` torna-se a única pipeline. As três
   funções `process_commits*` de `main.py:131-500` (~326 linhas triplicadas) são
   removidas; as opções correspondentes do menu passam a delegar ao analisador (thin
   wrapper). O rastreamento por `analyzed_commits.json` é aposentado (fonte única: CSV
   master + JSONL + cloud); script one-shot documenta como migrar registros antigos
   se necessário. `safe_processing_loop` (morto) e o `signal_handler` mentiroso
   (`main.py:44-53`) são removidos — o tratamento de interrupção correto já existe no
   analisador (ARQ-5 resolvido por eliminação).
2. **ARQ-2 — `settings` como fonte única.** `config.py` reduz-se a paths derivados e
   funções de filesystem; `set_llm_model` passa a mutar `settings.llm_model` (um só
   estado); `LLM_HOST` e o alias `LLM_MODEL` removidos (migração mecânica dos call
   sites); `get_timeout` perde o limiar mágico `50000` (`settings.py:121` →
   `settings.timeout_prompt_threshold`).
3. **ARQ-3 — Empacotamento correto.** Adotar src-layout real: mover o pacote para
   `src/refan/` com `[tool.setuptools.packages.find] where = ["src"]` (imports viram
   `from refan.handlers...`) — **ou**, alternativa de menor atrito, renomear o pacote
   no packaging mantendo layout (`packages = ["refan"]` via `package-dir`). Decisão
   recomendada: src-layout completo (é o padrão da comunidade e elimina o problema para
   sempre; o custo é um sed de imports + um commit mecânico verificado pela suíte).
   `refan --help` e `pipx install` passam a funcionar de qualquer CWD.
4. **ARQ-6/7 — CLI completa e sem armadilhas.**
   - Corrigir `--skip-analyzed` → `action=argparse.BooleanOptionalAction`
     (`--skip-analyzed/--no-skip-analyzed`), removendo `--no-skip`.
   - Todos os paths de dados resolvidos a partir de `PROJECT_ROOT`/settings (nunca CWD):
     `cli.py:194`, `menu_analysis.py:43,355,418`, `llm_purity_analyzer.py:105`,
     `CSVDataLoader` (`llm_handler.py:69`).
   - Promover scripts maduros a subcomandos: `refan seed-supabase`,
     `refan reconcile`, `refan verify-baseline`, `refan doctor` (E3),
     `refan clean-repos` (E4), `refan report` (E7). Os scripts viram wrappers finos ou
     são removidos.
   - Seleção de modelo: uma função em um lugar (`src/.../model_selection.py`), usada
     por `refan.py`, menu e CLI; opções 8/9 do menu LLM viram uma função
     parametrizada.
   - Menus: corrigir `NameError pd` (import no topo), opção 6 (remover ou apontar para
     dashboard real), `int()` protegido, `backup_file`, contagem "1-12".
5. **ARQ-8 — Nomes canônicos nas bordas.** Adapters são o único lugar que conhece
   nomes legados; internamente só `CommitPair`/`AnalysisResult`. Remover o rename
   `diff_size_chars→diff_size` (padronizar em um nome, migrando o leitor).
6. **QUA-5 — Observabilidade.** `get_logger()` em todos os handlers/analisador;
   `print` colorido permanece **apenas** na camada de menu/CLI interativa; flag global
   `--log-level` e log em arquivo por sessão (`output/models/<m>/logs/session_<ts>.log`).
   Todos os `except Exception` genéricos ganham `logger.exception(...)` (traceback
   preservado) e mensagens em **português** consistente (código/identificadores em
   inglês — convenção já dominante).

**Verificação:** suíte verde + testes novos dos menus (smoke via monkeypatch de
input); `refan --help` de um diretório qualquer; `grep -rn "analyzed_commits.json"`
vazio; contagem de linhas de `main.py` reduzida em ≥400.

**Impacto metodológico:** nenhum nos dados; o Motor A não era usado pela CLI headless.
Registrar no changelog que os menus interativos agora delegam ao mesmo motor da CLI
(elimina a possibilidade de resultados de origem ambígua).

## 11. Fase E6 — Qualidade contínua (gates)

**Branch:** `evolution/phase-6/quality-gates`

**Objetivo:** impedir regressão por construção: lint, tipos, cobertura e higiene
verificados em cada push.

**Mudanças:**

1. **Ruff** (lint + format, substitui black/isort/flake8 com uma dependência única —
   justificativa: ferramenta padrão atual, rápida, zero-config razoável):
   `[tool.ruff]` no `pyproject.toml`, line-length 100, regras `E,F,W,I,UP,B,SIM`;
   `ruff format`. Um commit mecânico de formatação inicial isolado (facilita
   `git blame` com `.git-blame-ignore-revs`).
2. **Mypy gradual**: strict nos módulos já tipados (`settings`, `command_handler`,
   `cli`, `models/`, `utils/persistence`, `timeutils`, `version_info`,
   `supabase_client`) via `[[tool.mypy.overrides]]`; `main.py`/`menu_analysis.py`
   entram como best-effort (`ignore_errors` temporário com issue de acompanhamento).
   Adicionar type hints onde faltam (`main.py`, `menu_analysis.py`, `git_handler`,
   `data_handler`, `purity_handler` — hoje sem anotações).
3. **Cobertura dos módulos órfãos (QUA-2), por prioridade científica**:
   1. `llm_purity_analyzer.py` — testes do fluxo de sessão com handlers mockados
      (skip/retry-failed/interrupção/persistência dos novos campos E2-E3);
   2. `purity_handler.py` — carga, coerção de tipos (a fragilidade da coerção
      booleana do pandas vira teste explícito), agreement unificado;
   3. `adapters.py` — roundtrip canônico↔legado sem perda;
   4. `failure_logger.py`, `llm_sizing.py` (regras de num_ctx de VAL-7);
   5. `data_handler.py` restante.
   Meta: nenhum módulo de produção com 0% (visualização tratada em E7).
4. **Marcadores aplicados de verdade (QUA-3)**: `slow` nos testes que exigem
   Ollama/rede; `integration` nos que leem CSVs reais; job de CI separado documenta a
   execução manual de `pytest -m slow` pré-release.
5. **CI ampliada** (`ci.yml`): jobs paralelos `lint` (ruff check + format --check),
   `typecheck` (mypy), `test` (matriz 3.10–3.12 com `--cov`, threshold inicial 60%
   subindo por fase até 75%, relatório no PR), `hygiene`
   (`check_repo_hygiene.py` de E0: arquivos `" 2"`, manifesto dos rastreados,
   `pip-audit` para CVEs nas deps pinadas).
6. **Pre-commit** (`.pre-commit-config.yaml`): ruff, ruff-format, checagem de arquivos
   `" 2"`, trailing whitespace, `check-added-large-files` (protege contra commit
   acidental de dados fora do LFS).
7. **Apêndice A executado**: remoção do código morto inventariado (com um commit por
   grupo, justificado).

**Verificação:** CI verde nos 4 jobs; `ruff check` e `mypy` limpos localmente;
cobertura ≥60% no relatório; pre-commit instalado e documentado no README.

## 12. Fase E7 — Instrumentação científica

**Branch:** `evolution/phase-7/statistical-instrumentation`

**Objetivo:** a ferramenta deixa de apenas *coletar* classificações e passa a
*produzir as análises estatísticas da dissertação* de forma reprodutível — hoje isso
está espalhado em scripts ad-hoc de `scripts/research/` e nos dois visualization
handlers semi-órfãos.

**Mudanças:**

1. **`src/analysis/metrics.py`** (novo, funções puras + testes com valores conhecidos
   da literatura):
   - Matriz de confusão LLM×Purity (com `not_comparable` explícito para NONE);
   - **Cohen's kappa** (concordância corrigida por acaso LLM×Purity — reportar só
     "% agreement" é metodologicamente frágil);
   - Kappa par-a-par entre modelos + **Fleiss' kappa** multi-modelo;
   - Intervalos de confiança (Wilson) para proporções;
   - **McNemar** para comparar dois modelos pareados no mesmo conjunto;
   - Justificativa das escolhas documentada em docstring com referências.
   Dependência nova: `scipy` (pinada) — ou implementação própria testada, decisão
   registrada (recomendado: scipy; reimplementar estatística é risco, não rigor).
2. **`refan report`**: gera, a partir de JSONL/cloud, relatório por modelo e
   cross-modelo em três formatos: Markdown (leitura), CSV (dados) e **tabelas
   LaTeX** (dissertação — `booktabs`), com as métricas acima + metadados de
   proveniência no rodapé (sessões, digests, prompt hash, tool version). Filtros:
   `--exclude-heuristic` (default, ver VAL-2), `--model`, `--prompt-version`.
3. **Estudo de estabilidade** (`refan stability --model X --n 5 --sample 50`):
   re-executa uma amostra com seeds distintos e reporta taxa de flip por commit —
   quantifica a variância do "instrumento LLM" (pergunta certa de banca; hoje não há
   resposta). Resultados versionados como experimento.
4. **Protocolo de validação humana** (`docs/EXPERIMENTS.md` + suporte na ferramenta):
   amostragem estratificada (por classe e por concordância/discordância com Purity)
   exportada via `refan sample --n 100 --stratify` para planilha de anotação manual;
   o Purity Checker não é oráculo perfeito — a comparação com julgamento humano é o
   que ancora as conclusões.
5. **Racionalização da visualização**: `llm_visualization_handler.py` (1042 linhas,
   órfão — QUA-4) é removido; `visualization_handler.py` é reduzido ao que o fluxo
   interativo realmente usa, sem `fig.show()` em batch, salvando nos diretórios por
   modelo; visual analítico rico fica no dashboard web (repo `refan-dashboard`,
   Fase 12) alimentado pelo Supabase — que passa a ter métricas com significado
   (REP-4, ROB-6).
6. **(Opcional, série experimental v3.0 — decisão explícita do pesquisador):**
   protótipo de **structured outputs** do Ollama (`format` com JSON schema, disponível
   desde Ollama 0.5): elimina por construção todo o parsing frágil (VAL-8) e o
   pattern `FINAL:`. Por alterar a condição experimental, entra como
   `prompt_versions` tag `v3.0-structured`, rodada em paralelo numa amostra e
   comparada (kappa v2.0×v3.0) antes de qualquer adoção. Não substitui a v2.0 nesta
   série.

**Verificação:** `refan report` sobre os dados do baseline TCC reproduz os números
publicados no TCC (validação do módulo contra resultado conhecido); testes de
`metrics.py` contra exemplos da literatura; estudo de estabilidade piloto executado.

## 13. Fase E8 — Documentação final e release

**Branch:** `evolution/phase-8/documentation-release`

**Objetivo:** consolidar a série e deixar o repositório "defensável" — legível por
banca, orientadora e por você-daqui-a-um-ano.

**Mudanças:**

1. **`README.md` reescrito** (DOC-1): o que é, arquitetura real (diagrama), quickstart
   (doctor → analyze → report), tabela de subcomandos, env vars, troubleshooting.
2. **`docs/ARCHITECTURE.md`**: visão atual pós-v2.2 (módulos, fluxo de dados, decisões)
   — os *_PLAN.md são registros históricos; este é o retrato vivo.
3. **`docs/EXPERIMENTS.md`**: protocolo experimental do mestrado (perguntas de
   pesquisa, variáveis, procedimento passo-a-passo por sessão, checklist doctor,
   critérios de exclusão, como citar sessões/digests na dissertação).
4. **`docs/adr/`**: registrar as decisões desta série como ADRs curtos (remoção da
   heurística de keywords; imutabilidade de prompt; src-layout; scipy; structured
   outputs adiado) — formaliza o que os planos já fazem em tabelas.
5. **`tests/README.md`** atualizado (DOC-2); **`CLAUDE.md`** revisado para refletir a
   arquitetura pós-E5 (motor único, settings única, subcomandos novos).
6. **`CHANGELOG.md`** iniciado (v2.0.0 → v2.1.0 → v2.2.0, keep-a-changelog).
7. **Release**: merge chain → `main`, tag `v2.2.0`, push com tags; abrir issues (ou
   seção backlog) para o Apêndice B.

**Verificação fim-a-fim da série (critérios de aceitação):**

```bash
git clone <repo> && cd refan && git lfs pull
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,json5,supabase]"
refan doctor                                   # verde (fora da raiz também)
python -m pytest -m "not slow" --cov           # verde, cobertura ≥75%, <5s
ruff check . && mypy                           # limpos
python scripts/data/generate_baseline_manifest.py --verify   # OK
refan analyze --model mistral --limit 5        # JSONL com digest, num_ctx, seed,
                                               # tempos, extraction_method
kill -9 <pid meio da sessão> && refan analyze --limit 5      # retoma sem perda/corrupção
refan report --model mistral                   # kappa + IC + LaTeX com proveniência
refan reproduce output/models/mistral/analises/sessions/<s>.jsonl  # 100% match
# CI: lint + typecheck + test(3.10-3.12) + hygiene verdes
```

---

## 14. Grafo de dependências e ordem

```
E0 (emergência)  ──→ tudo               [horas, hoje]
E1 (fechar v2.1) ──→ E2..E8             [requer E0]
E2 (validade)    ──→ E3, E7             [prioridade máxima pós-E1]
E3 (reprodutib.) ──→ E7
E4 (robustez)    — paralela a E3 (arquivos distintos; coordenar llm_purity_analyzer)
E5 (unificação)  — após E2 (evita retrabalho nos menus que serão removidos/finados)
E6 (qualidade)   — após E5 (lint/format sobre a árvore final; cobertura dos módulos que sobraram)
E7 (ciência)     — após E2+E3 (métricas exigem dados válidos e rastreáveis)
E8 (docs/release)— última
```

**Regra de ouro de sequenciamento:** nenhuma sessão de análise "para valer" (dados da
dissertação) antes do merge de **E2**; idealmente após **E3** (digest). Se houver
urgência de rodar análises antes disso, rodá-las cientes de que serão série piloto.

## 15. Estimativas de esforço (sessões de trabalho focado)

| Fase | Estimativa | Observação |
|------|-----------|------------|
| E0 | 0,5 dia | Mecânica + mudança do repo de diretório |
| E1 | 1–2 dias | Majoritariamente escrita (H9 já especificado) |
| E2 | 3–4 dias | 9 correções com testes + 2 scripts de auditoria |
| E3 | 2–3 dias | Digest/registro por análise + doctor/reproduce |
| E4 | 3 dias | atomic_io + git handler + runner + cloud |
| E5 | 3–4 dias | Remoção do Motor A + packaging + CLI (mecânico mas extenso) |
| E6 | 2–3 dias | Formatação inicial + mypy gradual + testes órfãos + CI |
| E7 | 3–4 dias | metrics + report + stability + validação contra TCC |
| E8 | 1–2 dias | Documentação + release |
| **Total** | **~4–5 semanas** de trabalho efetivo, paralelizável com o uso da ferramenta a partir de E3 |

## 16. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Mover o repo quebrar venv/paths/automações | Recriar venv (documentado em E0); grep por paths absolutos antes de mover; testar suíte + doctor após mover |
| Correções de VAL-* mudarem números já apresentados à orientadora | As auditorias retroativas (E2) produzem a tabela antes/depois **explicando por quê** — é ganho de credibilidade, não perda; comunicar proativamente |
| Remoção do Motor A quebrar fluxo de menu usado ocasionalmente | Fase E5 mantém os menus como wrappers; testes de smoke dos menus; dry-run manual das 12 opções antes do merge |
| src-layout (E5) gerar conflitos com branches paralelas | Fazer E5 num momento de branches limpas; commit mecânico de rename isolado; suíte como rede |
| `--filter=blob:none` falhar em servidores git antigos | Fallback automático para clone completo + log da decisão por repo |
| scipy aumentar superfície de dependências | Pinada com `==` no lock como as demais; alternativa própria descartada por risco de erro estatístico (registrado em ADR) |
| Structured outputs (v3.0) seduzir para troca prematura de protocolo | Item explicitamente marcado como série experimental opcional, gated por comparação kappa em amostra |
| Trigger de imutabilidade (VAL-4) atrapalhar correções legítimas de descrição | Trigger bloqueia apenas `system_prompt`/`sha256_hash`; `description` permanece editável |

## Apêndice A — Inventário de código morto a remover (E5/E6)

| Item | Local | Nota |
|------|-------|------|
| `_attempt_json_repair` + `_fix_quotes_in_json` | `llm_handler.py:722-823` | Duplicata inerte do json_parser central |
| Imports `estimate_token_count`, `reduce_diff_simple` | `llm_handler.py:143` | Não usados |
| `has_valid_classification` | `llm_handler.py:847-852` | Calculado e nunca lido |
| Branch inalcançável de `reduce_diff` + custo O(n²) | `llm_handler.py:166-187` | Reescrever com contador de tamanho incremental |
| Subsistema file-based diff (save/cleanup/branch de prompt) | `llm_handler.py` + `optimized_prompt.py:242-268` | Inalcançável (60k<100k) e conceitualmente quebrado (LLM não lê filesystem) — remover; VAL-7 cobre diffs grandes |
| `safe_processing_loop` | `main.py:80-119` | Morto |
| 3× `process_commits*` | `main.py:131-500` | Substituídos pelo motor único (E5) |
| Blocos de print comentados no signal_handler | `main.py:55-67` | Morto |
| `import json as _json` + reimports locais | `config.py:9,63` | Mortos |
| `llm_visualization_handler.py` | 1042 linhas | Órfão do app (só scripts deprecated) — remover com os scripts que o usam |
| `scripts/deprecated/` (31 arquivos) | — | Deletar em bloco (histórico preservado no git) |
| Opção 6 do menu LLM (script inexistente) | `menu_analysis.py:300-301` | Remover/redirecionar |
| Alias `LLM_MODEL` | `config.py:33,49` | Migrar call sites |

## Apêndice B — Backlog explícito (fora da série v2.2)

- **Fase 12** (dashboard `refan-dashboard`): consumir os novos metadados (digest,
  falhas, tempos reais); painel de falhas; RLS revisado — o runner continua único
  escritor via service key.
- **Structured outputs v3.0** (E7.6) se o piloto justificar.
- **Depósito Zenodo (DOI)** do baseline + snapshot v2.2 para a dissertação (plano B do
  LFS já cogitado no HARDENING_PLAN).
- **Paralelização produtor-consumidor** (extração de diff em thread separada da
  inferência): ganho real de throughput; adiado porque muda o perfil de carga do
  Ollama — medir antes.
- **Multi-backend LLM** (protocolo `LLMAdapter` já existe): OpenAI-compat local
  (vLLM/llama.cpp) para validação cruzada de runtime.
- Migração dos dados históricos do TCC para o Supabase (backfill previsto na Fase 11.1
  e nunca executado — decidir se o cloud é fonte analítica completa ou só da série nova).
