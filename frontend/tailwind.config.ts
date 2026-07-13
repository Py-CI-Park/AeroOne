import type { Config } from 'tailwindcss';

/* AeroOne — Claude Design 핸드오프 토큰을 Tailwind 유틸리티로 노출.
 * 색/폰트/스케일/모서리/그림자는 app/globals.css 의 CSS 변수와 1:1 매핑.
 * data-theme="light|dark" 한 줄로 두 모드 전환 (변수만 스위치). */
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: 'var(--surface-base)',
          raised: 'var(--surface-raised)',
          elevated: 'var(--surface-elevated)',
          sunken: 'var(--surface-sunken)',
          overlay: 'var(--surface-overlay)',
        },
        ink: {
          1: 'var(--text-primary)',
          2: 'var(--text-secondary)',
          3: 'var(--text-tertiary)',
          4: 'var(--text-quaternary)',
          inverse: 'var(--text-inverse)',
        },
        line: {
          subtle: 'var(--border-subtle)',
          DEFAULT: 'var(--border-default)',
          strong: 'var(--border-strong)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          active: 'var(--accent-active)',
          soft: 'var(--accent-soft)',
          on: 'var(--accent-onaccent)',
        },
        ok: { DEFAULT: 'var(--ok)', soft: 'var(--ok-soft)' },
        warn: { DEFAULT: 'var(--warn)', soft: 'var(--warn-soft)' },
        danger: { DEFAULT: 'var(--danger)', soft: 'var(--danger-soft)' },
        focus: 'var(--focus-ring)',
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        serif: 'var(--font-serif)',
        mono: 'var(--font-mono)',
      },
      fontSize: {
        xs: ['12px', '16px'],
        sm: ['12px', '18px'],
        base: ['13px', '20px'],
        md: ['14px', '22px'],
        lg: ['16px', '25px'],
        xl: ['18px', '28px'],
        '2xl': ['22px', '30px'],
        '3xl': ['28px', '36px'],
        '4xl': ['34px', '42px'],
        '5xl': ['44px', '52px'],
      },
      fontWeight: {
        regular: '400',
        medium: '500',
        semibold: '600',
        bold: '700',
      },
      borderRadius: {
        none: '0',
        xs: '2px',
        sm: '3px',
        DEFAULT: '4px',
        md: '4px',
        lg: '6px',
        xl: '8px',
        full: '999px',
      },
      boxShadow: {
        xs: 'var(--sh-xs)',
        sm: 'var(--sh-sm)',
        md: 'var(--sh-md)',
        lg: 'var(--sh-lg)',
        focus: 'var(--sh-focus)',
        none: 'none',
      },
      transitionTimingFunction: {
        out: 'var(--ease-out)',
        'in-out': 'var(--ease-in-out)',
      },
      letterSpacing: {
        tightest: '-0.015em',
        tighter: '-0.01em',
        tight: '-0.005em',
        wide: '0.05em',
        wider: '0.08em',
      },
    },
  },
  plugins: [],
};

export default config;
