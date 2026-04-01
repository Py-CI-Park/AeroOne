from __future__ import annotations

from pathlib import Path


class PathGuardError(ValueError):
    pass


def ensure_within_root(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_root == resolved_candidate or resolved_root in resolved_candidate.parents:
        return resolved_candidate
    raise PathGuardError(f'{resolved_candidate} is outside allowed root {resolved_root}')
