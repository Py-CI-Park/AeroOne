export interface PermissionCatalogEntry {
  key: string;
  label: string;
  description: string;
  category: string;
}

export const PERMISSION_CATALOG: Record<string, { label: string; description: string; category: string }> = {
  'admin.users.read': { label: '사용자 조회', description: '관리자 콘솔에서 사용자 목록과 상세 정보를 조회합니다.', category: '사용자 관리' },
  'admin.users.manage': { label: '사용자 관리', description: '사용자 계정 상태와 기본 속성을 변경합니다.', category: '사용자 관리' },
  'admin.users.reset_password': { label: '비밀번호 초기화', description: '사용자 비밀번호 초기화 작업을 수행합니다.', category: '사용자 관리' },
  'admin.rbac.read': { label: 'RBAC 조회', description: '역할, 그룹, 권한 매트릭스를 조회합니다.', category: '권한/RBAC' },
  'admin.rbac.manage': { label: 'RBAC 관리', description: '그룹과 역할 기반 권한 구성을 변경합니다.', category: '권한/RBAC' },
  'admin.audit.read': { label: '감사 로그 조회', description: '관리자 감사 이벤트와 운영 이력을 조회합니다.', category: '감사/세션' },
  'admin.dashboard.manage': { label: '대시보드 관리', description: '대시보드 모듈 표시와 구성을 관리합니다.', category: '대시보드/모듈' },
  'admin.newsletters.read': { label: '뉴스레터 조회', description: '뉴스레터 콘텐츠와 메타데이터를 조회합니다.', category: '뉴스레터' },
  'admin.newsletters.write': { label: '뉴스레터 편집', description: '뉴스레터 콘텐츠를 생성하거나 수정합니다.', category: '뉴스레터' },
  'admin.newsletters.bulk': { label: '뉴스레터 일괄 작업', description: '뉴스레터 대량 처리 작업을 실행합니다.', category: '뉴스레터' },
  'admin.newsletters.sync': { label: '뉴스레터 동기화', description: '외부 또는 파일 기반 뉴스레터 동기화를 실행합니다.', category: '뉴스레터' },
  'admin.taxonomy.read': { label: '분류 조회', description: '카테고리와 태그 분류 정보를 조회합니다.', category: '분류' },
  'admin.taxonomy.manage': { label: '분류 관리', description: '카테고리와 태그 분류 체계를 변경합니다.', category: '분류' },
  'admin.read_tracking.read': { label: '읽음 추적 조회', description: '사용자 읽음 상태와 통계를 조회합니다.', category: '읽음 추적' },
  'admin.read_tracking.purge': { label: '읽음 추적 정리', description: '읽음 추적 데이터를 정리하거나 삭제합니다.', category: '읽음 추적' },
  'admin.backup.read': { label: '백업 조회', description: '백업 목록과 상태를 조회합니다.', category: '백업/복원' },
  'admin.backup.create': { label: '백업 생성', description: '관리자 백업 생성을 실행합니다.', category: '백업/복원' },
  'admin.restore.execute': { label: '복원 실행', description: '선택한 백업으로 복원 작업을 실행합니다.', category: '백업/복원' },
  'admin.ai.read': { label: 'AI 운영 조회', description: 'AI 서비스 상태와 운영 지표를 조회합니다.', category: 'AI 운영' },
  'admin.ai.manage': { label: 'AI 운영 관리', description: 'AI 운영 설정과 관리 작업을 수행합니다.', category: 'AI 운영' },
  'admin.sessions.read': { label: '세션 조회', description: '접속 세션과 로그인 현황을 조회합니다.', category: '감사/세션' },
  'admin.sessions.purge': { label: '세션 정리', description: '만료되었거나 불필요한 세션을 정리합니다.', category: '감사/세션' },
  'admin.resource_grants.read': { label: '리소스 권한 조회', description: '사용자와 그룹의 리소스별 권한을 조회합니다.', category: '권한/RBAC' },
  'admin.resource_grants.manage': { label: '리소스 권한 관리', description: '리소스별 권한 부여와 회수를 관리합니다.', category: '권한/RBAC' },
  'admin.office.manage': { label: 'Office Studio 보존·격리 관리', description: '만료 작업 purge, 작업 격리 보관함 인벤토리·복원·삭제, 미해결 복구 증적 인벤토리·비가역 폐기, 운영 스토리지 회계 현황을 관리합니다.', category: 'Office Studio' },
  'collections.read': { label: '문서 전체 열람', description: '허용된 컬렉션 문서를 열람합니다.', category: '문서 열람' },
  'collections.nsa.read': { label: 'NSA 문서 열람', description: 'NSA 컬렉션 문서를 열람합니다.', category: '문서 열람' },
  'search.nsa.read': { label: 'NSA 검색 열람', description: 'NSA 컬렉션 검색 결과를 조회합니다.', category: '검색' },
  'search.use': { label: '검색 사용', description: '문서 검색 기능을 사용합니다.', category: '검색' },
  'ai.use': { label: 'AI 사용', description: 'AI 질의와 요약 기능을 사용합니다.', category: 'AI 사용' },
  'ai.history.manage_own': { label: '내 AI 기록 관리', description: '본인의 AI 대화 기록을 관리합니다.', category: 'AI 사용' },
  'dashboard.openwebui.launch': { label: 'Open WebUI 실행', description: '대시보드에서 같은 호스트 8080 포트의 Open WebUI 링크 카드를 노출합니다.', category: '대시보드' },
  'office.use': { label: 'Office Studio 사용', description: '보고서·차트·다이어그램 생성과 본인 산출물 관리를 사용합니다.', category: 'Office Studio' },
  'admin.leantime.read': { label: 'Leantime 연결 조회', description: 'Leantime 서버 연결 등록 정보(마스킹된 API 키)와 상태를 조회합니다.', category: 'Leantime' },
  'admin.leantime.manage': { label: 'Leantime 연결 관리', description: 'Leantime 서버 연결의 등록·검증·회전·삭제를 수행합니다(평문 키는 저장·노출하지 않음).', category: 'Leantime' },
  'leantime.read': { label: 'Leantime 읽기', description: 'Leantime 프로젝트·담당 작업·기간 일정 요약을 서버 프록시로 조회합니다.', category: 'Leantime' },
};

export function describePermission(key: string): PermissionCatalogEntry {
  const entry = PERMISSION_CATALOG[key];
  if (!entry) return { key, label: key, description: '', category: '기타' };
  return { key, ...entry };
}

export function groupPermissionsByCategory(keys: string[]): Array<{ category: string; entries: PermissionCatalogEntry[] }> {
  const groups = new Map<string, PermissionCatalogEntry[]>();
  for (const key of keys) {
    const entry = describePermission(key);
    groups.set(entry.category, [...(groups.get(entry.category) ?? []), entry]);
  }

  return Array.from(groups.entries())
    .sort(([left], [right]) => {
      if (left === '기타') return 1;
      if (right === '기타') return -1;
      return left.localeCompare(right, 'ko');
    })
    .map(([category, entries]) => ({
      category,
      entries: entries.sort((left, right) => left.key.localeCompare(right.key)),
    }));
}
