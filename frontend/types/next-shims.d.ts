declare module 'next';
declare module 'next/link' {
  import * as React from 'react';
  const Link: React.ComponentType<React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }>;
  export default Link;
}
declare module 'next/navigation' {
  export function redirect(path: string): never;
  export function useRouter(): { push(path: string): void };
}

declare module 'next/headers' {
  export function cookies(): { getAll(): { name: string; value: string }[] };
}
