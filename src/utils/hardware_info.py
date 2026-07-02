"""Identidade de hardware e métricas de GPU para o snapshot de sessão.

Fase E3 (EVOLUTION_PLAN.md, REP-3): as condições de execução — máquina, SO,
GPU, camadas na GPU — influenciam latência e viabilidade das análises, mas
não eram registradas em lugar nenhum (as colunas de GPU de ``runner_status``
existiam vazias desde a Fase 11). Tudo aqui é best-effort e nunca falha a
análise: valores indisponíveis viram ``"unknown"``/None.

Duas funções:
- :func:`get_hardware_info` — snapshot estático (cacheado por processo),
  gravado no ``config_snapshot`` de cada sessão;
- :func:`sample_gpu_metrics` — amostra dinâmica (utilização %, memória MB)
  via ``nvidia-smi``, enviada em cada heartbeat do runner. Em máquinas sem
  NVIDIA (ex.: o MacBook de monitoramento) retorna ``(None, None)``.
"""

from __future__ import annotations

import functools
import os
import platform
import subprocess

from src.core.settings import settings as _settings


def _total_ram_gb() -> float | None:
    """RAM física total em GB (POSIX; None se indeterminável)."""
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return round(page_size * pages / (1024**3), 1)
    except (ValueError, OSError, AttributeError):
        return None


def _nvidia_gpu_info() -> dict | None:
    """Nome/VRAM/driver da GPU NVIDIA via nvidia-smi; None se ausente."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        line = result.stdout.strip().splitlines()[0]
        name, memory_total, driver = [part.strip() for part in line.split(",")]
        return {"gpu": name, "gpu_memory": memory_total, "gpu_driver": driver}
    except (FileNotFoundError, subprocess.SubprocessError, IndexError, ValueError):
        return None


@functools.lru_cache(maxsize=1)
def get_hardware_info() -> dict:
    """Snapshot estático do ambiente de execução (cacheado por processo)."""
    info: dict = {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "ram_gb": _total_ram_gb(),
        "num_gpu_layers": _settings.num_gpu_layers,
    }
    nvidia = _nvidia_gpu_info()
    if nvidia:
        info.update(nvidia)
    elif platform.system() == "Darwin" and platform.machine() == "arm64":
        info["gpu"] = "Apple Silicon (GPU integrada)"
        info["gpu_driver"] = "Metal"
    else:
        info["gpu"] = "unknown"
    return info


def sample_gpu_metrics() -> tuple[float | None, float | None]:
    """Amostra (utilização %, memória usada MB) da GPU NVIDIA.

    Best-effort para o heartbeat; (None, None) sem NVIDIA/nvidia-smi.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        line = result.stdout.strip().splitlines()[0]
        utilization, memory_used = [part.strip() for part in line.split(",")]
        return float(utilization), float(memory_used)
    except (FileNotFoundError, subprocess.SubprocessError, IndexError, ValueError):
        return None, None
