"""Refuse to silently overwrite preregistered stage artifacts.

`runs/stage1_*.json` and `runs/stage2_*.json` back the first two of the four
preregistered criteria, and `runs/store_data*.db` is the replayed store the
agent conditions read. They have been destroyed twice by pipeline reruns, so
writing over an existing one now requires an explicit opt-in:

    ALLOW_OVERWRITE_STAGE=1 python3 detect/eval_stage1.py

Use `guarded_write(path, obj)` in place of a bare `json.dump` to a stage path.
"""

import fnmatch
import json
import os

PROTECTED_PATTERNS = ["runs/stage1_*.json", "runs/stage2_*.json",
                      "runs/store_data*.db"]
OVERRIDE_ENV = "ALLOW_OVERWRITE_STAGE"


class ProtectedArtifactError(RuntimeError):
    pass


def is_protected(path):
    norm = os.path.normpath(path).replace(os.sep, "/")
    return any(fnmatch.fnmatch(norm, pat) for pat in PROTECTED_PATTERNS)


def check_writable(path):
    """Raise unless `path` may be written."""
    if not is_protected(path) or not os.path.exists(path):
        return
    if os.environ.get(OVERRIDE_ENV) == "1":
        return
    raise ProtectedArtifactError(
        f"refusing to overwrite preregistered artifact {path}. "
        f"It backs a preregistered criterion and has been destroyed twice. "
        f"Re-run with {OVERRIDE_ENV}=1 if you intend to regenerate it.")


def guarded_write(path, obj, indent=2):
    check_writable(path)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent)
    return path
