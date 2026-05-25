// AeroOne — 공유 UI primitive (Tag / Btn / Thumb). Claude Design 핸드오프 이식.
// 모든 색/간격/모서리는 Tailwind 시맨틱 토큰(globals.css 변수)으로만 표현.
import React from 'react';

type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger';

const TAG_TONE: Record<Tone, string> = {
  neutral: 'bg-surface-sunken text-ink-2 border-line-subtle',
  accent: 'bg-accent-soft text-accent border-transparent',
  ok: 'bg-ok-soft text-ok border-transparent',
  warn: 'bg-warn-soft text-warn border-transparent',
  danger: 'bg-danger-soft text-danger border-transparent',
};

export function Tag({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-[7px] py-[2px] font-mono text-xs tracking-[0.02em] ${TAG_TONE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type BtnSize = 'sm' | 'md' | 'lg';

const BTN_VARIANT: Record<BtnVariant, string> = {
  primary: 'bg-accent text-accent-on border-transparent hover:bg-accent-hover active:bg-accent-active',
  secondary:
    'bg-surface-elevated text-ink-1 border-line hover:bg-surface-sunken active:border-line-strong',
  ghost: 'bg-transparent text-ink-2 border-transparent hover:bg-surface-sunken',
  danger: 'bg-transparent text-danger border-danger hover:bg-danger-soft',
};

const BTN_SIZE: Record<BtnSize, string> = {
  sm: 'px-[10px] py-[5px] text-sm',
  md: 'px-[14px] py-[7px] text-base',
  lg: 'px-[18px] py-[9px] text-md',
};

type BtnProps = {
  variant?: BtnVariant;
  size?: BtnSize;
  icon?: React.ReactNode;
  children?: React.ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

export function Btn({ variant = 'secondary', size = 'md', icon, children, className = '', ...rest }: BtnProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded border font-medium tracking-tight transition-colors duration-[120ms] ease-out focus-visible:shadow-focus focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${BTN_VARIANT[variant]} ${BTN_SIZE[size]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}

// 발행자가 채울 썸네일 자리. 폐쇄망 — 외부 이미지 X, 추상 그라데이션 placeholder.
const THUMB_PALETTES = [
  ['#3a4f63', '#6c8aa8', '#c9d5e0'],
  ['#5b4a36', '#a8967a', '#dfd4c2'],
  ['#3d4f3b', '#7a967a', '#cfdac9'],
  ['#4a3a4a', '#94808a', '#d6c8cf'],
  ['#3a3f4a', '#7c8090', '#cbd0d8'],
];

export function Thumb({
  seed = 0,
  height = 96,
  label,
  className = '',
}: {
  seed?: number;
  height?: number;
  label?: string;
  className?: string;
}) {
  const p = THUMB_PALETTES[seed % THUMB_PALETTES.length];
  return (
    <div
      className={`relative w-full overflow-hidden rounded border border-line-subtle ${className}`}
      style={{ height, background: `linear-gradient(135deg, ${p[0]} 0%, ${p[1]} 60%, ${p[2]} 100%)` }}
    >
      <div
        className="absolute inset-0"
        style={{ background: 'repeating-linear-gradient(90deg, transparent 0 6px, rgba(255,255,255,0.04) 6px 7px)' }}
      />
      {label && (
        <span className="absolute bottom-1.5 left-2 font-mono text-[10px] uppercase tracking-wide text-white/[0.78]">
          {label}
        </span>
      )}
    </div>
  );
}
