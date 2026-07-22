import Link from 'next/link';

import { Icon } from '@/components/ui/icons';
import type { DashboardAuth } from '@/lib/server-auth';
import type { ServiceModule } from '@/lib/types';

const FEATURED_KEYS = ['civil-aircraft', 'ai', 'aero-work', 'newsletter'] as const;
const FEATURED_LABELS: Record<(typeof FEATURED_KEYS)[number], string> = {
  'civil-aircraft': '민수기체 빠른 실행',
  ai: '문서 AI 빠른 실행',
  'aero-work': '업무 공간 빠른 실행',
  newsletter: '뉴스레터 빠른 실행',
};

type CinematicHeroProps = {
  modules: ServiceModule[];
  auth: DashboardAuth;
  activeCount: number;
  comingCount: number;
};

export function CinematicHero({ modules, auth, activeCount, comingCount }: CinematicHeroProps) {
  const featuredModules = FEATURED_KEYS.flatMap((key) =>
    modules.filter((module) => module.key === key && module.is_enabled && !module.is_external),
  ).slice(0, 4);

  const greeting = !auth.authenticated
    ? 'AeroOne의 문서와 업무 서비스를 한곳에서 확인하세요.'
    : auth.isAdmin
      ? `${auth.username ?? '운영자'}님, 서비스 운영 현황을 확인하세요.`
      : `${auth.username ?? '사용자'}님, 업무를 이어가세요.`;

  return (
    <section className="cinematic-hero" aria-labelledby="cinematic-hero-title">
      <div
        aria-hidden="true"
        className="cinematic-hero__poster"
        style={{ backgroundImage: "url('/media/aeroone-flight-deck.webp')" }}
      />
      <div className="cinematic-hero__content">
        <div className="max-w-2xl">
          <p className="cinematic-hero__eyebrow">AeroOne flight deck</p>
          <h1 id="cinematic-hero-title" className="cinematic-hero__title">{greeting}</h1>
          <p className="cinematic-hero__count">{activeCount} active · {comingCount} coming soon</p>
          {!auth.authenticated ? (
            <Link href="/login" aria-label="AeroOne 로그인" className="cinematic-hero__cta">
              로그인
            </Link>
          ) : null}
        </div>

        {featuredModules.length > 0 ? (
          <section className="cinematic-hero__featured" aria-labelledby="featured-services-title">
            <div className="cinematic-hero__featured-heading">
              <h2 id="featured-services-title">Featured</h2>
              <span>권한에 맞는 빠른 시작</span>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {featuredModules.map((module) => (
                <Link
                  key={module.key}
                  href={module.href}
                  aria-label={FEATURED_LABELS[module.key as keyof typeof FEATURED_LABELS]}
                  className="cinematic-hero__featured-card"
                >
                  <span className="cinematic-hero__featured-icon" aria-hidden="true">
                    <Icon.doc size={15} />
                  </span>
                  <span className="cinematic-hero__featured-title">{module.title}</span>
                  {module.description ? (
                    <span className="cinematic-hero__featured-description">{module.description}</span>
                  ) : null}
                  <span className="cinematic-hero__featured-open">
                    Open <Icon.chevR size={11} />
                  </span>
                </Link>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}
