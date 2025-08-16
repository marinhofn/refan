#!/usr/bin/env python3
"""
Script para corrigir imports em todos os scripts que podem ser executados diretamente
"""

import os
import re
from pathlib import Path

def fix_script_imports(file_path: Path, levels_up: int):
    """Corrige imports em um script específico."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem a correção
        if 'project_root = Path(__file__)' in content:
            print(f"⚪ Já corrigido: {file_path}")
            return False
        
        # Verificar se tem imports src.
        if 'from src.' not in content and 'import src.' not in content:
            print(f"⚪ Sem imports src: {file_path}")
            return False
            
        original_content = content
        
        # Encontrar a linha do shebang e docstring
        lines = content.split('\n')
        insert_position = 0
        
        # Pular shebang
        if lines[0].startswith('#!'):
            insert_position = 1
        
        # Pular docstring
        in_docstring = False
        docstring_quotes = None
        for i in range(insert_position, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            if line.startswith('"""') or line.startswith("'''"):
                if not in_docstring:
                    docstring_quotes = line[:3]
                    in_docstring = True
                    if line.count(docstring_quotes) >= 2:  # docstring em uma linha
                        insert_position = i + 1
                        break
                elif line.endswith(docstring_quotes):
                    in_docstring = False
                    insert_position = i + 1
                    break
            elif not in_docstring:
                insert_position = i
                break
        
        # Criar código de correção
        path_setup = f"""
import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).{'parent.' * levels_up}parent
    sys.path.insert(0, str(project_root))
"""
        
        # Inserir o código antes dos imports
        lines.insert(insert_position, path_setup)
        new_content = '\n'.join(lines)
        
        # Salvar arquivo
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Corrigido: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erro em {file_path}: {e}")
        return False

def main():
    """Corrige todos os scripts."""
    project_root = Path(__file__).parent
    
    # Scripts em scripts/ (2 níveis acima)
    scripts_dir = project_root / "scripts"
    if scripts_dir.exists():
        print("\n🔍 Corrigindo scripts em scripts/...")
        for py_file in scripts_dir.rglob("*.py"):
            if py_file.name != "__init__.py":
                fix_script_imports(py_file, 2)  # scripts/subpasta -> projeto
    
    # Scripts em tests/ (1 nível acima) 
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        print("\n🔍 Corrigindo scripts em tests/...")
        for py_file in tests_dir.rglob("*.py"):
            if py_file.name != "__init__.py":
                fix_script_imports(py_file, 1)  # tests -> projeto
    
    print(f"\n✅ Correção concluída!")

if __name__ == "__main__":
    main()
