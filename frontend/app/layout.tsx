import './globals.css';

import { ReactNode } from 'react';
import Script from 'next/script';

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

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Script id="extension-hydration-guard" strategy="beforeInteractive">
          {EXTENSION_HYDRATION_GUARD}
        </Script>
        {children}
      </body>
    </html>
  );
}
