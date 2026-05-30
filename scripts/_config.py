#!/usr/bin/env python3
"""
配置加载器（所有脚本共用）

按优先级查找 config.yaml：
1. 环境变量 FKTO_CONFIG 指向的路径
2. 当前脚本同目录的 ../config.yaml
3. ~/.hermes/feishu-kanban-task-orchestration/config.yaml
4. /etc/feishu-kanban-task-orchestration/config.yaml

如果都没有，退回到 config.example.yaml（占位值会让脚本 no-op，避免误操作）。
"""

import os
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    print("[_config] 缺 PyYAML，跑 `pip install pyyaml`", file=sys.stderr)
    raise


_CACHE = None


def _candidate_paths():
    here = Path(__file__).resolve().parent
    candidates = []
    if os.environ.get("FKTO_CONFIG"):
        candidates.append(Path(os.environ["FKTO_CONFIG"]).expanduser())
    candidates.append(here.parent / "config.yaml")
    candidates.append(Path("~/.hermes/feishu-kanban-task-orchestration/config.yaml").expanduser())
    candidates.append(Path("/etc/feishu-kanban-task-orchestration/config.yaml"))
    candidates.append(here.parent / "config.example.yaml")  # 兜底
    return candidates


def load_config():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    for p in _candidate_paths():
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                _CACHE = yaml.safe_load(f) or {}
            _CACHE["_loaded_from"] = str(p)
            return _CACHE
    raise FileNotFoundError("config.yaml not found; 复制 config.example.yaml -> config.yaml 后再跑")


def env_with_overrides():
    """返回带 config.env 的环境字典，子进程用这个 env 跑"""
    cfg = load_config()
    env = dict(os.environ)
    for k, v in (cfg.get("env") or {}).items():
        env[str(k)] = str(v)
    return env
