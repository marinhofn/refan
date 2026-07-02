# Plano de Refatoração e Evolução Arquitetural — Refan v2

## Contexto

O Refan é uma ferramenta acadêmica que classifica commits Git como **pure** ou **floss** refactoring usando LLMs locais (Ollama). Foi desenvolvida como TCC na UFCG e agora evolui para o mestrado com requisitos significativamente expandidos:

1. **Refatoração interna** (Fases 0-10): limpar o código atual (duplicação, magic values, handlers paralelos, etc.)
2. **Infraestrutura distribuída** (Fase 11): Supabase Cloud como persistência central, controle remoto do runner
3. **Frontend dashboard** (Fase 12): React + TypeScript + Shadcn em repo separado, monitoramento em tempo real

### Hardware

| Máquina | Papel | Specs |
|---------|-------|-------|
| **Desktop** (casa) | Analysis runner | Ryzen 7 5700X, 32GB DDR4, RTX 4070 Ti Super 16GB VRAM, Ubuntu (recomendado) |
| **MacBook Pro** | Monitoramento + controle | M4 Pro 24GB |

### Decisões Arquiteturais Chave

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Persistência central | **Supabase Cloud** | Auth, Realtime, Postgres, Storage — sem servidor custom |
| Runner → Cloud | **supabase-py (SDK direto)** | Runner é backend confiável, sem camada intermediária |
| Real-time | **Supabase Realtime (Postgres changes)** | Zero código de servidor; automático a partir de mudanças no DB |
| Controle remoto | **Command queue table + polling** | Sobrevive desconexões; auditável; sem port forwarding |
| Docker no runner | **Não** (inicialmente) | GPU passthrough adiciona fragilidade; ferramenta single-user |
| OS do runner | **Ubuntu nativo** (não WSL2) | Acesso direto à GPU, melhor gerenciamento de memória, estabilidade para runs longos |
| Frontend | **React + TypeScript + Shadcn/UI** | Repo separado; Shadcn dá componentes polidos com esforço mínimo |
| Auth | **Supabase Auth** | Já no stack; email/password para equipe pequena |
| Offline | **JSONL local + sync** | Sessões de pesquisa são longas; internet pode cair |

---

## Estratégia de Branches e Commits

> Detalhada completamente em `REFACTORING_PLAN.md` (seção "Estratégia de Branches e Commits"). Resumo:

- **Branch de integração**: `refactor/v2-architecture` (já criada)
- **Branch por fase**: `refactor/phase-N/nome` (feature branches mergeadas com `--no-ff`)
- **Commits**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `build:`, `chore:`)
- **Tags**: `v2.0.0-phase-N` em cada milestone, `v2.0.0` no merge final em `main`
- **Fases 11-12**: branches próprias a partir de `main` após `v2.0.0`

---

## Parte I: Refatoração Interna (Fases 0-10)

> As Fases 0-10 estão detalhadas em `REFACTORING_PLAN.md` com line numbers, comparações byte-a-byte, e comandos de verificação. Abaixo está o resumo executivo — consultar o arquivo completo para implementação.

### Fase 0: Infraestrutura de Testes
- `pyproject.toml` + `conftest.py` com fixtures comuns
- Testes de caracterização para `extract_json_from_text`, `_extract_final_classification`, `GitHandler`, `DataHandler`
- Limpar 5 arquivos vazios, mover 9 scripts que não são testes

### Fase 1: Extrair Utilitários (Eliminar Duplicação)
- Consolidar `extract_json_from_text()` (3 cópias → 1 em `json_parser.py`)
- Criar `classification.py`, `failure_logger.py`, `llm_sizing.py`
- Redução líquida: ~163 linhas

### Fase 2: Dataclass de Configuração
- `RefanSettings` centraliza 21 magic values (7 conflitos resolvidos entre handlers)
- 26 substituições em 4 arquivos

### Fase 3: Fundir os Dois LLM Handlers
- 1.746 linhas (660 + 1.086) → ~600 linhas unificadas
- Corrigir bug `_call_ollama()` (linha 764, método inexistente)
- Fundir 2 funções `process_commits` em `main.py`

### Fase 4: Error Handling e Logging
- Corrigir 6 bare `except:` e 13 `os.chdir()` (→ `subprocess.run(cwd=)`)
- Introduzir `logging_config.py`

