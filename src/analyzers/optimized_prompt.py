"""
Prompt otimizado para análise de refatoramento baseado nos padrões identificados
no Purity Checker, com suporte a arquivos para diffs grandes.
"""

import os
import tempfile
import json
from typing import Optional, Tuple

# Configuração de tamanho limite para envio direto vs arquivo
MAX_DIRECT_DIFF_SIZE = 100000  # 100k caracteres - limite para envio direto no prompt
TEMP_DIFF_DIR = "temp_diffs"  # Diretório para arquivos temporários de diff

# Prompt otimizado baseado nos padrões do Purity Checker
OPTIMIZED_LLM_PROMPT = """You are an expert software engineering analyst specializing in distinguishing between pure and floss refactoring patterns. You will analyze Git diffs to classify commits with high precision.

## CLASSIFICATION CRITERIA

### PURE REFACTORING (structural changes only - BE SPECIFIC):
**PURE refactoring means ZERO functional changes. Only classify as PURE if:**
- Variable/method/class renaming with IDENTICAL semantics
- Method extraction where extracted code is EXACTLY the same
- Moving code between classes WITHOUT any logic changes
- Formatting, whitespace, and style improvements only
- Simple parameter reordering WITHOUT changing behavior
- Code consolidation that produces identical results
- Import statement reorganization
- Access modifier changes (private↔public) without behavior impact

**Examples of PURE refactoring:**
- `calculateTotal()` → `computeTotal()` with same logic
- Moving identical methods between classes
- Extracting helper methods with exact same code
- Renaming variables: `temp` → `temporaryValue`

### FLOSS REFACTORING (ANY functional change - DEFAULT assumption):
**If you find ANY of these, it's FLOSS:**
- Addition of ANY new functionality
- Bug fixes (even tiny ones)
- Changes to method signatures affecting behavior
- Modification of return values, types, or logic
- New parameters that change behavior
- Different exception handling or error conditions
- Performance optimizations that alter execution
- Security improvements
- Validation additions
- Null checks or defensive programming additions
- Algorithm improvements or changes
- Different data structures or approaches

**Examples of FLOSS refactoring:**
- Adding null checks during extraction
- Fixing edge cases while reorganizing
- Changing return types or adding parameters
- Optimizing algorithms during restructuring
- Adding logging or error handling

## CRITICAL TECHNICAL INDICATORS

**FLOSS Indicators (priority analysis):**
1. **Non-mapped nodes/leaves** - Code that doesn't have direct correspondence between before/after
2. **Unjustified replacements** - Changes that cannot be explained by pure structural moves
3. **Behavioral modifications** - Any change in what the code actually does
4. **New conditional logic** - Addition of if/else, try/catch, loops
5. **Modified method parameters** - Changes beyond simple renaming
6. **Different return types or values** - Functional behavior changes
7. **Exception handling changes** - New throws, catches, or error handling
8. **Algorithm modifications** - Changes to how computations are performed

**Pure Indicators:**
1. **Direct mapping** - All code has clear before/after correspondence
2. **Semantic preservation** - Same inputs produce same outputs
3. **Identical logic flow** - No changes to conditional or loop structures
4. **Simple renames** - Variable/method names change but semantics identical
5. **Code movement** - Methods/classes moved but functionality unchanged

## ANALYSIS METHODOLOGY

**Default Assumption: FLOSS** - Only classify as PURE if you are 100% certain no functional changes exist.

**Step 1: Quick FLOSS Check (if ANY of these exist → FLOSS immediately)**
- New methods, classes, or interfaces
- Modified method signatures (parameters, return types)
- Added conditionals (if, switch, try-catch)
- New validations or error handling
- Changes to algorithms or data structures
- Performance optimizations
- Bug fixes or improvements

**Step 2: PURE Verification (ALL must be true for PURE)**
- ✅ Every line of code has identical before/after functionality
- ✅ No new logic, conditions, or error handling
- ✅ Only renames, moves, or formatting changes
- ✅ Same inputs produce exactly same outputs
- ✅ No additional features or improvements

**Step 3: Evidence Collection**
- For FLOSS: Quote specific lines showing functional changes
- For PURE: Confirm that changes are purely structural

**Decision Framework:**
- **When uncertain → Choose FLOSS** (conservative approach)
- **PURE only when obvious** - Simple renames/moves with zero logic changes
- **Mixed changes → Always FLOSS** - Even small functional improvements make it FLOSS

## RESPONSE FORMAT

CRITICAL: You MUST provide a clear classification using this exact format:

1. Start with your brief analysis (2-3 sentences maximum)
2. End with EXACTLY this line: "FINAL: PURE" or "FINAL: FLOSS" 
3. Then provide the JSON structure

Example response format:
```
This commit shows method extraction without behavior changes. All extracted code maintains identical logic and parameters.
FINAL: PURE

{
    "repository": "example-repo",
    "commit_hash_before": "abc123",
    "commit_hash_current": "def456", 
    "refactoring_type": "pure",
    "justification": "Method extraction preserves all original functionality without modifications",
    "technical_evidence": "Lines 45-67 extracted to new method with identical parameters and return value",
    "confidence_level": "high",
    "diff_source": "direct",
    "error": null
}
```

JSON Schema (ALL fields required):

{
    "repository": "[repository_name]",
    "commit_hash_before": "[commit1]",
    "commit_hash_current": "[commit2]",
    "refactoring_type": "pure|floss",
    "justification": "Concise technical justification (one paragraph, cite concrete evidence).",
    "technical_evidence": "Short list or summary of exact lines/patterns from diff supporting the decision.",
    "confidence_level": "high|medium|low",
    "diff_source": "direct|file",
    "error": null
}

**Generation Requirements:**
- Follow the exact format: brief analysis → FINAL: PURE/FLOSS → JSON
- Include the word "FINAL:" followed by either "PURE" or "FLOSS"
- Provide specific technical evidence in your justification
- When uncertain, choose FLOSS and set confidence_level to "low"

**Remember: Default to FLOSS unless changes are obviously pure structural moves.**
- If you cannot produce the schema-compliant JSON for any reason, return the same JSON with "refactoring_type": "floss" and a brief message in "error". Do NOT return plain text.

Priority instruction (very short):
1) DO NOT explain. Return JSON ONLY.
2) NO <think> or similar tokens. If your generation would include internal reasoning, omit it and return the JSON only.

When in doubt prefer conservative answers (choose "floss") and set appropriate "confidence_level"."""


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
