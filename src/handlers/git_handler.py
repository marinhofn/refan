"""Módulo para encapsular operações Git: clonar, verificar commits e obter diffs.

Refatorado na Fase 4 (subprocess.run(cwd=) para thread-safety) e endurecido na
Fase E4 (EVOLUTION_PLAN.md, ROB-4):

- **Partial clone** (``--filter=blob:none``): a análise usa apenas o diff
  entre dois commits — blobs são baixados sob demanda pelo próprio git no
  ``diff``; histórico completo de blobs era desperdício de rede/disco.
  Fallback automático para clone completo em servidores sem suporte.
- **Path local ``owner__repo``**: o basename puro colidia (``a/log4j`` e
  ``b/log4j`` compartilhavam diretório → diff do repositório errado).
- **Fetch direcionado e lazy**: o ``git fetch --all`` incondicional a cada
  execução foi removido; o fetch ocorre apenas quando um hash requerido não
  existe localmente (e busca os hashes específicos, com fallback amplo).
- **Validação**: hashes passam por regex antes de qualquer subprocess;
  argumentos externos vêm depois de ``--`` (argument injection); diretório
  de clone corrompido/parcial é detectado (``git rev-parse``) e re-clonado.
- **Limpeza LRU**: ``cleanup_repos`` aplica um orçamento de disco
  (``settings.repo_cache_max_gb``) removendo os repositórios menos
  recentemente usados (exposto como ``refan clean-repos``).
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from src.core.config import REPO_DIR
from src.core.settings import settings as _settings
from src.utils.colors import error, info, progress, success, warning

_HASH_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def is_valid_commit_hash(commit_hash: str) -> bool:
    """Valida o formato de um hash (7-40 hex) antes de usá-lo em subprocess."""
    return bool(commit_hash) and bool(_HASH_RE.match(str(commit_hash)))


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
        """Caminho local ``owner__repo`` (evita colisão de basename — ROB-4).

        ``https://github.com/a/log4j`` e ``https://github.com/b/log4j``
        recebem diretórios distintos; antes compartilhavam ``log4j`` e o
        diff podia sair do repositório errado.
        """
        parts = [p for p in str(repo_url).strip().strip("/").split("/") if p]
        repo_name = parts[-1] if parts else "unknown"
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        owner = parts[-2] if len(parts) >= 2 else ""
        # descartar esquema/host que sobram em URLs curtas (ex.: "github.com")
        if owner and ("." in owner or ":" in owner):
            owner = ""
        local_name = f"{owner}__{repo_name}" if owner else repo_name
        return os.path.join(REPO_DIR, local_name)

    def _is_valid_repo(self, repo_path) -> bool:
        """True se o diretório contém um repositório git são."""
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0

    def _touch_last_used(self, repo_path) -> None:
        """Marca o repositório como recém-usado (base do LRU de limpeza)."""
        try:
            os.utime(repo_path, None)
        except OSError:
            pass

    def ensure_repo_cloned(self, repo_url, required_hashes=None):
        """Garante repositório local são com os commits requeridos presentes.

        Args:
            repo_url: URL do repositório.
            required_hashes: hashes que precisam existir localmente. Quando
                informados e ausentes, dispara fetch direcionado (fallback
                ``fetch --all --tags``). Sem hashes, um repositório existente
                NÃO gera tráfego de rede (o ``fetch --all`` incondicional
                por execução foi removido — ROB-4).

        Returns:
            tuple: (bool, str) — sucesso e caminho local ou mensagem de erro.
        """
        repo_path = self._get_repo_local_path(repo_url)

        try:
            if os.path.exists(repo_path) and not self._is_valid_repo(repo_path):
                # Clone anterior interrompido/corrompido: sem isto, toda
                # execução futura cairia no ramo "já existe" e falharia.
                print(warning(f"Repositório corrompido/parcial em {repo_path} — re-clonando."))
                shutil.rmtree(repo_path, ignore_errors=True)

            if not os.path.exists(repo_path):
                print(progress(f"Clonando repositório {repo_url}..."))
                if not self._clone(repo_url, repo_path):
                    error_msg = f"Erro ao clonar o repositório {repo_url}"
                    return False, error_msg
                print(success(f"Repositório {repo_url} clonado com sucesso."))

            if required_hashes:
                missing = [
                    h for h in required_hashes
                    if is_valid_commit_hash(h) and not self.commit_exists(repo_path, h)
                ]
                if missing and not self._fetch_missing(repo_path, missing):
                    error_msg = (
                        f"Commits {', '.join(h[:8] for h in missing)} indisponíveis "
                        f"em {repo_url} mesmo após fetch"
                    )
                    print(error(error_msg))
                    return False, error_msg

            self._touch_last_used(repo_path)
            return True, repo_path

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
            error_msg = f"Erro ao clonar/atualizar o repositório {repo_url}: {stderr}"
            print(error(error_msg))
            return False, error_msg
        except Exception as e:
            error_msg = f"Erro ao processar repositório {repo_url}: {str(e)}"
            print(error(error_msg))
            return False, error_msg

    def _clone(self, repo_url, repo_path) -> bool:
        """Clona com partial clone; fallback para clone completo."""
        partial = subprocess.run(
            ["git", "clone", "--filter=blob:none", "--", repo_url, repo_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if partial.returncode == 0:
            return True
        print(warning(
            "Partial clone não suportado pelo servidor — usando clone completo."
        ))
        shutil.rmtree(repo_path, ignore_errors=True)
        full = subprocess.run(
            ["git", "clone", "--", repo_url, repo_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if full.returncode != 0:
            print(error(f"Clone falhou: {full.stderr.strip()[:300]}"))
            shutil.rmtree(repo_path, ignore_errors=True)
            return False
        return True

    def _fetch_missing(self, repo_path, missing_hashes) -> bool:
        """Fetch direcionado dos hashes ausentes; fallback amplo."""
        print(progress(f"Buscando {len(missing_hashes)} commit(s) ausente(s)..."))
        targeted = subprocess.run(
            ["git", "fetch", "origin", "--", *missing_hashes],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if targeted.returncode != 0:
            subprocess.run(
                ["git", "fetch", "--all", "--tags"],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        return all(self.commit_exists(repo_path, h) for h in missing_hashes)

    def commit_exists(self, repo_path, commit_hash):
        """Verifica se um commit específico existe no repositório.

        Hash com formato inválido retorna False com aviso (nunca chega ao
        subprocess); erro de ambiente (diretório sem git) é reportado alto
        para não se confundir com "commit ausente" (ROB-4).
        """
        if not is_valid_commit_hash(commit_hash):
            print(warning(f"Hash inválido ignorado: {commit_hash!r}"))
            return False
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        except OSError as e:
            print(error(
                f"Erro de ambiente ao verificar commit {commit_hash[:8]} em "
                f"{repo_path}: {e} — NÃO significa que o commit não existe."
            ))
            return False

    def get_commit_diff(self, repo_path, commit1, commit2):
        """Obtém o diff entre dois commits.

        Returns:
            str: O diff entre os dois commits ou None em caso de erro.
        """
        if not (is_valid_commit_hash(commit1) and is_valid_commit_hash(commit2)):
            print(error(f"Hashes inválidos para diff: {commit1!r}, {commit2!r}"))
            return None
        try:
            result = subprocess.run(
                ["git", "diff", commit1, commit2, "--"],
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
        if not is_valid_commit_hash(commit_hash):
            print(error(f"Hash inválido para mensagem: {commit_hash!r}"))
            return None
        try:
            result = subprocess.run(
                ["git", "log", "--format=%B", "-n", "1", commit_hash, "--"],
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

    # ------------------------------------------------------------------
    # Limpeza LRU (ROB-4): repositórios clonados são cache reconstruível
    # ------------------------------------------------------------------

    def cleanup_repos(self, max_gb: float | None = None, dry_run: bool = False) -> dict:
        """Aplica o orçamento de disco removendo repositórios menos usados.

        Args:
            max_gb: orçamento em GB (default: settings.repo_cache_max_gb).
            dry_run: apenas reporta o que seria removido.

        Returns:
            dict com total_gb_before/after e lista removed [(nome, gb)].
        """
        budget_gb = max_gb if max_gb is not None else _settings.repo_cache_max_gb
        repo_root = Path(REPO_DIR)
        if not repo_root.is_dir():
            return {"total_gb_before": 0.0, "total_gb_after": 0.0, "removed": []}

        def dir_size_bytes(path: Path) -> int:
            return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

        repos = []
        for entry in repo_root.iterdir():
            if entry.is_dir():
                repos.append({
                    "path": entry,
                    "size": dir_size_bytes(entry),
                    "last_used": entry.stat().st_mtime,
                })
        total = sum(r["size"] for r in repos)
        total_gb_before = total / (1024**3)
        removed = []

        if total_gb_before > budget_gb:
            # menos recentemente usados primeiro
            for repo in sorted(repos, key=lambda r: r["last_used"]):
                if total / (1024**3) <= budget_gb:
                    break
                size_gb = repo["size"] / (1024**3)
                age = time.strftime("%Y-%m-%d", time.localtime(repo["last_used"]))
                if dry_run:
                    print(info(f"[dry-run] removeria {repo['path'].name} ({size_gb:.2f} GB, último uso {age})"))
                else:
                    shutil.rmtree(repo["path"], ignore_errors=True)
                    print(info(f"Removido {repo['path'].name} ({size_gb:.2f} GB, último uso {age})"))
                removed.append((repo["path"].name, round(size_gb, 2)))
                total -= repo["size"]

        return {
            "total_gb_before": round(total_gb_before, 2),
            "total_gb_after": round(total / (1024**3), 2),
            "removed": removed,
        }
