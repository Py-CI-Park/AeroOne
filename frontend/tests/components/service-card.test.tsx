import React from 'react';
import { render, screen } from '@testing-library/react';

import { ServiceCard } from '@/components/dashboard/service-card';

it('renders a service dashboard card without an icon', () => {
  render(
    <ServiceCard
      title="뉴스레터 서비스"
      description="최신 뉴스레터를 바로 확인합니다."
      href="/newsletters"
      badge="활성 서비스"
    />,
  );

  const card = screen.getByRole('link', { name: /뉴스레터 서비스/i });

  expect(card).toBeInTheDocument();
  expect(card).toHaveAttribute('href', '/newsletters');
  expect(screen.getByText('활성 서비스')).toBeInTheDocument();
  expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
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
