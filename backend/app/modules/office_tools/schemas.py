"""Office Studio의 생성·작업·수명주기 API에 사용하는 typed 요청·응답 스키마.

보고서·차트·다이어그램 생성 결과와 owner/admin 작업 수명주기, 재시도 가능한 오류 envelope를
한 모듈에서 정의해 FastAPI 응답과 OpenAPI 계약이 같은 DTO를 사용하게 한다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# 다이어그램 유형(브라우저 Mermaid 렌더 대상). 서버는 소스만 만들고 검증한다.
DiagramType = Literal['flowchart', 'sequence', 'state', 'gantt']

# 서버측 입력 상한(BUILD_CONTRACT §2.4 "서버 검증"). 프런트 zod 와 값이 일치해야 한다.
MAX_DESCRIPTION_CHARS = 30_000
MAX_TITLE_CHARS = 200

# 보고서 스튜디오(svc01) 입력 상한/화이트리스트. 라우트가 이 값을 강제한다.
ReportAiMode = Literal['none', 'polish', 'executive']
MAX_REPORT_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_REPORT_MARKDOWN_CHARS = 200_000
REPORT_MARKDOWN_SUFFIXES = ('.md', '.markdown', '.txt')

# 차트 스튜디오(svc02) 입력 상한/화이트리스트. capabilities 의 limits 값과 일치한다.
ChartType = Literal['bar', 'line', 'area', 'scatter', 'pie', 'histogram']
MAX_CHART_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_CHART_DATA_ROWS = 100_000
CHART_DATA_SUFFIXES = ('.csv', '.xlsx', '.xlsm', '.json')


class OfficeSampleResponse(BaseModel):
    """각 스튜디오의 '예제 불러오기'용 샘플 데이터 + 폼 프리필 힌트."""

    key: str
    tool: Literal['report', 'chart', 'diagram']
    filename: str
    media_type: str
    title: str
    description: str
    content: str
    hints: dict[str, Any] = Field(default_factory=dict)


class OfficeHealth(BaseModel):
    status: str
    service: str


class OfficeServiceFlags(BaseModel):
    report: bool
    chart: bool
    diagram: bool


class OfficeLlmCapability(BaseModel):
    active: bool
    default_model: str | None
    fallback: str


class OfficeCapabilities(BaseModel):
    services: OfficeServiceFlags
    llm: OfficeLlmCapability
    limits: dict[str, int]


class DiagramGenerateRequest(BaseModel):
    """다이어그램 생성 요청. AI 보조를 켜면 활성 LLM 연결로 Mermaid 를 제안한다."""

    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    diagram_type: DiagramType = 'flowchart'
    title: str = Field(default='', max_length=MAX_TITLE_CHARS)
    ai_assist: bool = True


class DiagramSpec(BaseModel):
    """검증을 통과한 Mermaid 소스와 메타. LLM/폴백 양쪽이 같은 형태를 만든다."""

    diagram_type: DiagramType = 'flowchart'
    title: str = Field(default='업무 다이어그램', max_length=MAX_TITLE_CHARS)
    mermaid: str = Field(min_length=3, max_length=50_000)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class OfficeJobArtifactResponse(BaseModel):
    """검증된 job manifest의 다운로드 가능한 산출물."""

    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    download_url: str


class DiagramGenerateResponse(BaseModel):
    """생성 결과. job 레코드 요약 + 브라우저가 렌더할 Mermaid 소스."""

    job_id: str
    status: str
    title: str
    llm_used: bool
    diagram_type: DiagramType
    mermaid: str
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[OfficeJobArtifactResponse] = Field(default_factory=list)
    preview_url: str
    bundle_url: str


class ReportGenerateResponse(BaseModel):
    """보고서 생성 결과. job 요약 + 즉시 미리보기용 sanitize HTML 을 함께 돌려준다.

    ``html`` 은 응답 편의(iframe srcdoc)용이며 job.json 에는 저장하지 않는다(중복 회피).
    영구 산출물은 ``aeroone_report.html`` artifact 로 별도 다운로드한다.
    """

    job_id: str
    status: str
    title: str
    ai_mode: ReportAiMode
    llm_used: bool
    html: str
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[OfficeJobArtifactResponse] = Field(default_factory=list)
    preview_url: str
    bundle_url: str


class ChartColumnProfile(BaseModel):
    """inspect 가 돌려주는 열 단위 프로필(스펙 작성 힌트)."""

    name: str
    dtype: str
    non_null: int
    null: int
    unique: int
    numeric: bool
    datetime: bool


class ChartInspectResponse(BaseModel):
    """데이터 프로필 — 행/열 수 + 열별 요약 + 앞부분 샘플."""

    row_count: int
    column_count: int
    columns: list[ChartColumnProfile] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)


class ChartGenerateResponse(BaseModel):
    """차트 생성 결과. job 요약 + 브라우저가 렌더할 ChartSpec/ECharts option."""

    job_id: str
    status: str
    title: str
    llm_used: bool
    chart_spec: dict[str, Any]
    echarts_option: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[OfficeJobArtifactResponse] = Field(default_factory=list)
    preview_url: str
    bundle_url: str
class OfficeJobUsageResponse(BaseModel):
    """현재 소유자의 job 수·산출물 사용량과 적용 중인 한도."""

    job_count: int
    total_bytes: int
    max_jobs_per_owner: int
    max_bytes_per_owner: int


class OfficeJobListItemResponse(BaseModel):
    """소유자 작업 목록에 필요한 안전한 job 요약."""

    job_id: str
    service: str
    status: str
    created_at: str
    updated_at: str
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[OfficeJobArtifactResponse] = Field(default_factory=list)
    title: str | None = None
    llm_used: bool | None = None


class OfficeJobDetailResponse(BaseModel):
    """job 상세의 불변 핵심 필드와 서비스별 완료 메타데이터."""

    model_config = ConfigDict(extra='allow')

    job_id: str
    service: str
    owner_id: int
    status: str
    created_at: str
    updated_at: str
    request_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[OfficeJobArtifactResponse] = Field(default_factory=list)
    error: str | None = None


class OfficeJobListResponse(BaseModel):
    """소유자 범위 작업 목록과 사용량."""

    jobs: list[OfficeJobListItemResponse] = Field(default_factory=list)
    usage: OfficeJobUsageResponse


class OfficeJobOwnerIdentityItemResponse(BaseModel):
    """정상 소유자 sidecar 또는 이름·경로를 숨긴 손상 evidence placeholder."""

    kind: Literal['owner_identity', 'corrupt']
    management_token: str | None = None
    job_id: str | None = None
    owner_id: int | None = None
    physical_bytes: int = Field(ge=0)
    reason: str | None = None


class OfficeJobOwnerIdentityInventoryResponse(BaseModel):
    """소유자 identity sidecar의 typed inventory와 손상 evidence 점유량."""

    items: list[OfficeJobOwnerIdentityItemResponse] = Field(default_factory=list)
    total_bytes: int = Field(ge=0)
    corrupt_entries: int = Field(ge=0)
    corrupt_physical_bytes: int = Field(ge=0)

class OfficeJobQuarantineItemResponse(BaseModel):
    """정상 격리 항목 또는 이름·경로를 숨긴 손상 evidence placeholder."""

    kind: Literal['quarantine', 'corrupt']
    quarantine_id: str | None = None
    management_token: str | None = None
    job_id: str | None = None
    owner_id: int | None = None
    size_bytes: int = Field(ge=0)
    physical_bytes: int = Field(ge=0)
    quarantined_at: str | None = None
    reason: str


class OfficeJobQuarantineInventoryResponse(BaseModel):
    """격리 저장소의 typed inventory와 논리·물리 점유량."""

    items: list[OfficeJobQuarantineItemResponse] = Field(default_factory=list)
    total_bytes: int = Field(ge=0)
    physical_total_bytes: int = Field(ge=0)
    corrupt_entries: int = Field(ge=0)


class OfficeJobDeletionOutcomeResponse(BaseModel):
    """Purge가 완료하지 못한 삭제의 실제 제거·durability 상태."""

    entry_id: str
    entry_kind: str
    parent_id: str
    physical_bytes: int = Field(ge=0)
    partial_bytes_removed: int = Field(ge=0)
    removed: bool
    durably_synced: bool
    durability: Literal['pending', 'synced', 'platform_best_effort']
    retry_required: bool


class OfficeJobDirectMutationOutcomeResponse(BaseModel):
    """직접 관리자 mutation의 공개·제거·durability 실제 결과."""

    operation: str
    target_id: str
    management_token: str | None = None
    job_id: str | None = None
    owner_id: int | None = None
    logical_bytes: int = Field(ge=0)
    physical_bytes: int = Field(ge=0)
    partial_bytes_removed: int = Field(ge=0)
    published: bool
    removed: bool
    durably_synced: bool
    durability: Literal['pending', 'synced', 'platform_best_effort']
    retry_required: bool

class OfficeJobAuditPersistenceStateResponse(BaseModel):
    """파일 outbox receipt의 감사 반영과 미해결 mutation 상태."""

    pending_result_id: str
    state: Literal[
        'prepared',
        'mutation_started',
        'result_ready',
        'audit_persisted',
        'audit_failed',
        'unresolved',
    ]
    retry_required: bool
    outcome_known: bool = False

class OfficeJobPendingReceiptItemResponse(BaseModel):
    """Publicly safe operator inventory for a pending destructive-operation receipt."""

    pending_result_id: str
    original_actor_id: int | None = Field(default=None, ge=1)
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    state: Literal['prepared', 'mutation_started', 'result_ready', 'audit_persisted', 'unresolved']
    phase: int | None = Field(default=None, ge=0, le=3)
    outcome_known: bool
    retry_required: bool
    created_at: str | None = None
    updated_at: str | None = None


class OfficeJobPendingReceiptInventoryResponse(BaseModel):
    """All pending receipts, projected without intent, provenance, audit metadata, or evidence."""

    items: list[OfficeJobPendingReceiptItemResponse] = Field(default_factory=list)


class OfficeJobPendingReceiptReplayResponse(BaseModel):
    """A privileged operator triggered recovery; the original receipt owns lifecycle provenance."""

    pending_result_id: str
    replayed: bool



class OfficeJobUnresolvedMutationFailureDetail(BaseModel):
    """receipt가 결과를 안전하게 단정할 수 없거나 감사 재시도가 남은 실패 상태."""

    error: str
    audit_persistence: OfficeJobAuditPersistenceStateResponse
    unresolved: bool
    outcome: (
        OfficeJobDeletionOutcomeResponse
        | OfficeJobDirectMutationOutcomeResponse
        | OfficeJobOwnerDeletionOutcomeResponse
        | None
    ) = None
    partial_result: OfficeJobPurgeResponse | None = None
    receipt_metadata: dict[str, Any] | None = None


class OfficeJobUnresolvedMutationFailureResponse(BaseModel):
    """FastAPI HTTPException envelope를 포함한 미해결 mutation 실패 응답."""

    detail: OfficeJobUnresolvedMutationFailureDetail


class OfficeJobDirectMutationPartialFailureDetail(BaseModel):
    """뒤늦은 실패에도 손실하지 않는 직접 mutation 부분 결과."""

    error: str
    outcome: OfficeJobDirectMutationOutcomeResponse
    audit_persistence: OfficeJobAuditPersistenceStateResponse | None = None




class OfficeJobDirectMutationFailureResponse(BaseModel):
    """직접 mutation의 typed partial 또는 명시적 미해결 실패 envelope."""

    detail: OfficeJobDirectMutationPartialFailureDetail | OfficeJobUnresolvedMutationFailureDetail


class OfficeJobOwnerDeletionOutcomeResponse(BaseModel):
    """소유자 삭제의 job·durability·sidecar 정리 실제 결과."""

    operation: str
    job_id: str
    owner_id: int = Field(gt=0)
    logical_bytes: int = Field(ge=0)
    physical_bytes: int = Field(ge=0)
    partial_bytes_removed: int = Field(ge=0)
    removed: bool
    durably_synced: bool
    durability: Literal['pending', 'synced', 'platform_best_effort']
    owner_identity_removed: bool
    owner_identity_durably_synced: bool
    owner_identity_durability: Literal['pending', 'synced', 'platform_best_effort']
    retry_required: bool


class OfficeJobOwnerDeletionResponse(BaseModel):
    """성공한 소유자 삭제의 typed actual outcome."""

    outcome: OfficeJobOwnerDeletionOutcomeResponse


class OfficeJobOwnerDeletionPartialFailureDetail(BaseModel):
    """부분 완료된 소유자 삭제의 재시도 판단 가능한 공개 결과."""

    error: str
    outcome: OfficeJobOwnerDeletionOutcomeResponse
    audit_persistence: OfficeJobAuditPersistenceStateResponse | None = None


class OfficeJobOwnerDeletionFailureResponse(BaseModel):
    """소유자 삭제의 typed partial 또는 명시적 미해결 실패 envelope."""

    detail: OfficeJobOwnerDeletionPartialFailureDetail | OfficeJobUnresolvedMutationFailureDetail






class OfficeJobQuarantineActionResponse(BaseModel):
    """격리 복원·삭제의 호환 inventory 항목과 직접 mutation 결과."""

    item: OfficeJobQuarantineItemResponse | None = None
    outcome: OfficeJobDirectMutationOutcomeResponse


class OfficeJobRecoveryItemResponse(BaseModel):
    """정상 recovery 항목 또는 이름·경로를 숨긴 손상 evidence placeholder."""

    kind: Literal['recovery', 'corrupt']
    recovery_id: str | None = None
    management_token: str | None = None
    transaction_id: str | None = None
    reason: str
    quarantined_at: str | None = None
    journal_preserved: bool
    stage_preserved: bool
    size_bytes: int = Field(ge=0)
    physical_bytes: int = Field(ge=0)


class OfficeJobRecoveryInventoryResponse(BaseModel):
    """해결되지 않은 recovery transaction inventory와 점유량."""

    items: list[OfficeJobRecoveryItemResponse] = Field(default_factory=list)
    recovery_ids: list[str] = Field(default_factory=list)
    management_tokens: list[str] = Field(default_factory=list)
    total_bytes: int = Field(ge=0)
    corrupt_entries: int = Field(ge=0)


class OfficeJobRecoveryActionResponse(BaseModel):
    """recovery evidence 제거의 호환 inventory 항목과 직접 mutation 결과."""

    item: OfficeJobRecoveryItemResponse | None = None
    outcome: OfficeJobDirectMutationOutcomeResponse


class OfficeJobEvidenceDispositionResponse(BaseModel):
    """손상 evidence token의 되돌릴 수 없는 안전 처분 결과."""

    outcome: OfficeJobDirectMutationOutcomeResponse


class OfficeJobStorageAccountingResponse(BaseModel):
    """소유자 quota와 별개인 Office JobStore의 전체 파일 점유량."""

    job_bytes: int = Field(ge=0)
    artifact_logical_bytes: int = Field(ge=0)
    job_logical_bytes: int = Field(ge=0)
    job_physical_bytes: int = Field(ge=0)
    job_metadata_physical_bytes: int = Field(ge=0)
    job_temporary_physical_bytes: int = Field(ge=0)
    job_artifact_physical_bytes: int = Field(ge=0)
    job_unclassified_physical_bytes: int = Field(ge=0)
    quarantine_bytes: int = Field(ge=0)
    quarantine_physical_bytes: int = Field(ge=0)
    recovery_quarantine_physical_bytes: int = Field(ge=0)
    owner_identity_physical_bytes: int = Field(ge=0)
    owner_identity_entries: int = Field(ge=0)
    owner_identity_corrupt_entries: int = Field(ge=0)
    owner_identity_corrupt_physical_bytes: int = Field(ge=0)
    staging_physical_bytes: int = Field(ge=0)
    transaction_journal_physical_bytes: int = Field(ge=0)
    owner_deletion_tombstone_entries: int = Field(ge=0)
    owner_deletion_tombstone_physical_bytes: int = Field(ge=0)
    pending_result_entries: int = Field(ge=0)
    pending_result_physical_bytes: int = Field(ge=0)
    temporary_bundle_bytes: int = Field(ge=0)
    bundle_physical_bytes: int = Field(ge=0)
    lock_physical_bytes: int = Field(ge=0)
    root_unclassified_physical_bytes: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


class OfficeJobMaintenanceResponse(BaseModel):
    """Purge에 포함되는 journal recovery 및 보조 저장소 정리 결과."""

    recovered_transactions: int = Field(ge=0)
    rolled_back_transactions: int = Field(ge=0)
    unresolved_recovery_transactions: int = Field(ge=0)
    unresolved_recovery_ids: list[str] = Field(default_factory=list)
    malformed_recovery_evidence: int = Field(ge=0)
    owner_deletion_tombstone_failures: list[str] = Field(default_factory=list)
    orphan_stage_dirs: int = Field(ge=0)
    orphan_stage_bytes: int = Field(ge=0)
    stale_bundles: int = Field(ge=0)
    stale_bundle_bytes: int = Field(ge=0)
    expired_quarantine_entries: int = Field(ge=0)
    expired_quarantine_bytes: int = Field(ge=0)


class OfficeJobPurgeResponse(BaseModel):
    """관리자 보존 기간 purge의 완전한 destructive-work 결과."""

    deleted_jobs: int = Field(ge=0)
    deleted_job_ids: list[str] = Field(default_factory=list)
    freed_bytes: int = Field(ge=0)
    logical_artifact_freed_bytes: int = Field(ge=0)
    physical_deleted_bytes: int = Field(ge=0)
    quarantined_job_ids: list[str] = Field(default_factory=list)
    quarantined_quarantine_ids: list[str] = Field(default_factory=list)
    quarantined_bytes: int = Field(ge=0)
    logical_artifact_quarantined_bytes: int = Field(ge=0)
    physical_quarantined_bytes: int = Field(ge=0)
    failed_job_ids: list[str] = Field(default_factory=list)
    failed_quarantine_ids: list[str] = Field(default_factory=list)
    quarantine_bytes: int = Field(ge=0)
    temporary_bundle_bytes: int = Field(ge=0)
    expired_quarantine_entries: int = Field(ge=0)
    expired_quarantine_bytes: int = Field(ge=0)
    expired_quarantine_ids: list[str] = Field(default_factory=list)
    stale_bundles: int = Field(ge=0)
    stale_bundle_bytes: int = Field(ge=0)
    orphan_stage_dirs: int = Field(ge=0)
    orphan_stage_bytes: int = Field(ge=0)
    maintenance: OfficeJobMaintenanceResponse
    partial_deletion_outcomes: list[OfficeJobDeletionOutcomeResponse] = Field(default_factory=list)


class OfficeJobPurgePartialFailureDetail(BaseModel):
    """부분 완료 purge의 공개 오류 detail. 내부 예외 원인은 노출하지 않는다."""

    error: str
    partial_result: OfficeJobPurgeResponse
    audit_persistence: OfficeJobAuditPersistenceStateResponse | None = None


class OfficeJobPurgeFailureResponse(BaseModel):
    """Purge의 typed partial 또는 명시적 미해결 실패 envelope."""

    detail: OfficeJobPurgePartialFailureDetail | OfficeJobUnresolvedMutationFailureDetail


OfficeJobUnresolvedMutationFailureDetail.model_rebuild()
