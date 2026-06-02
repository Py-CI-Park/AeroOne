// AeroOne 업데이트 내역 — 헤더의 버전 라벨을 누르면 뜨는 팝업의 데이터 원천.
// 폐쇄망이라 외부 의존 없이 번들에 직접 담는다. 새 릴리스마다 맨 앞에 항목을 추가하고
// APP_VERSION 은 항상 CHANGELOG[0].version 을 따른다(헤더 라벨이 자동으로 이를 표시).

export const APP_CONTACT = {
  name: '박찬일',
} as const;

export type ChangelogEntry = {
  version: string;
  date: string; // YYYY-MM-DD
  items: string[];
};

// 최신 버전이 맨 위.
export const CHANGELOG: ChangelogEntry[] = [
  {
    version: '1.0.22',
    date: '2026-06-02',
    items: [
      '기본 실행을 LAN(IP)으로 변경 — setup_offline/start_offline 을 옵션 없이 실행하면(더블클릭 포함) 프롬프트 없이 이 PC 의 LAN IP 를 자동 감지해 0.0.0.0 으로 띄웁니다. 이 PC 에서만 쓰려면 --local.',
    ],
  },
  {
    version: '1.0.21',
    date: '2026-06-02',
    items: [
      'start_offline.bat 더블클릭 시 LAN(IP)으로 띄울지 한 번 물어보는 선택 프롬프트 추가 — Y면 LAN IP 자동, 기본(N/15초)은 이 PC 만(localhost).',
    ],
  },
  {
    version: '1.0.20',
    date: '2026-06-02',
    items: [
      'LAN(IP) 접속 편의 개선 — setup_offline/start_offline 에 --allow-host=auto(이 PC의 LAN IP 자동 감지)를 추가하고, 방화벽 인바운드 허용 헬퍼를 모든 네트워크 프로필에 적용.',
    ],
  },
  {
    version: '1.0.19',
    date: '2026-06-02',
    items: [
      '뉴스레터 페이지에서 아래로 스크롤하면 우하단에 "맨 위로" 버튼이 나타나 한 번에 위로 이동.',
    ],
  },
  {
    version: '1.0.18',
    date: '2026-06-02',
    items: [
      '버전 팝업의 문의 표기를 이름만 노출하도록 정리(이메일 제외).',
    ],
  },
  {
    version: '1.0.17',
    date: '2026-06-02',
    items: [
      '헤더의 버전 라벨을 누르면 업데이트 내역과 문의 정보를 보여주는 팝업을 추가.',
    ],
  },
  {
    version: '1.0.16',
    date: '2026-06-02',
    items: [
      'Newsletter/output 에 파일을 넣으면 서버 재시작 없이 페이지 새로고침만으로 자동 반영(읽기 시 지연 동기화).',
      'LAN(IP) 접속 보강 — 방화벽 인바운드 허용 헬퍼(scripts/allow_lan_firewall.cmd)와 start_offline 안내 힌트 추가.',
    ],
  },
  {
    version: '1.0.15',
    date: '2026-05-27',
    items: ['폐쇄망 프론트 창이 따옴표 escape 오류로 기동하지 못하던 문제 수정.'],
  },
  {
    version: '1.0.14',
    date: '2026-05-27',
    items: ['뉴스레터 첫 진입 시 본문이 잘리던 문제 수정(iframe 높이 재측정 보강).'],
  },
];

export const APP_VERSION = CHANGELOG[0].version;
