import './globals.css';

import { ReactNode } from 'react';
import { cookies } from 'next/headers';
import Script from 'next/script';

import { NEWSLETTER_THEME_COOKIE, resolveNewsletterTheme } from '@/lib/theme';

const EXTENSION_HYDRATION_GUARD = `
(() => {
  const selectors = ['#__endic_crx__', '[data-wxt-integrated]'];

  const clean = () => {
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach((node) => {
        if (node instanceof HTMLElement) {
          node.remove();
        }
      });
    }
  };

  clean();
  document.addEventListener('DOMContentLoaded', clean, { once: true });

  let attempts = 0;
  const timer = window.setInterval(() => {
    clean();
    attempts += 1;
    if (attempts >= 40) {
      window.clearInterval(timer);
    }
  }, 50);
})();
`;

export const metadata = {
  title: {
    default: 'AeroOne',
    template: '%s | AeroOne',
  },
  description: 'AeroOne 사내 뉴스레터 / 문서 플랫폼',
  icons: {
    icon: '/icon.svg',
    shortcut: '/icon.svg',
    apple: '/icon.svg',
  },
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // 테마는 쿠키 한 곳을 진실 소스로 삼아 <html> 에 1회 부착한다.
  // 페이지별 data-theme 는 클라이언트 라우터 캐시로 stale 해질 수 있어 여기로 올린다.
  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;
  const theme = resolveNewsletterTheme(cookieTheme ?? process.env.NEWSLETTERS_THEME);

  return (
    <html lang="ko" data-theme={theme} suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Script id="extension-hydration-guard" strategy="beforeInteractive">
          {EXTENSION_HYDRATION_GUARD}
        </Script>
        {children}
      </body>
    </html>
  );
}
