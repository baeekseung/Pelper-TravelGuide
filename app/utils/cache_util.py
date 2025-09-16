import os
import pickle
import hashlib
from typing import Any, Optional


def _cache_dir() -> str:
    # 프로젝트 루트 기준 cache 디렉토리
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cdir = os.path.join(here, "cache")
    os.makedirs(cdir, exist_ok=True)
    return cdir


def _key_to_path(key: str) -> str:
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(_cache_dir(), f"{h}.pkl")


def load_cache(key: str) -> Optional[Any]:
    path = _key_to_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def save_cache(key: str, data: Any) -> None:
    path = _key_to_path(key)
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass
