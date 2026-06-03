'use client';

import { useEffect } from 'react';

import { recordNewsletterRead } from '@/lib/api';

// 독자가 본문을 열면 읽음 비콘을 1회 발화한다. 같은 브라우저 세션에서 같은 글을
// 다시 렌더해도 sessionStorage 가드로 중복 발화하지 않는다(서버도 30분 디바운스로
// 흡수하지만 클라이언트 폭주를 먼저 막는다). 렌더 출력은 없다.
export function ReadBeacon({ newsletterId }: { newsletterId: number }) {
  useEffect(() => {
    if (!newsletterId) {
      return;
    }
    const key = `read:${newsletterId}`;
    try {
      if (sessionStorage.getItem(key)) {
        return;
      }
      sessionStorage.setItem(key, '1');
    } catch {
      // sessionStorage 를 쓸 수 없는 환경은 가드 없이 1회 기록을 시도한다.
    }
    recordNewsletterRead(newsletterId);
  }, [newsletterId]);

  return null;
}
