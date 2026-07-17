import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ExternalLauncherCard, NotebookLinkCard } from '@/components/dashboard/notebook-link-card';

const { fetchLauncherHealthMock } = vi.hoisted(() => ({ fetchLauncherHealthMock: vi.fn() }));

vi.mock('@/lib/api', () => ({ fetchLauncherHealth: fetchLauncherHealthMock }));

function health(status: 'ready' | 'starting' | 'absent' | 'error', overrides: Partial<Record<string, unknown>> = {}) {
  return {
    status,
    port: 8080,
    probe_target: '127.0.0.1:8080',
    checked_at: '2026-07-17T00:00:00Z',
    latency_ms: status === 'ready' ? 12 : null,
    detail: `detail:${status}`,
    ...overrides,
  };
}

// 링크 포트의 단일 원천은 헬스 페이로드다 — kind 별 실제 기본 포트로 응답해야
// 카드 href 단언(8502/8080)이 실제 계약(백엔드 port 반영)을 검증한다.
const KIND_PORTS: Record<string, number> = { open_notebook: 8502, open_webui: 8080 };

function mockHealthPerKind(status: 'ready' | 'starting' | 'absent' | 'error' = 'ready') {
  fetchLauncherHealthMock.mockImplementation((kind: string) => Promise.resolve(
    health(status, { port: KIND_PORTS[kind] ?? 8080, probe_target: `127.0.0.1:${KIND_PORTS[kind] ?? 8080}` }),
  ));
}

const READY = health('ready');

function setLocation(overrides: Partial<Location>) {
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      hostname: 'localhost',
      protocol: 'http:',
      ...overrides,
    },
    writable: true,
  });
}

beforeEach(() => {
  fetchLauncherHealthMock.mockReset();
  mockHealthPerKind('ready');
});

afterEach(() => {
  setLocation({});
});

test('resolves an open_notebook launcher to the current browser host on port 8502', async () => {
  setLocation({ hostname: 'workstation-07' });

  render(
    <ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />,
  );

  const link = await screen.findByRole('link', { name: /Notebook/i });
  expect(link).toHaveAttribute('href', 'http://workstation-07:8502');
});

test('resolves an open_webui launcher to the current browser host on port 8080', async () => {
  setLocation({ hostname: 'workstation-07' });

  render(
    <ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />,
  );

  const link = await screen.findByRole('link', { name: /OpenWebUI/i });
  expect(link).toHaveAttribute('href', 'http://workstation-07:8080');
});

test('preserves an already-bracketed IPv6 hostname as-is', async () => {
  setLocation({ hostname: '[fe80::1]' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  await waitFor(() =>
    expect(screen.getByRole('link', { name: /OpenWebUI/i })).toHaveAttribute('href', 'http://[fe80::1]:8080'),
  );
});

test('defensively brackets an unbracketed IPv6 hostname', async () => {
  setLocation({ hostname: '::1' });

  render(<ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />);

  await waitFor(() =>
    expect(screen.getByRole('link', { name: /Notebook/i })).toHaveAttribute('href', 'http://[::1]:8502'),
  );
});

test('sets target=_blank and rel=noopener noreferrer for reserved launchers', async () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />);

  const link = await screen.findByRole('link', { name: /Notebook/i });
  expect(link).toHaveAttribute('target', '_blank');
  expect(link).toHaveAttribute('rel', 'noopener noreferrer');
});

test('renders an inert, hydration-safe placeholder during SSR (no window, no leaked href/target)', () => {
  const html = renderToStaticMarkup(
    <ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />,
  );

  expect(html).not.toContain('http://');
  expect(html).not.toContain('_blank');
  expect(html).toContain('aria-disabled');
});

test('fails closed for the "none" launcher kind: no link, no fetch/health/proxy affordance', () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="Untagged" badge="Active" launcherKind="none" />);

  expect(screen.queryByRole('link', { name: /Untagged/i })).not.toBeInTheDocument();
  expect(screen.getByText('Untagged').closest('[aria-disabled="true"]')).not.toBeNull();
  expect(fetchLauncherHealthMock).not.toHaveBeenCalled();
});

test('fails closed for an unrecognized launcher kind value', () => {
  setLocation({ hostname: 'localhost' });

  render(
    <ExternalLauncherCard
      title="Mystery"
      badge="Active"
      launcherKind={'totally-unknown' as unknown as 'none'}
    />,
  );

  expect(screen.queryByRole('link', { name: /Mystery/i })).not.toBeInTheDocument();
  expect(fetchLauncherHealthMock).not.toHaveBeenCalled();
});

