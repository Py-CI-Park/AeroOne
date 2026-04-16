import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders one moon icon that switches light theme to dark through cookie route', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const toggle = screen.getByRole('link', { name: '다크 테마로 전환' });

  expect(selector).toBeInTheDocument();
  expect(toggle).toHaveTextContent('☾');
  expect(toggle).toHaveAttribute('href', '/theme?theme=dark&next=%2Fnewsletters');
  expect(screen.queryByRole('link', { name: '라이트 테마로 전환' })).not.toBeInTheDocument();
});

test('renders one sun icon that switches dark theme to light and preserves current path', () => {
  render(<NewsletterThemeSelector theme="dark" currentPath="/newsletters?slug=newsletter-20260330" />);

  const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

  expect(toggle).toHaveTextContent('☀');
  expect(toggle).toHaveAttribute('href', '/theme?theme=light&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330');
  expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
});
