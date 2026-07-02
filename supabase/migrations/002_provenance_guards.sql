-- 002_provenance_guards.sql — defesa em profundidade para proveniência
-- (EVOLUTION_PLAN.md, Fase E2, achados VAL-4 e VAL-5).
--
-- O código do runner já foi corrigido (get-then-insert em prompt_versions;
-- upsert de commits omitindo chaves None), mas registros de pesquisa merecem
-- proteção NA CAMADA DO BANCO contra qualquer cliente futuro (dashboard,
-- scripts, SQL manual):
--
-- 1. prompt_versions: system_prompt/sha256_hash são imutáveis após o insert
--    (a descrição permanece editável).
-- 2. commits.purity_analysis: valor não-nulo nunca regride para NULL nem é
--    alterado — o baseline Purity é a variável independente da pesquisa.
--
-- Aplicação: supabase db push, ou SQL Editor do dashboard, ou MCP
-- apply_migration. Verificação pós-aplicação ao final do arquivo.

-- ---------------------------------------------------------------------------
-- 1. Imutabilidade de versões de prompt (VAL-4)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.reject_prompt_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.system_prompt IS DISTINCT FROM OLD.system_prompt
       OR NEW.sha256_hash IS DISTINCT FROM OLD.sha256_hash
       OR NEW.version_tag IS DISTINCT FROM OLD.version_tag THEN
        RAISE EXCEPTION
            'prompt_versions é imutável (version_tag/system_prompt/sha256_hash). '
            'Registre uma NOVA versão em vez de alterar % (VAL-4, EVOLUTION_PLAN.md).',
            OLD.version_tag;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prompt_versions_immutable ON public.prompt_versions;
CREATE TRIGGER trg_prompt_versions_immutable
    BEFORE UPDATE ON public.prompt_versions
    FOR EACH ROW
    EXECUTE FUNCTION public.reject_prompt_version_mutation();

-- ---------------------------------------------------------------------------
-- 2. Baseline Purity não regride (VAL-5)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.protect_commit_purity_analysis()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.purity_analysis IS NOT NULL
       AND NEW.purity_analysis IS DISTINCT FROM OLD.purity_analysis THEN
        RAISE EXCEPTION
            'commits.purity_analysis é o baseline da pesquisa e não pode ser '
            'alterado/anulado (commit %, % -> %). VAL-5, EVOLUTION_PLAN.md.',
            OLD.commit_hash_current, OLD.purity_analysis, NEW.purity_analysis;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_commits_purity_protected ON public.commits;
CREATE TRIGGER trg_commits_purity_protected
    BEFORE UPDATE ON public.commits
    FOR EACH ROW
    EXECUTE FUNCTION public.protect_commit_purity_analysis();

-- ---------------------------------------------------------------------------
-- Diagnóstico de dano pré-existente (VAL-5): commits cujo purity foi anulado
-- por syncs anteriores à correção. Rode como SELECT; a recuperação é feita
-- re-executando scripts/seed_supabase.py (idempotente) a partir do CSV.
-- ---------------------------------------------------------------------------
-- SELECT commit_hash_current
--   FROM public.commits
--  WHERE purity_analysis IS NULL;

-- Verificação pós-aplicação (ambas devem falhar com a exceção dos triggers):
-- UPDATE public.prompt_versions SET sha256_hash = 'x' WHERE version_tag = 'v2.0-mestrado';
-- UPDATE public.commits SET purity_analysis = NULL WHERE purity_analysis IS NOT NULL LIMIT 1;
