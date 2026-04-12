-- Refan: Schema inicial para persistência cloud via Supabase
-- Refs: ARCHITECTURE_PLAN.md Phase 11.1

-- ============================================================
-- Tabelas de dados base
-- ============================================================

-- Dataset de commits (carregado uma vez do CSV)
CREATE TABLE commits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    commit_hash_current TEXT NOT NULL,
    commit_hash_before TEXT NOT NULL,
    repository_url TEXT NOT NULL,
    project_name TEXT NOT NULL,
    purity_analysis TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(commit_hash_current)
);
CREATE INDEX idx_commits_purity ON commits(purity_analysis);
CREATE INDEX idx_commits_project ON commits(project_name);

-- Modelos LLM registrados
CREATE TABLE llm_models (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    safe_name TEXT NOT NULL,
    family TEXT,
    parameter_count TEXT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Versões de prompt (reprodutibilidade acadêmica)
CREATE TABLE prompt_versions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    version_tag TEXT NOT NULL UNIQUE,
    system_prompt TEXT NOT NULL,
    classification_criteria TEXT,
    description TEXT,
    sha256_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Resultados do PurityChecker (baseline)
CREATE TABLE purity_checker_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    commit_id UUID NOT NULL REFERENCES commits(id),
    purity_classification TEXT,
    purity_description TEXT,
    refactoring_type TEXT,
    refactoring_description TEXT,
    UNIQUE(commit_id, refactoring_type)
);

-- ============================================================
-- Tabelas de análise
-- ============================================================

-- Sessões de análise (uma por batch run)
CREATE TABLE analysis_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    model_id UUID NOT NULL REFERENCES llm_models(id),
    prompt_version_id UUID NOT NULL REFERENCES prompt_versions(id),
    runner_hostname TEXT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','paused','completed','failed','cancelled')),
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    config_snapshot JSONB NOT NULL,
    total_planned INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_skipped INTEGER DEFAULT 0,
    purity_filter TEXT,
    error_message TEXT
);

-- Resultados individuais (1 row por commit × sessão)
CREATE TABLE analysis_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES analysis_sessions(id),
    commit_id UUID NOT NULL REFERENCES commits(id),
    model_id UUID NOT NULL REFERENCES llm_models(id),
    prompt_version_id UUID NOT NULL REFERENCES prompt_versions(id),
    classification TEXT NOT NULL
        CHECK (classification IN ('PURE','FLOSS','FAILED','ERROR')),
    justification TEXT,
    confidence_level TEXT,
    technical_evidence TEXT,
    llm_raw_response TEXT,
    extraction_method TEXT,
    diff_size_chars INTEGER,
    diff_lines INTEGER,
    processing_time_ms INTEGER,
    diff_source TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(session_id, commit_id)
);
CREATE INDEX idx_results_commit ON analysis_results(commit_id);
CREATE INDEX idx_results_model ON analysis_results(model_id);
CREATE INDEX idx_results_classification ON analysis_results(classification);
CREATE INDEX idx_results_commit_model ON analysis_results(commit_id, model_id);

-- Falhas de análise (substitui json_failures.json)
CREATE TABLE analysis_failures (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID REFERENCES analysis_sessions(id),
    commit_id UUID REFERENCES commits(id),
    model_id UUID NOT NULL REFERENCES llm_models(id),
    error_type TEXT NOT NULL,
    error_message TEXT,
    llm_raw_response TEXT,
    prompt_excerpt TEXT,
    occurred_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Tabelas de controle do runner
-- ============================================================

-- Status do runner (heartbeat)
CREATE TABLE runner_status (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    runner_id TEXT NOT NULL UNIQUE,
    session_id UUID REFERENCES analysis_sessions(id),
    status TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle','running','paused','error','offline')),
    current_commit_hash TEXT,
    current_commit_index INTEGER,
    total_commits_in_batch INTEGER,
    model_name TEXT,
    last_heartbeat TIMESTAMPTZ DEFAULT now(),
    ollama_status TEXT,
    gpu_utilization_pct REAL,
    memory_used_mb REAL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Fila de comandos (controle remoto)
CREATE TABLE command_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    runner_id TEXT NOT NULL,
    command TEXT NOT NULL
        CHECK (command IN (
            'pause','resume','cancel','restart',
            'skip_commit','reanalyze_commit',
            'change_model','change_prompt','update_config'
        )),
    payload JSONB,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','acknowledged','completed','failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_message TEXT
);
CREATE INDEX idx_commands_pending ON command_queue(runner_id, status)
    WHERE status = 'pending';

-- ============================================================
-- Views
-- ============================================================

CREATE VIEW cross_model_comparison AS
SELECT
    c.commit_hash_current,
    c.project_name,
    c.purity_analysis AS purity_checker,
    json_object_agg(m.name, ar.classification) AS model_classifications,
    COUNT(DISTINCT ar.model_id) AS models_analyzed,
    CASE
        WHEN COUNT(DISTINCT ar.classification)
             FILTER (WHERE ar.classification IN ('PURE','FLOSS')) = 1
        THEN 'unanimous' ELSE 'disagreement'
    END AS consensus_status
FROM commits c
LEFT JOIN analysis_results ar ON c.id = ar.commit_id
LEFT JOIN llm_models m ON ar.model_id = m.id
WHERE ar.classification IN ('PURE','FLOSS')
GROUP BY c.id;

CREATE MATERIALIZED VIEW model_metrics AS
SELECT
    m.name AS model_name,
    COUNT(*) AS total_analyzed,
    COUNT(*) FILTER (WHERE ar.classification = 'PURE') AS pure_count,
    COUNT(*) FILTER (WHERE ar.classification = 'FLOSS') AS floss_count,
    COUNT(*) FILTER (WHERE ar.classification = 'FAILED') AS failed_count,
    ROUND(AVG(ar.processing_time_ms)::numeric, 0) AS avg_processing_time_ms,
    COUNT(*) FILTER (WHERE
        (c.purity_analysis = 'TRUE' AND ar.classification = 'PURE') OR
        (c.purity_analysis = 'FALSE' AND ar.classification = 'FLOSS')
    ) AS agree_with_purity,
    COUNT(*) FILTER (WHERE c.purity_analysis IN ('TRUE','FALSE')) AS purity_comparable
FROM analysis_results ar
JOIN llm_models m ON ar.model_id = m.id
JOIN commits c ON ar.commit_id = c.id
WHERE ar.classification IN ('PURE','FLOSS')
GROUP BY m.name;

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE runner_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_sessions ENABLE ROW LEVEL SECURITY;

-- Leitura para todos autenticados
CREATE POLICY "read_results" ON analysis_results FOR SELECT TO authenticated USING (true);
CREATE POLICY "read_commands" ON command_queue FOR SELECT TO authenticated USING (true);
CREATE POLICY "read_runner" ON runner_status FOR SELECT TO authenticated USING (true);
CREATE POLICY "read_sessions" ON analysis_sessions FOR SELECT TO authenticated USING (true);

-- Dashboard pode inserir comandos
CREATE POLICY "insert_commands" ON command_queue FOR INSERT TO authenticated WITH CHECK (true);

-- Realtime: habilitar para tabelas que o dashboard observa
ALTER PUBLICATION supabase_realtime ADD TABLE runner_status;
ALTER PUBLICATION supabase_realtime ADD TABLE analysis_results;
ALTER PUBLICATION supabase_realtime ADD TABLE analysis_sessions;