### Fase 5: Padronizar Modelo de Dados
- `CommitPair` e `AnalysisResult` dataclasses (canônicos)
- Camada de adaptação `adapters.py` para CSV legado
- **PREREQUISITO para Fase 11** (schema Supabase espelha essas dataclasses)

### Fase 6: Persistência Incremental
- CSV full-rewrite → JSONL append-only por sessão
- `SessionWriter` classe com `append()` e `merge_to_csv()`
- **PREREQUISITO para Fase 11** (JSONL = buffer offline para sync com Supabase)

### Fase 7: Interface CLI
- `refan analyze`, `refan status`, `refan compare`, `refan merge-sessions`
- **PREREQUISITO para Fase 11** (runner precisa ser headless/scriptável)

### Fases 8-10: Scripts, Colors, Docs
- Consolidar 20 scripts → estrutura organizada
- Eliminar `from colors import *` (9 módulos)
- Documentação e `pyproject.toml` completo

---

## Parte II: Infraestrutura Distribuída (Fases 11-12)

### Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    SUPABASE CLOUD                        │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ Postgres │  │ Realtime │  │ Auth               │    │
│  │ (dados)  │  │(channels)│  │(email/pw, advisors)│    │
│  └────┬─────┘  └────┬─────┘  └────────────────────┘    │
│       │              │                                   │
│  ┌────┴─────┐  ┌────┴──────────┐                        │
│  │  Views   │  │ RLS Policies  │                        │
│  │(métricas)│  │(runner=write, │                        │
│  └──────────┘  │ dashboard=read│                        │
│                └───────────────┘                        │
└────────┬───────────────┬────────────────────────────────┘
         │               │
    supabase-py      supabase-js
    (service_role)   (anon key + RLS)
         │               │
┌────────┴───────┐  ┌────┴──────────────────┐
│ ANALYSIS RUNNER│  │  FRONTEND DASHBOARD   │
│ (Desktop)      │  │  (Repo separado)      │
│                │  │                       │
│ Python + Ollama│  │ React + TS + Shadcn   │
│ RTX 4070 Ti    │  │ Vercel/Netlify        │
│ Ubuntu         │  │                       │
└────────────────┘  └───────────────────────┘
                          ↑
                    ┌─────┴──────┐
                    │  MacBook   │
                    │  (browser) │
                    └────────────┘
```

**Fluxos de comunicação:**
- **Dados**: Runner → `supabase-py` INSERT → Postgres → Realtime → Dashboard
- **Controle**: Dashboard INSERT → `command_queue` → Runner poll (5s) → executa
- **Heartbeat**: Runner UPSERT → `runner_status` → Realtime → Dashboard (progress bar)

---

### Fase 11: Integração Supabase

**Depende de**: Fases 5 (data models), 6 (persistence), 7 (CLI)

#### 11.1 Setup do projeto Supabase e schema

**Criar projeto Supabase** e aplicar migrations:

```sql
-- Tabela de commits (dataset base, carregado uma vez do CSV)
CREATE TABLE commits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    commit_hash_current TEXT NOT NULL,
    commit_hash_before TEXT NOT NULL,
    repository_url TEXT NOT NULL,
    project_name TEXT NOT NULL,
    purity_analysis TEXT,             -- TRUE/FALSE/NONE do PurityChecker
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(commit_hash_current)
);
CREATE INDEX idx_commits_purity ON commits(purity_analysis);
CREATE INDEX idx_commits_project ON commits(project_name);

-- Modelos LLM registrados
CREATE TABLE llm_models (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,        -- "mistral", "deepseek-r1:8b"
    safe_name TEXT NOT NULL,
    family TEXT,                       -- "mistral", "deepseek", "gemma"
    parameter_count TEXT,              -- "7B", "8B"
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Versões de prompt (reprodutibilidade acadêmica)
CREATE TABLE prompt_versions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    version_tag TEXT NOT NULL UNIQUE,  -- "v1.0-tcc", "v2.0-mestrado"
    system_prompt TEXT NOT NULL,
    classification_criteria TEXT,
    description TEXT,
    sha256_hash TEXT NOT NULL,         -- integridade do prompt
    created_at TIMESTAMPTZ DEFAULT now()
);

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
    config_snapshot JSONB NOT NULL,    -- RefanSettings.to_dict()
    total_planned INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_skipped INTEGER DEFAULT 0,
    purity_filter TEXT,
    error_message TEXT
);

