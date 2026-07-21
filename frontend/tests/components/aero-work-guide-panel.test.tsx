import React from 'react';
import { render, screen } from '@testing-library/react';

import { AeroWorkGuidePanel } from '@/components/aero-work/aero-work-guide-panel';

describe('AeroWorkGuidePanel', () => {
  test('사용법 패널을 data-testid와 함께 렌더한다', () => {
    render(<AeroWorkGuidePanel />);

    expect(screen.getByTestId('aero-work-guide')).toBeInTheDocument();
  });

  test('주요 사용법 섹션 제목을 렌더한다', () => {
    render(<AeroWorkGuidePanel />);

    expect(screen.getByRole('heading', { name: /처음 세팅/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '기능별 활용법' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '폐쇄망 배포 요약' })).toBeInTheDocument();
  });

  test('업무대화 일정 등록 예시를 렌더한다', () => {
    render(<AeroWorkGuidePanel />);

    expect(screen.getByText('내일 오전 10시 주간회의 일정 등록해줘')).toBeInTheDocument();
  });

  test('관리자 또는 운영자 설정에 배지를 표시한다', () => {
    render(<AeroWorkGuidePanel />);

    expect(screen.getAllByText('관리자/운영자').length).toBeGreaterThan(0);
  });
});
