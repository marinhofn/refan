-- 004_rls_and_metrics_refresh.sql — RLS completo e refresh das métricas
-- (EVOLUTION_PLAN.md, Fase E4, achado ROB-6).
--
-- 1. O schema inicial habilitou RLS em apenas 4 das 9 tabelas; as demais
--    (commits, llm_models, prompt_versions, analysis_failures,
--    purity_checker_results) ficavam expostas aos roles anon/authenticated
--    conforme os grants padrão — incluindo analysis_failures, que carrega
--    llm_raw_response/prompt_excerpt. Política: leitura para autenticados;
--    escrita SOMENTE pelo runner (service_role, que bypassa RLS).
-- 2. A materialized view model_metrics nunca era atualizada (nenhum REFRESH
--    no código). A função refresh_model_metrics() é chamada pelo runner ao
--    finalizar cada sessão (via RPC).
--
-- Aplicação: supabase db push, SQL Editor, ou MCP apply_migration.

-- ---------------------------------------------------------------------------
-- 1. RLS nas tabelas restantes (leitura autenticada; escrita só service_role)
-- ---------------------------------------------------------------------------

ALTER TABLE public.commits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.llm_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_failures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purity_checker_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "read_all" ON public.commits;
CREATE POLICY "read_all" ON public.commits
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "read_all" ON public.llm_models;
CREATE POLICY "read_all" ON public.llm_models
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "read_all" ON public.prompt_versions;
CREATE POLICY "read_all" ON public.prompt_versions
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "read_all" ON public.analysis_failures;
CREATE POLICY "read_all" ON public.analysis_failures
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "read_all" ON public.purity_checker_results;
CREATE POLICY "read_all" ON public.purity_checker_results
    FOR SELECT TO authenticated USING (true);

-- ---------------------------------------------------------------------------
-- 2. Refresh de model_metrics via RPC (chamado pelo runner pós-sessão)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.refresh_model_metrics()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW public.model_metrics;
END;
$$;

-- Somente o runner (service_role) executa o refresh.
REVOKE EXECUTE ON FUNCTION public.refresh_model_metrics() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.refresh_model_metrics() FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_model_metrics() TO service_role;
