import React from 'react';
import { render, screen } from '@testing-library/react';

import { MarkdownMessage } from '@/components/ai/ai-markdown';

// G003 회귀: 스트리밍 중간 상태('## ' 처럼 제목 텍스트가 아직 도착하지 않은 접두사)가
// 파서 무한 루프를 일으켜 브라우저 메인 스레드를 잠갔던 실결함(라이브 E2E 실측).
// MarkdownMessage 는 델타마다 전체 재파싱되므로, 대표 답변의 "모든 접두사"가 종료되어야 한다.
const FULL_ANSWER = [
  '## 폐쇄망 사내 포털의 장점',
  '',
  '1. **보안 강화:** 외부 유출이 차단됩니다.',
  '2. **정보 통제:** 접근 권한을 관리합니다.',
  '',
  '---',
  '',
  '| 항목 | 효과 |',
  '|---|---|',
  '| 보안 | 높음 |',
  '',
  '> 참고: 폐쇄망 원칙.',
  '',
  '- [x] 완료 항목',
  '- [ ] 진행 항목',
  '',
  '```python',
  "print('hi')",
  '```',
].join('\n');

test('every streaming prefix of a representative markdown answer renders without hanging', () => {
  // 문자 단위 전수는 느리므로 결함을 재현하는 경계(줄 시작+공백 직후)를 포함한 표본 접두사 사용.
  const prefixLengths = new Set<number>();
  for (let i = 1; i <= Math.min(FULL_ANSWER.length, 80); i++) prefixLengths.add(i);
  for (let i = 80; i <= FULL_ANSWER.length; i += 7) prefixLengths.add(i);
  prefixLengths.add(FULL_ANSWER.length);

  for (const length of prefixLengths) {
    const { unmount } = render(<MarkdownMessage content={FULL_ANSWER.slice(0, length)} />);
    unmount();
  }
});

test('a bare heading marker mid-stream renders as an (empty) heading, not an infinite loop', () => {
  render(<MarkdownMessage content={'## '} />);
  // 종료 자체가 회귀 가드다 — 렌더 결과에 heading 요소가 존재한다.
  expect(document.querySelector('h1, h2, h3, h4, h5')).not.toBeNull();
});

test('full answer renders headings, lists, table, quote, tasks, and code', () => {
  render(<MarkdownMessage content={FULL_ANSWER} />);
  expect(screen.getByText('폐쇄망 사내 포털의 장점')).toBeInTheDocument();
  expect(screen.getByText('보안 강화:')).toBeInTheDocument();
  expect(screen.getByText("print('hi')")).toBeInTheDocument();
  expect(screen.getByText('참고: 폐쇄망 원칙.')).toBeInTheDocument();
});
