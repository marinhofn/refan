# Reprodutibilidade — regimes experimentais, registro e procedimento

> Documento previsto na Fase H9 (`HARDENING_PLAN.md`) e complementado pela Fase E1
> (`EVOLUTION_PLAN.md`). Última atualização: 2026-07-01.

Este documento define **o que é registrado** por análise, **quais regimes
experimentais** existem e **como reproduzir** uma sessão. Lacunas conhecidas são
listadas ao final com a fase planejada que as fecha — transparência antes de
completude.

## 1. Séries experimentais e regimes

| Série | Período | Seed | Timestamps | Rastreio de prompt/ferramenta |
|-------|---------|------|------------|-------------------------------|
| **TCC (baseline)** | até set/2025 | sem seed (regime não determinístico do Ollama) | naive, hora local da máquina | não registrado por sessão (limitação histórica) |
| **v2.1+ (mestrado)** | a partir de jun/2026 | **fixo, 42** (`RefanSettings.llm_seed`), enviado em `options.seed` do Ollama | UTC timezone-aware (`src/utils/timeutils.py`) | `prompt_sha256` + `tool_version` em cada registro JSONL e no `config_snapshot` da sessão |

Decisões registradas (`HARDENING_PLAN.md`, Fase H5):

- **Seed fixo 42 por default.** Com `temperature=0.1` e seed fixo, a geração torna-se
  determinística por modelo/versão de runtime. Isso **difere do regime do TCC** — por
  isso os resultados v2.1+ constituem uma **nova série experimental**, comparada ao
  baseline como série, nunca misturada. Para replicar o regime antigo:
  `use_random_seed=True` (o seed é então omitido do payload; registro do seed efetivo
  nesse regime é lacuna REP-2, fase E3).
- **UTC a partir da H5.** Timestamps históricos (naive, hora local) **não foram
  reescritos** — a descontinuidade é aceita e documentada. Comparações temporais entre
  séries devem considerar o offset de fuso (UTC-3 em geral).
- **`tool_version`** = `git describe --tags --always --dirty`. O sufixo `-dirty`
  denuncia execução com working tree modificada — resultados `-dirty` não são
  auditáveis até o commit correspondente e **não devem ser usados na dissertação**.
- **`prompt_sha256`** = SHA-256 do template do sistema (ver `docs/PROMPTS.md` para as
  versões registradas e o escopo exato do hash).

## 2. O que é registrado hoje, por sessão e por análise

**Por sessão** (`config_snapshot`, local no JSON de sessão e cloud em
`analysis_sessions`): todos os campos de `RefanSettings.to_dict()` — temperatura,
`num_predict`, `keep_alive`, seed, thresholds de diff, janelas de contexto, timeouts,
modelo ativo — mais `prompt_sha256`, `tool_version`, `runner_id` e filtro de purity.
A service key do Supabase é **excluída** do snapshot por construção.

**Por análise** (registro JSONL em
`output/models/<modelo>/analises/sessions/session_<ts>.jsonl` e linha em
`analysis_results` no cloud): hashes do commit, repositório, classificação,
justificativa, resposta bruta do LLM, tamanho do diff, timestamps UTC,
`prompt_sha256`, `tool_version`.

## 3. Procedimento de reprodução de uma sessão

1. **Recuperar o snapshot**: abra o JSONL da sessão (ou a linha em
   `analysis_sessions`) e anote `tool_version`, `prompt_sha256`, `config_snapshot`
   (modelo, seed, temperatura, filtros) e a lista de commits analisados.
2. **Restaurar a ferramenta**: `git checkout <tool_version>` (tag ou hash; se houver
   sufixo `-dirty`, a sessão não é reproduzível com fidelidade — descarte).
   Ambiente: `pip install -r requirements-lock.txt` em Python 3.12 (dependências
   transitivas congeladas).
3. **Restaurar o modelo**: `ollama pull <modelo>` — **atenção**: tags do Ollama são
   mutáveis e o digest do modelo não era capturado antes da fase E3
   (`EVOLUTION_PLAN.md`, REP-1). Para sessões pré-E3, a identidade exata dos pesos não
   é verificável a posteriori (limitação documentada; a partir da E3 o digest é
   gravado e conferível via `ollama show`).
4. **Verificar integridade dos insumos**:
   `python scripts/data/generate_baseline_manifest.py --verify` e
   `python scripts/data/check_repo_hygiene.py`.
