import React from 'react';
import { render, screen } from '@testing-library/react';

import { ServiceCard } from '@/components/dashboard/service-card';

it('renders a service dashboard card', () => {
  render(
    <ServiceCard
      title="뉴스레터 서비스"
      description="최신 뉴스레터를 바로 확인합니다."
      href="/newsletters"
      badge="활성 서비스"
      icon="📰"
    />,
  );

  expect(screen.getByRole('link', { name: /뉴스레터 서비스/i })).toBeInTheDocument();
  expect(screen.getByText('활성 서비스')).toBeInTheDocument();
});
