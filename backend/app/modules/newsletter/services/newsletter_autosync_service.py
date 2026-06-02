from __future__ import annotations

import os
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.newsletter.services.file_discovery_service import HTML_RE, PDF_RE
from app.modules.newsletter.services.newsletter_import_service import ImportResult, NewsletterImportService

DirectorySignature = tuple[tuple[str, int, int], ...]


def compute_signature(import_root: Path) -> DirectorySignature:
    # FileDiscoveryService 와 동일한 규칙(_debug.html 제외 + HTML/PDF 파일명 정규식)으로
    # 후보 파일만 본다. 내용 해시 없이 (파일명, 크기, mtime_ns) 만으로 변경을 싸게 감지.
    # 무관한 파일이 추가돼도 헛 sync 가 돌지 않는다.
    if not import_root.exists():
        return ()
    entries: list[tuple[str, int, int]] = []
    with os.scandir(import_root) as iterator:
        for entry in iterator:
            name = entry.name
            if not entry.is_file() or name.endswith('_debug.html'):
                continue
            if not (HTML_RE.match(name) or PDF_RE.match(name)):
                continue
            stat = entry.stat()
            entries.append((name, stat.st_size, stat.st_mtime_ns))
    entries.sort()
    return tuple(entries)


class AutoSyncState:
    """프로세스 1개가 공유하는 자동 동기화 상태.

    실행 중인 서버는 Newsletter/output 을 스스로 재스캔하지 않는다 — sync 는
    seed(=setup_offline) 와 관리자 Sync 엔드포인트에서만 돌았다. 그래서 새 발행호가
    달력/목록/최신글에 뜨려면 setup 을 다시 돌려야 했다. 이 상태는 공개 읽기 요청이
    들어올 때마다 폴더의 싸구려 시그니처를 비교해 *바뀐 경우에만* sync 를 돌리도록
    마지막 시그니처와 동시 sync 방지용 lock 을 보관한다. create_app 에서 1회 생성해
    app.state 에 둔다.
    """

    __slots__ = ('signature', 'lock')

    def __init__(self) -> None:
        self.signature: DirectorySignature | None = None
        self.lock = threading.Lock()


class NewsletterAutoSyncService:
    """공개 읽기 경로에서 도는 지연(lazy) 자동 동기화.

    신뢰 경계: 스캔 대상은 운영자 자신의 신뢰 콘텐츠 폴더(seed 와 동일한 import_root)
    이고, 새로운 무인증 mutation 엔드포인트를 만들지 않는다. DB sync 는 읽기의 내부
    부수효과일 뿐이다. 변경 감지는 (파일명, 크기, mtime_ns) 만으로 싸게 처리하고,
    내용 해시 같은 무거운 작업은 변경이 감지된 sync 시점에만 NewsletterImportService
    안에서 수행한다.
    """

    def __init__(self, db: Session, import_root: Path, state: AutoSyncState) -> None:
        self.db = db
        self.import_root = import_root
        self.state = state

    def refresh_if_changed(self) -> ImportResult | None:
        # 폴더가 없으면 sync 를 돌리지 않는다. 빈 스캔으로 sync 를 돌리면
        # _deactivate_missing 이 기존 발행호를 전부 비활성화하는 파괴적 동작이 된다
        # (seed._sync_external_newsletters 와 동일한 가드).
        if not self.import_root.exists():
            return None
        with self.state.lock:
            signature = compute_signature(self.import_root)
            if signature == self.state.signature:
                return None
            result = NewsletterImportService(self.db, self.import_root).sync()
            # sync 는 신규 생성 시에만 flush 하므로, 갱신/비활성 변경이 같은 요청의
            # 후속 조회에 확실히 보이도록 한 번 더 flush 한다.
            self.db.flush()
            # 같은 요청에서 이어지는 조회가 일관된 상태를 보도록 세션을 만료시킨다.
            # published_at 은 tz-aware(UTC)로 생성되지만 SQLite 는 tz 를 저장하지 못해
            # 재로딩 시 naive 가 된다 — 방금 만든(aware) 행과 기존(naive) 행이 한 정렬에
            # 섞이면 _timeline_candidates 가 naive/aware 비교 오류를 낸다. expire_all 로
            # 전부 DB 에서 다시 읽어 "sync 후 다음 요청에서 read" 와 같은 상태로 맞춘다.
            self.db.expire_all()
            self.state.signature = signature
            return result
