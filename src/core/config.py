"""
Arquivo de configurações para a aplicação de análise de commits de refatoramento.
Contém constantes e definições utilizadas ao longo da aplicação.
"""

import os
from pathlib import Path
import subprocess
import json as _json
import requests

# Diretório raiz do projeto (volta 2 níveis de src/core/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Caminhos para diretórios de dados
CSV_PATH = PROJECT_ROOT / "csv" / "commits_with_refactoring.csv"
PURITY_CSV_PATH = PROJECT_ROOT / "csv" / "puritychecker_detailed_classification.csv"
REPO_DIR = PROJECT_ROOT / "repositorios"

"""Configurações dinâmicas do modelo LLM.

Agora suportamos múltiplos modelos (ex: mistral, gpt-oss-20b) rodando no Ollama.
O modelo ativo pode ser alterado em tempo de execução via função set_llm_model().
Cada modelo possui seus próprios diretórios de saída isolados em output/models/<modelo>/.
"""

# Endpoint padrão da API do Ollama (/api/generate)
LLM_HOST = "http://localhost:11434/api/generate"

# Modelo padrão inicial (pode ser sobrescrito via set_llm_model)
_CURRENT_LLM_MODEL = os.environ.get("REFAN_LLM_MODEL", "mistral")
# Alias legado para compatibilidade com código que importava LLM_MODEL diretamente
LLM_MODEL = _CURRENT_LLM_MODEL

def get_current_llm_model() -> str:
    """Retorna o nome do modelo LLM atualmente selecionado."""
    return _CURRENT_LLM_MODEL

def set_llm_model(model_name: str):
    """Define o modelo LLM atual e recria constantes/diretórios dinâmicos.
    
    Args:
        model_name: Nome do modelo conforme registrado no Ollama (ex: 'mistral', 'gpt-oss:20b')
    """
    global _CURRENT_LLM_MODEL, LLM_MODEL, MODEL_PATHS, ANALISES_DIR, ANALYZED_COMMITS_LOG, DASHBOARDS_DIR, COMPARISONS_DIR, PURITY_COMPARISON_DIR
    if not model_name or not isinstance(model_name, str):
        raise ValueError("Nome de modelo inválido")
    _CURRENT_LLM_MODEL = model_name
    LLM_MODEL = model_name  # manter alias legado sincronizado
    # Recalcular caminhos
    MODEL_PATHS = get_model_paths(model_name)
    ANALISES_DIR = str(MODEL_PATHS["ANALISES_DIR"])
    ANALYZED_COMMITS_LOG = str(MODEL_PATHS["ANALYZED_COMMITS_LOG"])
    DASHBOARDS_DIR = str(MODEL_PATHS["DASHBOARDS_DIR"])
    COMPARISONS_DIR = str(MODEL_PATHS["COMPARISONS_DIR"])
    PURITY_COMPARISON_DIR = str(MODEL_PATHS["COMPARISONS_DIR"])

def list_available_ollama_models() -> list:
    """Lista modelos disponíveis no Ollama via comando 'ollama list'.
    Retorna lista de nomes simples (coluna NAME). Se falhar, retorna apenas o modelo atual.
    """
    try:
        import subprocess, json as _json
        # Usa formato JSON para facilitar parsing (se suportado). Caso contrário, fallback para texto.
        proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            return [get_current_llm_model()]
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        # Ignorar cabeçalho se existir
        models = []
        for line in lines:
            if line.lower().startswith("name") and "size" in line.lower():
                continue
            # Formato esperado: NAME  ID  SIZE  MODIFIED
            parts = line.split()
            if parts:
                models.append(parts[0])
        # Garantir unicidade
        models = list(dict.fromkeys(models))
        return models or [get_current_llm_model()]
    except Exception:
        return [get_current_llm_model()]

