-- 003_model_digest.sql — identidade exata do modelo Ollama
-- (EVOLUTION_PLAN.md, Fase E3, achado REP-1).
--
-- Tags do Ollama são mutáveis ("mistral" hoje != "mistral" daqui a 3 meses);
-- sem o digest dos pesos, dois runs "com o mesmo modelo" são indistinguíveis
-- a posteriori. O runner agora captura digest e versão do Ollama por sessão
-- (config_snapshot em analysis_sessions) e por registro (JSONL local); esta
-- migration acrescenta o estado mais recente observado ao registro do modelo.
--
-- Aplicação: supabase db push, SQL Editor do dashboard, ou MCP apply_migration.

ALTER TABLE public.llm_models
    ADD COLUMN IF NOT EXISTS digest TEXT,
    ADD COLUMN IF NOT EXISTS last_seen_ollama_version TEXT;

COMMENT ON COLUMN public.llm_models.digest IS
    'Digest (sha256) dos pesos do modelo no Ollama, conforme último upsert do runner (REP-1). Histórico completo por sessão em analysis_sessions.config_snapshot.';
COMMENT ON COLUMN public.llm_models.last_seen_ollama_version IS
    'Versão do runtime Ollama observada no último upsert do runner.';
