// AeroOne — 인라인 SVG 아이콘 세트 (Claude Design 핸드오프 이식).
// 모두 currentColor 사용 — 부모의 color/Tailwind text-* 로 색 제어. 외부 의존 0.
import React from 'react';

type IconProps = {
  size?: number;
  className?: string;
  'aria-hidden'?: boolean;
};

function svg(
  node: React.ReactNode,
  { viewBox = '0 0 16 16', defaultSize = 14 }: { viewBox?: string; defaultSize?: number } = {},
) {
  return function IconComponent({ size, className, ...rest }: IconProps) {
    return (
      <svg
        viewBox={viewBox}
        width={size ?? defaultSize}
        height={size ?? defaultSize}
        fill="none"
        aria-hidden
        focusable={false}
        className={className}
        {...rest}
      >
        {node}
      </svg>
    );
  };
}

const sw = 'currentColor';

export const Icon = {
  logo: svg(
    <>
      <path d="M4 18L11 4L18 18" stroke={sw} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M7.5 12H14.5" stroke={sw} strokeWidth="1.6" strokeLinecap="round" />
    </>,
    { viewBox: '0 0 24 24', defaultSize: 16 },
  ),
  search: svg(
    <>
      <circle cx="7" cy="7" r="4.5" stroke={sw} strokeWidth="1.3" />
      <path d="M10.5 10.5L13.5 13.5" stroke={sw} strokeWidth="1.3" strokeLinecap="round" />
    </>,
  ),
  cal: svg(
    <>
      <rect x="2.5" y="3.5" width="11" height="10" rx="1" stroke={sw} strokeWidth="1.2" />
      <path d="M2.5 6.5H13.5" stroke={sw} strokeWidth="1.2" />
      <path d="M5.5 2V5M10.5 2V5" stroke={sw} strokeWidth="1.2" strokeLinecap="round" />
    </>,
  ),
  tag: svg(
    <>
      <path d="M2.5 2.5H8L13.5 8L8 13.5L2.5 8V2.5Z" stroke={sw} strokeWidth="1.2" strokeLinejoin="round" />
      <circle cx="5.5" cy="5.5" r="0.9" fill={sw} />
    </>,
  ),
  sun: svg(
    <>
      <circle cx="8" cy="8" r="2.8" stroke={sw} strokeWidth="1.3" />
      <path
        d="M8 1.5V3M8 13V14.5M1.5 8H3M13 8H14.5M3.4 3.4L4.4 4.4M11.6 11.6L12.6 12.6M3.4 12.6L4.4 11.6M11.6 4.4L12.6 3.4"
        stroke={sw}
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </>,
  ),
  moon: svg(
    <path
      d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5Z"
      stroke={sw}
      strokeWidth="1.3"
      strokeLinejoin="round"
    />,
  ),
  chevR: svg(
    <path d="M6 3L11 8L6 13" stroke={sw} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
    { defaultSize: 12 },
  ),
  chevL: svg(
    <path d="M10 3L5 8L10 13" stroke={sw} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
    { defaultSize: 12 },
  ),
  chevD: svg(
    <path d="M3 6L8 11L13 6" stroke={sw} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
    { defaultSize: 12 },
  ),
  doc: svg(
    <>
      <path d="M3.5 1.5H9.5L12.5 4.5V14.5H3.5V1.5Z" stroke={sw} strokeWidth="1.2" strokeLinejoin="round" />
      <path d="M9.5 1.5V4.5H12.5" stroke={sw} strokeWidth="1.2" strokeLinejoin="round" />
      <path d="M5.5 8H10.5M5.5 10.5H10.5M5.5 12.5H8.5" stroke={sw} strokeWidth="1.2" strokeLinecap="round" />
    </>,
  ),
  dot: svg(<circle cx="4" cy="4" r="3" fill={sw} />, { viewBox: '0 0 8 8', defaultSize: 8 }),
  download: svg(
    <>
      <path d="M8 2.5V10M4.5 6.5L8 10L11.5 6.5" stroke={sw} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2.5 12V13.5H13.5V12" stroke={sw} strokeWidth="1.3" strokeLinecap="round" />
    </>,
  ),
  external: svg(
    <>
      <path d="M6 3H3v10h10v-3" stroke={sw} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 3h4v4M13 3L8 8" stroke={sw} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    { defaultSize: 12 },
  ),
  list: svg(
    <path d="M2.5 4h11M2.5 8h11M2.5 12h11" stroke={sw} strokeWidth="1.3" strokeLinecap="round" />,
  ),
  grid: svg(
    <>
      <rect x="2.5" y="2.5" width="5" height="5" rx="0.5" stroke={sw} strokeWidth="1.2" />
      <rect x="8.5" y="2.5" width="5" height="5" rx="0.5" stroke={sw} strokeWidth="1.2" />
      <rect x="2.5" y="8.5" width="5" height="5" rx="0.5" stroke={sw} strokeWidth="1.2" />
      <rect x="8.5" y="8.5" width="5" height="5" rx="0.5" stroke={sw} strokeWidth="1.2" />
    </>,
  ),
  x: svg(<path d="M4 4L12 12M12 4L4 12" stroke={sw} strokeWidth="1.4" strokeLinecap="round" />, { defaultSize: 12 }),
  lock: svg(
    <>
      <rect x="3" y="7" width="10" height="7" rx="1" stroke={sw} strokeWidth="1.2" />
      <path d="M5 7V5a3 3 0 0 1 6 0v2" stroke={sw} strokeWidth="1.2" />
    </>,
  ),
} satisfies Record<string, React.ComponentType<IconProps>>;

export type IconName = keyof typeof Icon;