# Caminhos dinâmicos baseados no modelo atual
def get_model_paths(model_name: str | None = None):
    """Retorna caminhos específicos para o modelo LLM.

    Args:
        model_name: Nome do modelo; se None usa o modelo atual.
    """
    if model_name is None:
        model_name = get_current_llm_model()

    # Sanitizar nome para uso em diretório (substituir ':' por '_')
    safe_model_name = model_name.replace(':', '_')

    model_dir = PROJECT_ROOT / "output" / "models" / safe_model_name

    return {
        "MODEL_NAME": model_name,
        "SAFE_MODEL_NAME": safe_model_name,
        "MODEL_ROOT": model_dir,
        "ANALISES_DIR": model_dir / "analises",
        "ANALYZED_COMMITS_LOG": model_dir / "analises" / "analyzed_commits.json",
        "DASHBOARDS_DIR": model_dir / "dashboards",
        "COMPARISONS_DIR": model_dir / "comparisons",
        "COMPLETE_ANALYSES_DIR": model_dir / "analises_completas"
    }

###############################################
# Inicialização de caminhos para o modelo atual
###############################################
MODEL_PATHS = get_model_paths(_CURRENT_LLM_MODEL)
ANALISES_DIR = str(MODEL_PATHS["ANALISES_DIR"])
ANALYZED_COMMITS_LOG = str(MODEL_PATHS["ANALYZED_COMMITS_LOG"])
DASHBOARDS_DIR = str(MODEL_PATHS["DASHBOARDS_DIR"])
COMPARISONS_DIR = str(MODEL_PATHS["COMPARISONS_DIR"])

# Diretórios temporários
TEMP_DIR = PROJECT_ROOT / "output" / "temp"
PURITY_COMPARISON_DIR = str(MODEL_PATHS["COMPARISONS_DIR"])

# Configurações de depuração
DEBUG_SHOW_PROMPT = True       # Se True, mostra o prompt enviado ao modelo
DEBUG_MAX_PROMPT_LENGTH = 2000  # Tamanho máximo do prompt a ser exibido

# Configurações de sessão do modelo
RESET_MODEL_CONTEXT = True     # Se True, limpa o contexto do modelo antes de cada análise
USE_RANDOM_SEED = True         # Se True, usa um seed aleatório para cada solicitação

# -------------------------------------------------
# Configuração opcional de camadas na GPU (Ollama)
# -------------------------------------------------
# Por padrão o Ollama decide quantas camadas vão para a GPU (heurística baseada em VRAM) e
# imprime no comando runner: --n-gpu-layers <N>. Observamos uso elevado de CPU pois apenas
# parte pequena das camadas do modelo 20B foi alocada na GPU (ex: 21 camadas), o restante
# roda na CPU. Para forçar mais camadas na GPU (se houver VRAM disponível) defina a variável
# de ambiente REFAN_NUM_GPU_LAYERS antes de executar a aplicação. Ex:
#   export REFAN_NUM_GPU_LAYERS=60
# IMPORTANTE: Aumentar demais pode causar OOM (out of memory) e o modelo falhar ao carregar.
NUM_GPU_LAYERS_ENV = os.environ.get("REFAN_NUM_GPU_LAYERS")
try:
    NUM_GPU_LAYERS = int(NUM_GPU_LAYERS_ENV) if NUM_GPU_LAYERS_ENV else None
except ValueError:
    NUM_GPU_LAYERS = None

def get_generation_base_options():
    """Retorna opções padrão adicionais para geração no Ollama.

    Inclui num_gpu_layers caso o usuário tenha configurado REFAN_NUM_GPU_LAYERS e seja > 0.
    """
    opts = {}
    if NUM_GPU_LAYERS and NUM_GPU_LAYERS > 0:
        # Nome do campo conforme API do Ollama (num_gpu_layers) para forçar camadas na GPU
        opts["num_gpu_layers"] = NUM_GPU_LAYERS
    return opts

# Função para criar diretórios necessários
def create_directories(model_name: str | None = None):
    """Cria todos os diretórios necessários para o modelo informado ou atual."""
    paths = get_model_paths(model_name)
    for key, path in paths.items():
        if isinstance(path, Path):
            if key == "ANALYZED_COMMITS_LOG":
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                path.mkdir(parents=True, exist_ok=True)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    REPO_DIR.mkdir(parents=True, exist_ok=True)

