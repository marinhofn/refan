# Versões de Prompt — registro de proveniência

> Documento previsto na Fase H9 (`HARDENING_PLAN.md`) e complementado pela Fase E1
> (`EVOLUTION_PLAN.md`, achado REP-5). Última atualização: 2026-07-01.

Os prompts são **artefatos experimentais de primeira classe**: qualquer alteração em seu
texto altera a condição experimental e invalida a comparabilidade com resultados
anteriores. Por isso:

1. Cada versão de prompt tem uma **tag imutável**, um **arquivo verbatim** em
   `configs/prompts/<tag>.txt` e um **SHA-256** registrado aqui e na tabela
   `prompt_versions` do Supabase.
2. **Nunca edite um prompt publicado.** Mudanças exigem nova tag (novo arquivo, novo
   hash, nova entrada em `prompt_versions`) e menção explícita em
   `docs/REPRODUCIBILITY.md`.
3. O teste `tests/test_prompt_artifacts.py` falha se a constante usada pelo código
   divergir do arquivo verbatim correspondente — o arquivo é a referência citável; a
   constante é o que executa. (A inversão — código *carregar* do arquivo — está
   planejada na Fase E3 do `EVOLUTION_PLAN.md`.)

## Versões registradas

| Tag | Arquivo | SHA-256 | Tamanho | Constante no código | Uso |
|-----|---------|---------|---------|--------------------|-----|
| `v1.0-tcc` | `configs/prompts/v1.0-tcc.txt` | `5cf305d1e4f0bbf91908a37a68538efcb53022c9e396eb493bafe690f2b6f468` | 1.695 chars | `LLM_PROMPT` (`src/core/config.py`) | Prompt original do TCC; hoje usado apenas pelo caminho legado `LLMHandler.analyze_commit` (menu interativo, Motor A — remoção prevista na Fase E5) |
| `v2.0-mestrado` | `configs/prompts/v2.0-mestrado.txt` | `2c24d204ecf09e53e2b3ebff745aed5b5e1442436cdd84727323721a89e32ccd` | 6.320 chars | `OPTIMIZED_LLM_PROMPT` (`src/analyzers/optimized_prompt.py`) | Prompt da pipeline atual (`LLMPurityAnalyzer`); é o hash gravado como `prompt_sha256` em cada registro JSONL desde a Fase H5 |

Observações de escopo:

- O hash cobre **o template do sistema**, não o prompt efetivamente enviado (que
  concatena contexto do commit e diff — ver `optimized_prompt.py::build_optimized_commit_prompt_with_file_support`).
  O registro do hash do prompt efetivo por análise está planejado na Fase E3
  (`EVOLUTION_PLAN.md`, REP-2).
- No regime `v1.0-tcc`, o texto do sistema era complementado em tempo de construção
  pelo esqueleto `JSON_STRUCTURE` (`src/core/config.py`) e pelo contexto do commit.
  O arquivo verbatim registra somente o texto do sistema.
- A atribuição exata prompt→sessão para os dados históricos do TCC não foi registrada
  à época (limitação documentada); a partir da Fase H5 todo registro persistido carrega
  `prompt_sha256`.

## Racional do viés conservador ("Default: FLOSS")

O prompt `v2.0-mestrado` instrui explicitamente: *"Default Assumption: FLOSS"*,
*"When uncertain → Choose FLOSS"*, *"Mixed changes → Always FLOSS"*.

**Justificativa metodológica.** A definição de refatoração *pure* é universalmente
quantificada: **zero** mudanças comportamentais. Uma única evidência de mudança
funcional é suficiente para tornar o commit *floss*, enquanto afirmar *pure* exige
verificar a ausência de mudanças em todo o diff. A assimetria epistemológica justifica
o default conservador — o mesmo racional da regra FALSE>TRUE na agregação do baseline
Purity (`purity_handler._resolve_classification_conflict`), mantendo os dois lados da
comparação coerentes.

**Limitações conhecidas (mantidas por comparabilidade, candidatas à série v3.0):**

1. **Assimetria de erro induzida**: o viés aumenta o recall de FLOSS às custas do
   recall de PURE; commits pure de grande volume tendem a ser classificados floss sob
   incerteza. As métricas devem ser lidas com essa assimetria em mente (por classe,
   nunca só acurácia global).
2. **Few-shot desbalanceado**: o prompt contém um único exemplo completo, da classe
   PURE, sem exemplo FLOSS.
3. **Instruções de formato contraditórias**: o corpo pede "análise breve → linha
   `FINAL:` → JSON", mas a "Priority instruction" final pede "JSON ONLY / DO NOT
   explain". Modelos diferentes resolvem a contradição de formas diferentes, o que
   aumenta a variância de formato (mitigada pelo parser em cascata; ver
   `EVOLUTION_PLAN.md`, VAL-10).
4. **Fallback de schema força floss**: a instrução "se não conseguir produzir o JSON,
   retorne com `refactoring_type: floss`" faz do próprio formato uma fonte de rótulo
   FLOSS — casos assim devem ser tratados como falha, não como medição (correção do
   lado do parser na Fase E2, VAL-2/VAL-8).

**Decisão registrada**: o texto de `v2.0-mestrado` **não será alterado** durante as
séries v2.x — corrigir as limitações acima invalidaria a comparação com o baseline do
TCC e com as sessões já executadas. Melhorias de prompt constituem a série
experimental `v3.0` (ver `EVOLUTION_PLAN.md`, Fase E7, item 6) e serão comparadas
contra `v2.0-mestrado` em amostra controlada antes de qualquer adoção.
