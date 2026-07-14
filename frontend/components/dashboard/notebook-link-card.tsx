'use client';

import { useEffect, useState } from 'react';

import { ServiceCard } from '@/components/dashboard/service-card';
import type { ServiceModule } from '@/lib/types';

// Reserved external launcher kinds. Each is a fixed same-host co-deploy port; the frontend
// resolves the destination itself from window.location — a ServiceModule row (or any degraded
// fallback data) can never redirect a reserved launcher to an arbitrary origin, even if its
// `href` column is populated. Unknown/unsupported kinds (including the 'none' default) fail
// closed: no link is ever rendered for them here.
export type ReservedLauncherKind = Exclude<ServiceModule['launcher_kind'], 'none'>;

const RESERVED_LAUNCHER_PORTS: Record<ReservedLauncherKind, number> = {
  open_notebook: 8502,
  open_webui: 8080,
};

function isReservedLauncherKind(value: unknown): value is ReservedLauncherKind {
  return value === 'open_notebook' || value === 'open_webui';
}

// window.location.hostname is a bare hostname/IPv4, or an already-bracketed IPv6 literal
// (e.g. "[::1]") per the WHATWG URL spec. Defensively bracket any unbracketed IPv6 literal
// (contains ":") before composing the URL so `new URL()`/browsers always parse it as a host,
// not host:port.
function formatHost(host: string): string {
  if (host.includes(':') && !host.startsWith('[')) {
    return `[${host}]`;
  }
  return host;
}

export function ExternalLauncherCard({
  title,
  description,
  badge,
  launcherKind,
  active = true,
}: {
  title: string;
  description?: string;
  badge: string;
  launcherKind: ServiceModule['launcher_kind'];
  active?: boolean;
}) {
  // undefined = not yet hydrated (SSR has no window). Distinct from a resolved empty string so
  // the pre-hydration render is unambiguous.
  const [host, setHost] = useState<string | undefined>(undefined);
  const [isSecureContext, setIsSecureContext] = useState(false);

  useEffect(() => {
    setHost(window.location.hostname);
    setIsSecureContext(window.location.protocol === 'https:');
  }, []);

  if (!isReservedLauncherKind(launcherKind)) {
    // Fail closed: an unknown or 'none' launcher kind never gets a clickable external link,
    // regardless of what is_external/href say.
    return (
      <ServiceCard title={title} description={description} href="#" badge={badge} active={false} external />
    );
  }

  // SSR-safe disabled placeholder: server markup has no window, so it renders inert until the
  // client hydrates and resolves the real hostname. This also avoids a hydration mismatch (the
  // SSR href would otherwise differ from the client href).
  if (host === undefined) {
    return (
      <ServiceCard title={title} description={description} href="#" badge={badge} active={false} external />
    );
  }

  // Production HTTPS must never downgrade to a plain-http launcher: these reserved co-deploy
  // ports have no approved HTTPS destination configured, so under an https:// page the launcher
  // stays disabled instead of emitting a mixed-content http:// link.
  if (isSecureContext) {
    return (
      <ServiceCard title={title} description={description} href="#" badge={badge} active={false} external />
    );
  }

  const port = RESERVED_LAUNCHER_PORTS[launcherKind];
  const targetHref = `http://${formatHost(host)}:${port}`;

  return (
    <ServiceCard
      title={title}
      description={description}
      href={targetHref}
      badge={badge}
      active={active}
      external
    />
  );
}

// Backward-compatible alias: Open Notebook was the sole reserved launcher before v1.14.0.
export function NotebookLinkCard({
  title,
  description,
  badge,
  active = true,
}: {
  title: string;
  description?: string;
  badge: string;
  active?: boolean;
}) {
  return (
    <ExternalLauncherCard title={title} description={description} badge={badge} launcherKind="open_notebook" active={active} />
  );
}
