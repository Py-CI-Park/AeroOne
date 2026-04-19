import React from 'react';
import { render, screen } from '@testing-library/react';

import { ServiceCard } from '@/components/dashboard/service-card';

it('renders a service dashboard card without an icon', () => {
  render(
    <ServiceCard
      title="Newsletter"
      href="/newsletters"
      badge="활성 서비스"
    />,
  );

  const card = screen.getByRole('link', { name: /Newsletter/i });

  expect(card).toBeInTheDocument();
  expect(card).toHaveAttribute('href', '/newsletters');
  expect(card).not.toHaveTextContent('Open the latest issue and browse previous issues by date.');
  expect(screen.getByText('활성 서비스')).toBeInTheDocument();
  expect(screen.queryByTestId('service-card-description')).not.toBeInTheDocument();
  expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
});

it('renders a description when one is provided', () => {
  render(
    <ServiceCard
      title="문서"
      description="문서 설명"
      href="/docs"
      badge="활성 서비스"
    />,
  );

  expect(screen.getByTestId('service-card-description')).toHaveTextContent('문서 설명');
});

it('still renders a service dashboard card with an icon when provided', () => {
  render(
    <ServiceCard
      title="뉴스레터 서비스"
      description="최신 뉴스레터를 바로 확인합니다."
      href="/newsletters"
      badge="활성 서비스"
      icon="문서"
    />,
  );

  const card = screen.getByRole('link', { name: /뉴스레터 서비스/i });

  expect(card).toHaveTextContent('문서');
  expect(screen.getByTestId('service-card-icon')).toHaveTextContent('문서');
  expect(screen.getByText('활성 서비스')).toBeInTheDocument();
});
