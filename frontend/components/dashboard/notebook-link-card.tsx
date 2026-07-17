'use client';

import { useEffect, useState } from 'react';

import { ServiceCard } from '@/components/dashboard/service-card';
import { fetchLauncherHealth } from '@/lib/api';
import type { LauncherHealth, ServiceModule } from '@/lib/types';

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

type HealthPhase = 'checking' | 'ready' | 'starting' | 'absent' | 'error';

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
  const [healthPhase, setHealthPhase] = useState<HealthPhase>('checking');
  const [health, setHealth] = useState<LauncherHealth | null>(null);

  useEffect(() => {
    setHost(window.location.hostname);
    setIsSecureContext(window.location.protocol === 'https:');
  }, []);

  const reserved = isReservedLauncherKind(launcherKind);

  // Health polling is scoped to reserved kinds on active cards only — an inactive (coming-soon)
  // module or an unknown/unsupported kind never triggers a backend probe.
  useEffect(() => {
    if (!reserved || !active) {
      return undefined;
    }
    let cancelled = false;
    setHealthPhase('checking');
    fetchLauncherHealth(launcherKind as ReservedLauncherKind)
      .then((result) => {
        if (cancelled) return;
        setHealth(result);
        setHealthPhase(result.status);
      })
      .catch(() => {
        if (cancelled) return;
        setHealth(null);
        setHealthPhase('error');
      });
    return () => {
      cancelled = true;
    };
  }, [reserved, active, launcherKind]);

  if (!reserved) {
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
  // Only a 'ready' health probe unlocks the click-through — a dead link that opens a blank tab
  // for a not-yet-started co-deploy app is worse than a disabled card with a reason.
  const cardActive = active && healthPhase === 'ready';

  return (
    <div className="flex flex-col gap-2">
      <ServiceCard
        title={title}
        description={description}
        href={targetHref}
        badge={badge}
        active={cardActive}
        external
      />
      {active && (
        <div className="flex flex-wrap items-center gap-2 px-1" data-testid={`launcher-health-${launcherKind}`}>
          <LauncherHealthBadge phase={healthPhase} />
          {healthPhase !== 'ready' && healthPhase !== 'checking' && health?.detail && (
            <span className="text-xs text-ink-3">{health.detail}</span>
          )}
        </div>
      )}
    </div>
  );
}

// Badge styling mirrors the Leantime co-deploy status indicator (components/office-tools/
// leantime-status.tsx) so all external co-deploy health signals read consistently.
function LauncherHealthBadge({ phase }: { phase: HealthPhase }) {
  if (phase === 'ready') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-600">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 구동 중
      </span>
    );
  }
  if (phase === 'checking') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-3/10 px-3 py-1 text-xs font-semibold text-ink-3">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-3" /> 확인 중
      </span>
    );
  }
  if (phase === 'starting') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/15 px-3 py-1 text-xs font-semibold text-sky-600">
        <span className="h-1.5 w-1.5 rounded-full bg-sky-500" /> 기동 중
      </span>
    );
  }
  if (phase === 'error') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/15 px-3 py-1 text-xs font-semibold text-rose-600">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> 확인 실패
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-3/10 px-3 py-1 text-xs font-semibold text-ink-3">
      <span className="h-1.5 w-1.5 rounded-full bg-ink-3/60" /> 미설치 · 미구동
    </span>
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