test('disables the launcher under an https page instead of downgrading to a plain-http destination', async () => {
  setLocation({ hostname: 'aeroone.internal', protocol: 'https:' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
  expect(screen.getByText('OpenWebUI').closest('[aria-disabled="true"]')).not.toBeNull();
  await waitFor(() => expect(fetchLauncherHealthMock).toHaveBeenCalledWith('open_webui'));
});

test('respects an inactive module by rendering a disabled card instead of a link', () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Coming soon" launcherKind="open_webui" active={false} />);

  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
  expect(fetchLauncherHealthMock).not.toHaveBeenCalled();
});

test('Notebook and OpenWebUI launchers resolve to independent hosts/ports and can coexist', async () => {
  setLocation({ hostname: 'lan-pc-3' });

  render(
    <>
      <ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />
      <ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />
    </>,
  );

  await waitFor(() =>
    expect(screen.getByRole('link', { name: /Notebook/i })).toHaveAttribute('href', 'http://lan-pc-3:8502'),
  );
  expect(screen.getByRole('link', { name: /OpenWebUI/i })).toHaveAttribute('href', 'http://lan-pc-3:8080');
});

test('never renders a fetch/health/proxy affordance — the launcher is a plain external anchor only', async () => {
  setLocation({ hostname: 'localhost' });

  const { container } = render(
    <ExternalLauncherCard title="OpenWebUI" description="Ollama 호환 챗 UI" badge="Active" launcherKind="open_webui" />,
  );

  await screen.findByRole('link', { name: /OpenWebUI/i });
  expect(container.querySelectorAll('button')).toHaveLength(0);
  expect(container.querySelectorAll('form')).toHaveLength(0);
});

test('NotebookLinkCard remains a backward-compatible alias bound to open_notebook on 8502', async () => {
  setLocation({ hostname: 'localhost' });

  render(<NotebookLinkCard title="Notebook" description="NotebookLM 대안" badge="Active" />);

  const link = await screen.findByRole('link', { name: /Notebook/i });
  expect(within(link).getByTestId('service-card-description')).toHaveTextContent('NotebookLM 대안');
  expect(link).toHaveAttribute('href', 'http://localhost:8502');
});

// --- Health badge / disabled-until-ready behavior (G004 슬라이스 A) ---

test('shows a 구동 중 badge and an enabled link when the health probe reports ready', async () => {
  setLocation({ hostname: 'localhost' });
  fetchLauncherHealthMock.mockResolvedValue(READY);

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  await waitFor(() => expect(screen.getByText('구동 중')).toBeInTheDocument());
  expect(screen.getByRole('link', { name: /OpenWebUI/i })).toHaveAttribute('href', 'http://localhost:8080');
});

test('shows a 기동 중 badge and disables the card (no link) when the health probe reports starting', async () => {
  setLocation({ hostname: 'localhost' });
  fetchLauncherHealthMock.mockResolvedValue(health('starting'));

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  await waitFor(() => expect(screen.getByText('기동 중')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
  expect(screen.getByText('detail:starting')).toBeInTheDocument();
});

test('shows a 미설치 · 미구동 badge and disables the card when the health probe reports absent', async () => {
  setLocation({ hostname: 'localhost' });
  fetchLauncherHealthMock.mockResolvedValue(health('absent'));

  render(<ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /Notebook/i })).not.toBeInTheDocument();
});

test('shows a 확인 실패 badge, reason text, and a disabled card when the health fetch rejects', async () => {
  setLocation({ hostname: 'localhost' });
  fetchLauncherHealthMock.mockRejectedValue(new Error('network down'));

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  await waitFor(() => expect(screen.getByText('확인 실패')).toBeInTheDocument());
  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
});

test('does not query health or render a badge for an inactive (coming-soon) module', () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Coming soon" launcherKind="open_webui" active={false} />);

  expect(screen.queryByText('구동 중')).not.toBeInTheDocument();
  expect(screen.queryByText('기동 중')).not.toBeInTheDocument();
  expect(screen.queryByText('미설치 · 미구동')).not.toBeInTheDocument();
  expect(fetchLauncherHealthMock).not.toHaveBeenCalled();
});

test('never renders an actual <button>/<form> affordance even when the card is disabled by health', async () => {
  setLocation({ hostname: 'localhost' });
  fetchLauncherHealthMock.mockResolvedValue(health('absent'));

  const { container } = render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  await waitFor(() => expect(screen.getByText('미설치 · 미구동')).toBeInTheDocument());
  expect(container.querySelectorAll('button')).toHaveLength(0);
  expect(container.querySelectorAll('form')).toHaveLength(0);
});
