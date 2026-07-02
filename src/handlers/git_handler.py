"""Módulo para encapsular operações Git: clonar, verificar commits e obter diffs.

Refatorado na Fase 4: substitui os.chdir() por subprocess.run(cwd=)
para thread-safety e simplicidade.

Refs: REFACTORING_PLAN.md Phase 4
"""

import os
import subprocess
from src.core.config import REPO_DIR
from src.utils.colors import error, info, progress, success, warning


class GitHandler:
    def __init__(self):
        """Inicializa o manipulador Git."""
        self._ensure_repo_dir_exists()

    def _ensure_repo_dir_exists(self):
        """Garante que o diretório de repositórios existe."""
        if not os.path.exists(REPO_DIR):
            os.makedirs(REPO_DIR)
            print(info(f"Diretório {REPO_DIR} criado."))

    def _get_repo_local_path(self, repo_url):
        """Obtém o caminho local para um repositório baseado na URL."""
        repo_name = repo_url.strip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        return os.path.join(REPO_DIR, repo_name)

    def ensure_repo_cloned(self, repo_url):
        """Verifica se o repositório já foi clonado e o clona se necessário.

        Returns:
            tuple: (bool, str) - Sucesso e caminho local ou mensagem de erro.
        """
        repo_path = self._get_repo_local_path(repo_url)

        try:
            if os.path.exists(repo_path):
                print(progress(f"Repositório {repo_url} já existe localmente. Atualizando..."))
                subprocess.run(
                    ["git", "fetch", "--all"],
                    cwd=repo_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                print(success(f"Repositório {repo_url} atualizado com sucesso."))
                return True, repo_path
            else:
                print(progress(f"Clonando repositório {repo_url}..."))
                subprocess.run(
                    ["git", "clone", repo_url, repo_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                print(success(f"Repositório {repo_url} clonado com sucesso."))
                return True, repo_path

        except subprocess.CalledProcessError as e:
            error_msg = f"Erro ao clonar/atualizar o repositório {repo_url}: {e.stderr}"
            print(error(error_msg))
            return False, error_msg
        except Exception as e:
            error_msg = f"Erro ao processar repositório {repo_url}: {str(e)}"
            print(error(error_msg))
            return False, error_msg

    def commit_exists(self, repo_path, commit_hash):
        """Verifica se um commit específico existe no repositório."""
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            print(error(f"Erro ao verificar commit {commit_hash}: {str(e)}"))
            return False

    def get_commit_diff(self, repo_path, commit1, commit2):
        """Obtém o diff entre dois commits.

        Returns:
            str: O diff entre os dois commits ou None em caso de erro.
        """
        try:
            result = subprocess.run(
                ["git", "diff", commit1, commit2],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            # Tentar decodificar com diferentes encodings
            try:
                return result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return result.stdout.decode('latin-1')
                except UnicodeDecodeError:
                    try:
                        return result.stdout.decode('cp1252')
                    except UnicodeDecodeError:
                        decoded = result.stdout.decode('utf-8', errors='replace')
                        print(warning("Aviso: Alguns caracteres especiais foram substituídos no diff devido a problemas de encoding."))
                        return decoded

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)
            print(error(f"Erro ao obter diff entre {commit1} e {commit2}: {error_msg}"))
            return None
        except Exception as e:
            print(error(f"Erro ao processar diff entre {commit1} e {commit2}: {str(e)}"))
            return None

    def get_commit_message(self, repo_path, commit_hash):
        """Obtém a mensagem completa de um commit.

        Returns:
            str: A mensagem do commit ou None em caso de erro.
        """
        try:
            result = subprocess.run(
                ["git", "log", "--format=%B", "-n", "1", commit_hash],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(error(f"Erro ao obter mensagem do commit {commit_hash}: {e.stderr}"))
            return None
        except Exception as e:
            print(error(f"Erro ao processar mensagem do commit {commit_hash}: {str(e)}"))
            return None
