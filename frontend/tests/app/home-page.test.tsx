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

  expect(screen.getByRole('link', { name: /뉴스레터 서비스/i })).toHaveAttribute(
    'href',
    '/newsletters',
  );
});