-- Resultados de análise (1 row por commit × modelo × sessão)
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

-- Falhas (substitui json_failures.json)
CREATE TABLE analysis_failures (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID REFERENCES analysis_sessions(id),
    commit_id UUID REFERENCES commits(id),
    model_id UUID NOT NULL REFERENCES llm_models(id),
    error_type TEXT NOT NULL,          -- 'json_parse','timeout','ollama_error','git_error'
    error_message TEXT,
    llm_raw_response TEXT,
    prompt_excerpt TEXT,
    occurred_at TIMESTAMPTZ DEFAULT now()
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

-- Status do runner (heartbeat, 1 row por máquina)
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
```

**Views para métricas:**

```sql
-- Comparação cross-model
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

-- Métricas por modelo (materialized para performance)
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
```

**RLS Policies:**
```sql
-- Runner usa service_role key (bypass RLS) — seguro pois é processo backend
-- Dashboard usa anon key com RLS
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_queue ENABLE ROW LEVEL SECURITY;

-- Leitura para todos autenticados
CREATE POLICY "read_all" ON analysis_results FOR SELECT TO authenticated USING (true);
CREATE POLICY "read_all" ON command_queue FOR SELECT TO authenticated USING (true);

-- Escrita em command_queue para dashboard
CREATE POLICY "insert_commands" ON command_queue FOR INSERT TO authenticated WITH CHECK (true);
```

**Seed de dados existentes:**
- `commits` ← `csv/commits_with_refactoring.csv` (11.186 rows)
- `purity_checker_results` ← `csv/puritychecker_detailed_classification.csv` (~49.000 rows)
- `llm_models` ← 8 modelos já testados (mistral, deepseek-r1:1.5b/8b, gemma2:2b, gemma3:1b/4b, gpt-oss:20b)
- `prompt_versions` ← `OPTIMIZED_LLM_PROMPT` atual + `LLM_PROMPT` original
- `analysis_results` ← backfill dos CSVs em `csv/llm_analysis_csv/` (resultados existentes do TCC)

#### 11.2 Módulo Python Supabase Client

Novo arquivo `src/persistence/supabase_client.py`:

```python
"""Cliente Supabase para persistência cloud."""
from supabase import create_client
from src.models.commit import CommitPair, AnalysisResult

class SupabaseClient:
    def __init__(self, url: str, service_key: str):
        self.client = create_client(url, service_key)
    
    def upsert_commit(self, commit: CommitPair) -> str:
        """Insert ou get commit, retorna UUID."""
    
    def start_session(self, model_id, prompt_version_id, config) -> str:
        """Cria analysis_session, retorna UUID."""
    
    def record_result(self, session_id, commit_id, result: AnalysisResult):
        """INSERT em analysis_results + UPDATE counters da sessão."""
    
    def record_failure(self, session_id, commit_id, error_type, msg, raw_response):
        """INSERT em analysis_failures."""
    
    def update_heartbeat(self, runner_id, session_id, current_commit, index, total):
        """UPSERT runner_status."""
    
    def poll_commands(self, runner_id) -> list[dict]:
        """SELECT pending, marcar acknowledged."""
    
    def sync_local_queue(self, jsonl_path: str):
        """Bulk-upload de JSONL local (recovery offline)."""
```

**Integração no loop de análise** (`llm_purity_analyzer.py`):

```python
# Loop existente (pós-Fase 6):
for commit in commits:
    result = self._analyze_single_commit(commit)
    self.session_writer.append(result)      # local JSONL (Fase 6)
    self.supabase.record_result(...)        # cloud (Fase 11) — NEW
    self.supabase.update_heartbeat(...)     # heartbeat — NEW
    commands = self.supabase.poll_commands() # controle remoto — NEW
    self._handle_commands(commands)          # pause/skip/etc — NEW
```

Se Supabase falha (rede), o JSONL local captura o resultado. Na reconexão, `sync_local_queue()` sincroniza.

#### 11.3 Runner heartbeat e command handler

Novo arquivo `src/runner/command_handler.py`:

```python
class CommandHandler:
    def poll_and_execute(self) -> list[str]:
        commands = self.supabase.poll_commands(self.runner_id)
        for cmd in commands:
            match cmd['command']:
                case 'pause':   self.state = 'paused'  # bloqueia até resume
                case 'resume':  self.state = 'running'
                case 'cancel':  raise AnalysisCancelled()
                case 'skip_commit':
                    self.skip_list.add(cmd['payload']['commit_hash'])
                case 'reanalyze_commit':
                    self.reanalyze_queue.append(cmd['payload']['commit_hash'])
                case 'change_model':
                    self._switch_model(cmd['payload']['model_name'])
            self.supabase.mark_command_completed(cmd['id'])
```

Polling a cada 5 segundos entre commits. Comandos levam no máximo 5s + tempo do commit atual para serem processados.

#### 11.4 Config e .env

Adicionar a `RefanSettings` (Fase 2):
```python
# Supabase
supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
supabase_service_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", ""))
runner_id: str = field(default_factory=lambda: os.environ.get("REFAN_RUNNER_ID", socket.gethostname()))
```

`.env` (não trackear no Git):
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
REFAN_RUNNER_ID=desktop-rtx4070
REFAN_LLM_MODEL=mistral
```

**Novas dependências**: `supabase>=2.0`, `python-dotenv`

#### 11.5 Setup Ubuntu no Desktop

**Recomendação: Ubuntu nativo (não WSL2)**

Justificativa:
- Acesso direto à GPU sem camada de virtualização WSL2
- WSL2 não devolve memória alocada; com 32GB e modelos grandes, memória é crítica
- Sessões longas (horas/dias) são mais estáveis em bare metal
- Docker (se necessário futuramente) é nativo no Linux

Script de setup:
```bash
# Ubuntu 22.04/24.04
sudo apt update && sudo apt install -y git python3.12 python3.12-venv nvidia-driver-560

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral
ollama pull deepseek-r1:8b
ollama pull gemma3:4b

# Projeto
git clone <repo-url> refan && cd refan
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Config
cp .env.example .env  # editar com keys do Supabase
```

**Reprodutibilidade** — `config_snapshot` em cada sessão:
```json
{
    "ollama_version": "0.3.x",
    "model_digest": "sha256:abc...",
    "python_version": "3.12.x",
    "gpu": "RTX 4070 Ti Super 16GB",
    "driver_version": "560.xx",
    "refan_settings": { ... }
}
```

---

### Fase 12: Frontend Dashboard (Repo Separado)

**Repo**: `refan-dashboard` (separado do `refan`)

**Stack**:
- React 18+ com TypeScript
- Shadcn/UI (Tailwind-based)
- TanStack Query (server state) + Zustand (UI state)
- Supabase Realtime (subscriptions)
- Supabase Auth (login)
- Recharts ou Tremor (gráficos)
- Deploy: Vercel (free tier, auto-deploy)

#### 12.1 Páginas do Dashboard

**1. Live Monitor** (`/`)
- Commit sendo analisado AGORA (hash, repo, progress bar)
- Tempo decorrido, ETA
- Modelo em uso, status do Ollama
- GPU utilization (se disponível)
- Realtime via subscription em `runner_status`

**2. Results Table** (`/results`)
- Tabela paginada de todos os resultados
- Colunas: commit, projeto, Purity, LLM classification, modelo, confiança, timestamp
- **Filtros**: por modelo, por classificação (PURE/FLOSS/FAILED), por purity, por projeto
- Expandir row para ver justification + raw response
- Status visual: verde (PURE), vermelho (FLOSS), cinza (pendente), amarelo (em análise)

**3. Cross-Model Comparison** (`/comparison`)
- Tabela: commit × modelos (cada coluna = 1 modelo)
- Highlight de disagreements (onde modelos discordam)
- Venn diagram de concordância (como no TCC)
- Heatmap de concordância pairwise

**4. Metrics Dashboard** (`/metrics`)
- Agreement rate vs Purity Checker por modelo
- Distribuição PURE/FLOSS por modelo (bar chart)
- Taxa de falhas por modelo
- Tempo médio de processamento por modelo
- Baseado na materialized view `model_metrics`

**5. Session History** (`/sessions`)
- Lista de todas as sessões com stats
- Status, modelo, prompt, duração, success rate
- Link para resultados filtrados

**6. Control Panel** (`/control`)
- Status do runner (idle/running/paused)
- Botões: Pause, Resume, Cancel
- Input: skip commit hash, reanalyze commit
- Select: trocar modelo mid-run
- Escreve em `command_queue`

**7. Settings** (`/settings`)
- Gerenciar prompt versions (visualizar, comparar)
- Ver configuração do runner
- Gerenciar usuários (convidar orientadora)

#### 12.2 Realtime Subscriptions

```typescript
// Live monitor - atualiza a cada heartbeat do runner
supabase.channel('runner').on('postgres_changes', {
  event: 'UPDATE', schema: 'public', table: 'runner_status'
}, (payload) => setRunnerStatus(payload.new)).subscribe();

// Novos resultados - append em tempo real
supabase.channel('results').on('postgres_changes', {
  event: 'INSERT', schema: 'public', table: 'analysis_results'
}, (payload) => addResult(payload.new)).subscribe();

// Status da sessão
supabase.channel('session').on('postgres_changes', {
  event: 'UPDATE', schema: 'public', table: 'analysis_sessions'
}, (payload) => setSession(payload.new)).subscribe();
```

#### 12.3 Auth

- Supabase Auth com email/password
- Criar contas para: Marinho (admin), orientadora Melina, colaboradores
- RLS garante que todos autenticados podem ler, mas só o runner (service_role) escreve resultados

---

## Grafo de Dependências Atualizado

```
Fase 0 (Testes)
  ↓
Fase 1 (De-duplicar)
  ↓
Fase 2 (Settings) ──────────────────────────────┐
  ↓                                              │
Fase 3 (Merge handlers)                         │
  ↓                                              │
Fase 4 (Error handling) ←── paralela com 3       │
  ↓                                              │
Fase 5 (Data models) ───────────────────────┐    │
  ↓                                         │    │
Fase 6 (Persistência JSONL) ───────────┐    │    │
  ↓                                    │    │    │
Fase 7 (CLI) ─────────────────────┐    │    │    │
  ↓                               │    │    │    │
Fase 8 (Scripts)                  │    │    │    │
  ↓                               │    │    │    │
Fase 9 (Colors)                   │    │    │    │
  ↓                               │    │    │    │
Fase 10 (Docs)                    │    │    │    │
                                  │    │    │    │
                                  ▼    ▼    ▼    ▼
                            ┌─────────────────────────┐
                            │  Fase 11: Supabase      │
                            │  (depende de 2,5,6,7)   │
                            └────────────┬────────────┘
                                         │
                                         ▼
                            ┌─────────────────────────┐
                            │  Fase 12: Frontend      │
                            │  (depende de 11)        │
                            │  (repo separado)        │
                            └─────────────────────────┘
```

**Paralelização**: A Fase 12 (frontend) pode começar em paralelo com a Fase 11 assim que o schema Supabase estiver definido (11.1). O frontend pode ser desenvolvido com dados mockados enquanto o runner é integrado.

---

## O Que Você Pode Fazer no MacBook

Com esta arquitetura, do MacBook você poderá:

1. **Monitorar em tempo real** — ver qual commit está sendo analisado, progress bar, ETA
2. **Revisar resultados** — filtrar, buscar, comparar modelos, ver justificativas
3. **Controlar o desktop** — pausar, retomar, cancelar, pular commits, trocar modelo
4. **Compartilhar com a orientadora** — ela acessa o mesmo dashboard com login próprio
5. **Desenvolver o frontend** — React + TS no MacBook enquanto o desktop roda análises
6. **Rodar análises locais menores** — o MacBook M4 Pro pode rodar modelos menores via Ollama para testes rápidos
7. **Consultar dados via Supabase Studio** — SQL direto no browser para queries ad-hoc
8. **Gerar relatórios** — exportar dados do Supabase para scripts de análise no MacBook
9. **Versionamento de prompts** — criar e comparar variações de prompt pelo dashboard
10. **Análise de falhas** — investigar por que certos commits falharam, ver raw responses

---

## Verificação End-to-End

Para validar que tudo funciona integrado:

1. **Runner**: `python refan.py analyze --model mistral --limit 5 --skip-analyzed` → 5 commits analisados, resultados em Supabase
2. **Dashboard**: abrir no browser → ver os 5 resultados aparecerem em tempo real
3. **Controle**: clicar "Pause" no dashboard → runner pausa em <30s → clicar "Resume" → continua
4. **Offline**: desconectar internet do desktop → analisar 3 commits → reconectar → sync automático
5. **Orientadora**: login com conta dela → vê os mesmos dados, sem permissão de escrita em resultados
6. **Comparação**: filtrar por 2 modelos → ver concordância/discordância lado a lado
