import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders compact sun and moon links without slug', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const light = screen.getByRole('link', { name: '라이트 테마' });
  const dark = screen.getByRole('link', { name: '다크 테마' });

  expect(selector).toBeInTheDocument();
  expect(selector).not.toHaveTextContent('화면 테마 선택');
  expect(selector).not.toHaveTextContent('Light');
  expect(selector).not.toHaveTextContent('Dark');
  expect(light).toHaveTextContent('☀');
  expect(dark).toHaveTextContent('☾');
  expect(light).toHaveAttribute('href', '/newsletters?theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?theme=dark');
  expect(light).toHaveAttribute('aria-current', 'true');
  expect(dark).not.toHaveAttribute('aria-current');
});

test('preserves slug in compact theme links', () => {
  render(<NewsletterThemeSelector theme="dark" slug="newsletter-20260330" />);

  const light = screen.getByRole('link', { name: '라이트 테마' });
  const dark = screen.getByRole('link', { name: '다크 테마' });

  expect(light).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=dark');
  expect(dark).toHaveAttribute('aria-current', 'true');
});
