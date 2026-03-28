from pathlib import Path

import pytest

from app.core.path_guard import PathGuardError, ensure_within_root


def test_ensure_within_root_allows_descendant(tmp_path: Path) -> None:
    root = tmp_path / 'root'
    child = root / 'nested' / 'file.txt'
    child.parent.mkdir(parents=True)
    child.write_text('ok', encoding='utf-8')

    resolved = ensure_within_root(root, child)

    assert resolved == child.resolve()


def test_ensure_within_root_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / 'root'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('nope', encoding='utf-8')

    with pytest.raises(PathGuardError):
        ensure_within_root(root, outside)
