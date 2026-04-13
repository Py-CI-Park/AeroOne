import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders light and dark links without slug', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const light = screen.getByRole('link', { name: 'Light' });
  const dark = screen.getByRole('link', { name: 'Dark' });

  expect(selector).toBeInTheDocument();
  expect(light).toHaveAttribute('href', '/newsletters?theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?theme=dark');
  expect(light).toHaveAttribute('aria-current', 'true');
  expect(dark).not.toHaveAttribute('aria-current');
});

test('preserves slug in theme links', () => {
  render(<NewsletterThemeSelector theme="dark" slug="newsletter-20260330" />);

  const light = screen.getByRole('link', { name: 'Light' });
  const dark = screen.getByRole('link', { name: 'Dark' });

  expect(light).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=dark');
  expect(dark).toHaveAttribute('aria-current', 'true');
});
