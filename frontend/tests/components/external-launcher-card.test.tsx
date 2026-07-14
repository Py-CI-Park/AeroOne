import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ExternalLauncherCard, NotebookLinkCard } from '@/components/dashboard/notebook-link-card';

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

afterEach(() => {
  setLocation({});
});

test('resolves an open_notebook launcher to the current browser host on port 8502', () => {
  setLocation({ hostname: 'workstation-07' });

  render(
    <ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />,
  );

  const link = screen.getByRole('link', { name: /Notebook/i });
  expect(link).toHaveAttribute('href', 'http://workstation-07:8502');
});

test('resolves an open_webui launcher to the current browser host on port 8080', () => {
  setLocation({ hostname: 'workstation-07' });

  render(
    <ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />,
  );

  const link = screen.getByRole('link', { name: /OpenWebUI/i });
  expect(link).toHaveAttribute('href', 'http://workstation-07:8080');
});

test('preserves an already-bracketed IPv6 hostname as-is', () => {
  setLocation({ hostname: '[fe80::1]' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  expect(screen.getByRole('link', { name: /OpenWebUI/i })).toHaveAttribute('href', 'http://[fe80::1]:8080');
});

test('defensively brackets an unbracketed IPv6 hostname', () => {
  setLocation({ hostname: '::1' });

  render(<ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />);

  expect(screen.getByRole('link', { name: /Notebook/i })).toHaveAttribute('href', 'http://[::1]:8502');
});

test('sets target=_blank and rel=noopener noreferrer for reserved launchers', () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />);

  const link = screen.getByRole('link', { name: /Notebook/i });
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
});

test('disables the launcher under an https page instead of downgrading to a plain-http destination', () => {
  setLocation({ hostname: 'aeroone.internal', protocol: 'https:' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />);

  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
  expect(screen.getByText('OpenWebUI').closest('[aria-disabled="true"]')).not.toBeNull();
});

test('respects an inactive module by rendering a disabled card instead of a link', () => {
  setLocation({ hostname: 'localhost' });

  render(<ExternalLauncherCard title="OpenWebUI" badge="Coming soon" launcherKind="open_webui" active={false} />);

  expect(screen.queryByRole('link', { name: /OpenWebUI/i })).not.toBeInTheDocument();
});

test('Notebook and OpenWebUI launchers resolve to independent hosts/ports and can coexist', () => {
  setLocation({ hostname: 'lan-pc-3' });

  render(
    <>
      <ExternalLauncherCard title="Notebook" badge="Active" launcherKind="open_notebook" />
      <ExternalLauncherCard title="OpenWebUI" badge="Active" launcherKind="open_webui" />
    </>,
  );

  expect(screen.getByRole('link', { name: /Notebook/i })).toHaveAttribute('href', 'http://lan-pc-3:8502');
  expect(screen.getByRole('link', { name: /OpenWebUI/i })).toHaveAttribute('href', 'http://lan-pc-3:8080');
});

test('never renders a fetch/health/proxy affordance — the launcher is a plain external anchor only', () => {
  setLocation({ hostname: 'localhost' });

  const { container } = render(
    <ExternalLauncherCard title="OpenWebUI" description="Ollama 호환 챗 UI" badge="Active" launcherKind="open_webui" />,
  );

  expect(container.querySelectorAll('button')).toHaveLength(0);
  expect(container.querySelectorAll('form')).toHaveLength(0);
});

test('NotebookLinkCard remains a backward-compatible alias bound to open_notebook on 8502', () => {
  setLocation({ hostname: 'localhost' });

  render(<NotebookLinkCard title="Notebook" description="NotebookLM 대안" badge="Active" />);

  const link = within(screen.getByRole('link', { name: /Notebook/i }));
  expect(link.getByTestId('service-card-description')).toHaveTextContent('NotebookLM 대안');
  expect(screen.getByRole('link', { name: /Notebook/i })).toHaveAttribute('href', 'http://localhost:8502');
});
