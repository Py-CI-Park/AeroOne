import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { VersionBadge } from '@/components/layout/version-badge';
import { APP_CONTACT, APP_VERSION, CHANGELOG } from '@/lib/changelog';

test('shows the current version label and hides the dialog initially', () => {
  render(<VersionBadge />);

  expect(screen.getByRole('button', { name: `v${APP_VERSION}` })).toBeInTheDocument();
  expect(screen.queryByTestId('version-dialog')).not.toBeInTheDocument();
});

test('tracks the current 1.6.2 release in the dashboard header', () => {
  expect(APP_VERSION).toBe('1.6.2');
});

test('opens the changelog dialog with latest entry and contact info on click', () => {
  render(<VersionBadge />);

  fireEvent.click(screen.getByRole('button', { name: `v${APP_VERSION}` }));

  expect(screen.getByTestId('version-dialog')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '업데이트 내역' })).toBeInTheDocument();
  // 최신 릴리스의 첫 항목 본문이 보인다.
  expect(screen.getByText(CHANGELOG[0].items[0])).toBeInTheDocument();
  // 문의 정보는 이름만 노출(이메일/링크 없음).
  expect(screen.getByText('문의:')).toBeInTheDocument();
  expect(screen.getByText(APP_CONTACT.name, { exact: false })).toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

test('closes the dialog with a close control', () => {
  render(<VersionBadge />);

  fireEvent.click(screen.getByRole('button', { name: `v${APP_VERSION}` }));
  expect(screen.getByTestId('version-dialog')).toBeInTheDocument();

  // 헤더의 X 와 하단 버튼 둘 다 "닫기" — 아무거나 누르면 닫힌다.
  fireEvent.click(screen.getAllByRole('button', { name: '닫기' })[0]);
  expect(screen.queryByTestId('version-dialog')).not.toBeInTheDocument();
});
