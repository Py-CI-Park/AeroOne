import React from 'react';
import { render, screen } from '@testing-library/react';

import HomePage from '@/app/page';

test('removes the home hero copy while keeping the newsletter service link', async () => {
  render(await HomePage());

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();
  expect(
    screen.queryByText(/현재는 뉴스레터 서비스부터 시작합니다/),
  ).not.toBeInTheDocument();

  const newsletterLink = screen.getByRole('link', { name: /뉴스레터 서비스/i });

  expect(newsletterLink).toHaveAttribute(
    'href',
    '/newsletters',
  );
  expect(newsletterLink).toHaveTextContent('가장 최신 뉴스레터를 바로 열고, 발행 날짜별로 이전 뉴스레터를 탐색합니다.');
  expect(newsletterLink).toHaveTextContent('활성 서비스');
  expect(newsletterLink).toHaveTextContent('📰');
  expect(newsletterLink).not.toHaveTextContent('가장 최신 뉴스레터를 바로 보고, 발행 날짜별로 이전 뉴스레터를 탐색합니다.');
  expect(newsletterLink).not.toHaveTextContent('우선 제공');
  expect(newsletterLink).not.toHaveTextContent('🗞');
});
