"""
Prompt otimizado para análise de refatoramento baseado nos padrões identificados
no Purity Checker, com suporte a arquivos para diffs grandes.

Desde a Fase E3 (EVOLUTION_PLAN.md, REP-5), o template do sistema é CARREGADO
do artefato versionado ``configs/prompts/v2.0-mestrado.txt`` — o arquivo
citável com SHA-256 registrado em docs/PROMPTS.md é a fonte única; a constante
``OPTIMIZED_LLM_PROMPT`` é apenas a leitura dele. A sincronia é garantida por
tests/test_prompt_artifacts.py (hash do arquivo == hash registrado).
"""

import os
from pathlib import Path
from typing import Optional, Tuple

from src.core.settings import settings as _settings

_PROMPT_ARTIFACT = (
    Path(__file__).resolve().parents[2] / "configs" / "prompts" / "v2.0-mestrado.txt"
)


def _load_prompt_artifact() -> str:
    """Lê o artefato verbatim do prompt; falha alto se ausente.

    Um prompt ausente/alterado invalidaria a proveniência de toda a sessão —
    não há fallback silencioso por decisão de projeto (VAL-4/REP-5).
    """
    try:
        return _PROMPT_ARTIFACT.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Artefato de prompt não encontrado: {_PROMPT_ARTIFACT}. "
            "O repositório está íntegro? (git status / git checkout configs/prompts/)"
        ) from exc

# Alias do limiar centralizado em RefanSettings.max_diff_chars_file:
# diffs acima deste tamanho vão para arquivo temporário em vez de inline
# no prompt. Mantido como nome de módulo por compatibilidade com callers.
MAX_DIRECT_DIFF_SIZE = _settings.max_diff_chars_file
TEMP_DIFF_DIR = "temp_diffs"  # Diretório para arquivos temporários de diff

# Prompt otimizado (v2.0-mestrado) — texto vive no artefato versionado;
# ver docs/PROMPTS.md para hash, racional e limitações registradas.
OPTIMIZED_LLM_PROMPT = _load_prompt_artifact()


def ensure_temp_diff_dir():
    """Garante que o diretório para arquivos temporários existe."""
    if not os.path.exists(TEMP_DIFF_DIR):
        os.makedirs(TEMP_DIFF_DIR)


def save_diff_to_file(diff_content: str, commit_hash: str) -> str:
    """
    Salva o diff em um arquivo temporário.
    
    Args:
        diff_content (str): Conteúdo completo do diff
        commit_hash (str): Hash do commit para nome do arquivo
        
    Returns:
        str: Caminho do arquivo criado
    """
    ensure_temp_diff_dir()
    filename = f"diff_{commit_hash}.txt"
    filepath = os.path.join(TEMP_DIFF_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(diff_content)
    except UnicodeEncodeError:
        # Tentar com encoding alternativo se UTF-8 falhar
        try:
            with open(filepath, 'w', encoding='latin-1') as f:
                f.write(diff_content)
        except UnicodeEncodeError:
            # Como último recurso, salvar com errors='replace'
            with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                f.write(diff_content)
            print(f"Aviso: Alguns caracteres especiais foram substituídos no arquivo {filepath}")
    
    return filepath


def should_use_file_approach(diff_content: str) -> bool:
    """
    Determina se o diff deve ser salvo em arquivo devido ao tamanho.
    
    Args:
        diff_content (str): Conteúdo do diff
        
    Returns:
        bool: True se deve usar arquivo, False para envio direto
    """
    return len(diff_content) > MAX_DIRECT_DIFF_SIZE


def build_optimized_commit_prompt_with_file_support(commit_data: dict, system_prompt: str) -> Tuple[str, Optional[str]]:
    """
    Constrói um prompt otimizado, usando arquivo para diffs grandes.
    
    Args:
        commit_data (dict): Dados do commit incluindo diff
        system_prompt (str): Prompt base do sistema
        
    Returns:
        Tuple[str, Optional[str]]: (prompt_completo, caminho_arquivo_diff_ou_None)
    """
    repository = commit_data.get("repository", "")
    commit1 = commit_data.get("commit_hash_before", "")
    commit2 = commit_data.get("commit_hash_current", "")
    diff = commit_data.get("diff", "")
    
    # Estatísticas do diff
    diff_lines = len(diff.splitlines()) if diff else 0
    diff_size = len(diff)
    
    # Decidir se usar arquivo ou envio direto
    use_file = should_use_file_approach(diff)
    diff_file_path = None
    
    if use_file and diff:
        # Salvar diff em arquivo
        diff_file_path = save_diff_to_file(diff, commit2)
        
        context = f"""
Repository: {repository}
Commit Hash (Before): {commit1}
Commit Hash (Current): {commit2}

Diff Statistics:
- Size: {diff_size} characters ({diff_lines} lines)
- Approach: FILE-BASED (diff saved to temporary file due to size)
- File Path: {diff_file_path}

IMPORTANT: The complete diff has been saved to the file above. Please read and analyze the ENTIRE diff file content to make your classification. Do not make assumptions based on partial content.

Code Diff File Content:
[The complete diff is available in the file: {diff_file_path}]

Instructions:
1. Read the COMPLETE diff file content
2. Analyze ALL changes for behavioral vs structural modifications
3. Base your classification on the FULL diff content
4. Use the technical indicators specified in the instructions
5. Provide brief analysis, then FINAL: PURE or FINAL: FLOSS, then JSON with "diff_source": "file"

Analyze the complete diff and provide your classification."""
    else:
        # Envio direto no prompt
        context = f"""
Repository: {repository}
Commit Hash (Before): {commit1}
Commit Hash (Current): {commit2}

Diff Statistics:
- Size: {diff_size} characters ({diff_lines} lines)
- Approach: DIRECT (diff included in prompt)

Code Diff:
{diff}

Instructions:
1. Analyze ALL changes shown in the diff above
2. Look for behavioral vs structural modifications
3. Use the technical indicators specified in the instructions
4. Provide brief analysis, then FINAL: PURE or FINAL: FLOSS, then JSON with "diff_source": "direct"

Analyze this diff and provide your classification."""
    
    full_prompt = f"{system_prompt}\n\n{context}"
    return full_prompt, diff_file_path


def cleanup_temp_diff_file(file_path: str):
    """
    Remove arquivo temporário de diff.
    
    Args:
        file_path (str): Caminho do arquivo a ser removido
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Aviso: Não foi possível remover arquivo temporário {file_path}: {e}")


# Configurações para o handler otimizado
OPTIMIZED_CONFIG = {
    "max_direct_diff_size": MAX_DIRECT_DIFF_SIZE,
    "use_file_for_large_diffs": True,
    "temp_diff_dir": TEMP_DIFF_DIR,
    "focus_on_method_signatures": True,
    "prioritize_behavioral_changes": True,
    "conservative_classification": True  # Quando em dúvida, classificar como FLOSS
}
