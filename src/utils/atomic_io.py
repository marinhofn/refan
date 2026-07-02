"""Escrita atômica e lock advisory para os arquivos de dados da pesquisa.

Fase E4 (EVOLUTION_PLAN.md, ROB-1/ROB-2): os masters de trabalho (CSV),
o tracking de commits analisados e os JSONs de sessão eram sobrescritos
in-place — um crash no meio do write corrompia o arquivo, e dois processos
concorrentes perdiam atualizações (last-writer-wins). Horas de GPU dependem
desses arquivos.

Primitivas:
- :func:`atomic_write_text` / :func:`atomic_write_json` — escrevem em arquivo
  temporário NO MESMO diretório, com flush+fsync, e publicam via
  ``os.replace`` (atômico em POSIX): o leitor vê sempre o conteúdo antigo ou
  o novo, nunca um estado intermediário;
- :func:`file_lock` — lock advisory exclusivo (``fcntl.flock``) sobre um
  arquivo-sentinela ``<alvo>.lock``, serializando read-modify-write entre
  processos na mesma máquina (o design multi-runner usa máquinas distintas
  com masters distintos; o lock cobre o caso real de dois processos locais).
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Escreve texto em ``path`` de forma atômica (temp + fsync + replace)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, target)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | Path, obj, indent: int = 2) -> None:
    """Serializa ``obj`` como JSON e publica atomicamente em ``path``."""
    atomic_write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))


@contextmanager
def file_lock(path: str | Path):
    """Lock advisory exclusivo sobre ``<path>.lock`` (bloqueante).

    Uso:
        with file_lock(csv_master):
            df = pd.read_csv(csv_master)
            ...
            atomic_write_text(csv_master, df.to_csv(index=False))
    """
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