5. **Reexecutar**: `python refan.py analyze --model <modelo> --filter <filtro>
   --limit <n>` com `.env` idêntico (`REFAN_PROMPT_VERSION`, seed default).
6. **Comparar**: as classificações por commit devem coincidir registro a registro
   (com seed fixo e mesmo digest de modelo). Divergências devem ser investigadas antes
   de qualquer uso dos dados (`scripts/data/reconcile_supabase.py` cobre a comparação
   local↔cloud; comparação sessão↔sessão automatizada está planejada como
   `refan reproduce`, fase E3).

## 4. Agregação do baseline Purity: FALSE > TRUE

O CSV `csv/puritychecker_detailed_classification.csv` traz **uma linha por
refatoração detectada**, logo um mesmo commit aparece várias vezes e pode carregar
classificações conflitantes (`TRUE` e `FALSE`). A regra de consolidação
(`src/handlers/purity_handler.py::_resolve_classification_conflict`) é:

> **Se qualquer linha do commit é `FALSE`, o commit consolida como `FALSE`.**

Justificativa: *pure* é uma propriedade universalmente quantificada — basta **uma**
evidência de mudança funcional para o commit não ser pure. A regra é coerente com o
viés conservador do prompt ("when uncertain → FLOSS", ver `docs/PROMPTS.md`), mantendo
os dois lados da comparação (baseline e LLM) sob o mesmo princípio epistemológico.
Commits consolidados por conflito carregam a flag `had_classification_conflict=True`
e preservam todas as descrições originais concatenadas — a agregação é auditável e
não destrói informação.

## 5. Incidente de integridade do baseline (jul/2026) — registrado e resolvido

Em 2026-07-01, a verificação `generate_baseline_manifest.py --verify` do snapshot
imutável `baseline_tcc_2025/` **falhou**: 5 arquivos ausentes e 67 intrusos. Causa:
o repositório residia em diretório sincronizado pelo iCloud Drive, que cria cópias de
conflito com sufixo `" 2"` e removeu arquivos originais da working tree (99 artefatos
foram identificados no repositório como um todo, todos byte-idênticos aos originais
quando comparados).

Resolução (Fase E0 do `EVOLUTION_PLAN.md`): os 5 arquivos foram restaurados a partir
do Git LFS (`git restore`), os artefatos `" 2"` removidos após comparação byte a byte,
e a verificação voltou a passar — **"Baseline íntegro: 281 arquivos conferem com o
manifesto"**. Nenhum conteúdo versionado foi alterado: o snapshot commitado no LFS
permaneceu intacto durante todo o incidente (o dano era restrito à working tree).

Salvaguardas adicionadas: padrões `* 2*` no `.gitignore`, verificação
`scripts/data/check_repo_hygiene.py` local e como job `hygiene` na CI, e a
recomendação registrada de manter o repositório **fora** de diretórios sincronizados
por iCloud/Drive/Dropbox.

## 6. Lacunas conhecidas de reprodutibilidade (e onde serão fechadas)

| Lacuna | Impacto | Fase planejada (`EVOLUTION_PLAN.md`) |
|--------|---------|--------------------------------------|
| Digest do modelo Ollama não capturado (tag mutável) | Identidade dos pesos não verificável a posteriori | E3 (REP-1) |
| `num_ctx` efetivo, seed efetivo (regime aleatório) e hash do prompt completo não registrados por análise | Reconstrução exige recomputação a partir do snapshot | E3 (REP-2) |
| Hardware (GPU/driver/`REFAN_NUM_GPU_LAYERS`) fora do `config_snapshot` | Condições de execução parcialmente registradas | E3 (REP-3) |
| `processing_time_ms` sempre 0 | Métricas de desempenho sem significado | E3 (REP-4) |
| Validação de prompt contra `prompt_versions` pode sobrescrever registro histórico (upsert) | Proveniência de prompt violável | E2 (VAL-4) |
| Truncamento de contexto não detectado/registrado (`num_ctx` menor que o prompt) | Modelo pode classificar sem ver o diff inteiro, sem rastro | E2 (VAL-7) |
| `confidence_level`/`technical_evidence` fabricados no caminho de extração dominante | Duas variáveis registradas são constantes artificiais nas séries ≤ v2.1 | E2 (VAL-3); dados históricos: usar apenas classificação e justificativa |

Enquanto a Fase E2 não estiver mergeada, **nenhuma sessão nova deve alimentar a
dissertação** — ver "Regra de ouro de sequenciamento" no `EVOLUTION_PLAN.md`.