def ensure_model_directories():
    """Garante que os diretórios do modelo atual existem (idempotente)."""
    create_directories(get_current_llm_model())

# -------------------------------------------------
# Health check do modelo para evitar travamentos
# -------------------------------------------------
def check_llm_model_status(model: str | None = None, host: str | None = None, verbose: bool = True) -> dict:
    """Verifica se o modelo está disponível e responde a uma prompt simples.

    Returns dict com campos:
        available: bool
        pulled: bool (aparece em ollama list)
        test_generation: bool (conseguiu gerar)
        error: mensagem de erro se houver
    """
    from src.utils.colors import info, warning, error, success, dim
    model = model or get_current_llm_model()
    host = host or LLM_HOST
    result = {"model": model, "available": False, "pulled": False, "test_generation": False, "error": None}
    try:
        # 1. Conferir se aparece no 'ollama list'
        try:
            proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                lines = [l.split()[0] for l in proc.stdout.splitlines() if l.strip() and not l.lower().startswith("name")]
                if model in lines:
                    result["pulled"] = True
                else:
                    # Alguns modelos têm sufixos (ex: :latest). Tentar correspondência flexível
                    base = model.split(":")[0]
                    if any(l.startswith(base) for l in lines):
                        result["pulled"] = True
            else:
                result["error"] = f"falha ao listar modelos: {proc.stderr.strip()}"
        except Exception as e:
            result["error"] = f"erro executando ollama list: {e}"

        if not result["pulled"]:
            if verbose:
                print(warning(f"Modelo '{model}' não encontrado no Ollama. Execute: ollama pull {model}"))
            return result

        # 2. Testar geração curta
        payload = {"model": model, "prompt": "Say OK", "stream": False}
        try:
            resp = requests.post(host, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                txt = data.get("response", "")
                if txt:
                    result["test_generation"] = True
                    result["available"] = True
            else:
                result["error"] = f"status {resp.status_code}: {resp.text[:120]}"
        except requests.exceptions.Timeout:
            result["error"] = "timeout na geração de teste (modelo pode estar carregando)"
        except Exception as e:
            result["error"] = f"erro na requisição de teste: {e}"

        if verbose:
            if result["available"]:
                print(success(f"Modelo '{model}' verificado com sucesso."))
            else:
                print(warning(f"Modelo '{model}' não respondeu adequadamente: {result['error']}"))
        return result
    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(error(f"Falha no health check: {e}"))
        return result

# Prompt para o LLM
LLM_PROMPT = """You are a software engineering expert in charge of analyzing Git commits and identifying the type of refactoring they represent.

There are two types of refactoring to consider:

1. Pure refactoring: This is used strictly for improving the source code structure. It consists of pure refactoring, with no changes to the behavior or features of the code.
   - Must have absolutely NO functional changes or bug fixes
   - Focuses ONLY on improving code structure, readability, or maintainability   

2. Floss refactoring: This consists of refactoring the code alongside non-structural changes such as adding new features, fixing bugs, or modifying functionality. It blends refactoring with other goals.
   - Includes ANY combination of refactoring with bug fixes or feature changes
   - Even minor bug fixes alongside refactoring make it "floss"   

IMPORTANT: Your task is to examine the Git diff ONLY (ignore the commit message) and classify the type of refactoring it represents based solely on the code changes.

Focus exclusively on the actual code changes in the diff to determine if there are any behavioral modifications or purely structural changes. Base your decision ONLY on what you see in the code.

IMPORTANT OUTPUT FORMAT:
1. First, provide your analysis and reasoning
2. End with a clear line: FINAL: PURE or FINAL: FLOSS
3. Then provide the complete JSON with your classification

Please classify the commit as either "pure" or "floss" and explain your reasoning in the justification field of the JSON, citing specific parts of the code diff that support your classification.

Ensure your response contains both the clear "FINAL: [PURE|FLOSS]" line and the complete JSON structure."""

# Estrutura do JSON de saída
JSON_STRUCTURE = {
    "repository": "",
    "commit_hash_before": "",
    "commit_hash_current": "",
    "commit_message": "",
    "refactoring_type": "",
    "justification": ""
}
