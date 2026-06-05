// Pure frontend mini-game — no backend dependency.
// Casual coffee-bet tool: participants draw randomly for prizes (e.g. "커피" vs "꽝").
// Uses Fisher–Yates shuffle to produce a deterministic bijection given a fixed rng.
'use client';

import React, { useState } from 'react';

import { Btn } from '@/components/ui/primitives';

// ---------------------------------------------------------------------------
// Pure logic — exported for unit testing
// ---------------------------------------------------------------------------

/**
 * Produces a bijection participant → prize via Fisher–Yates shuffle.
 * @param participants - list of participant names
 * @param prizes       - list of prize strings; must be same length as participants
 * @param rng          - random function returning [0, 1); defaults to Math.random
 * @throws Error when participants.length !== prizes.length
 */
export function computeLadderMapping(
  participants: string[],
  prizes: string[],
  rng: () => number = Math.random,
): { participant: string; prize: string }[] {
  if (participants.length !== prizes.length) {
    throw new Error(
      `participants(${participants.length}) and prizes(${prizes.length}) must have the same length`,
    );
  }

  // Fisher–Yates shuffle on a copy of prizes
  const shuffled = [...prizes];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const tmp = shuffled[i];
    shuffled[i] = shuffled[j];
    shuffled[j] = tmp;
  }

  return participants.map((participant, idx) => ({ participant, prize: shuffled[idx] }));
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_PARTICIPANTS = ['Alice', 'Bob', 'Carol', 'Dave'];

function buildDefaultPrizes(count: number): string[] {
  return Array.from({ length: count }, (_, i) => (i === 0 ? '커피' : '꽝'));
}

function parseLines(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Mapping = { participant: string; prize: string };

export function LadderGame() {
  const [participantText, setParticipantText] = useState(DEFAULT_PARTICIPANTS.join('\n'));
  const [prizeText, setPrizeText] = useState(() =>
    buildDefaultPrizes(DEFAULT_PARTICIPANTS.length).join('\n'),
  );
  const [result, setResult] = useState<Mapping[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleParticipantChange(val: string) {
    setParticipantText(val);
    setResult(null);
    setError(null);
    // Auto-resize prizes to match participant count
    const count = parseLines(val).length;
    setPrizeText(count > 0 ? buildDefaultPrizes(count).join('\n') : '');
  }

  function handlePrizeChange(val: string) {
    setPrizeText(val);
    setResult(null);
    setError(null);
  }

  function handleDraw() {
    const participants = parseLines(participantText);
    const prizes = parseLines(prizeText);
    setResult(null);
    setError(null);

    if (participants.length === 0) {
      setError('참가자를 한 명 이상 입력하세요.');
      return;
    }

    try {
      const mapping = computeLadderMapping(participants, prizes);
      setResult(mapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
    }
  }

  const participantCount = parseLines(participantText).length;
  const prizeCount = parseLines(prizeText).length;
  const countMismatch = participantCount > 0 && prizeCount > 0 && participantCount !== prizeCount;

  return (
    <div className="space-y-6">
      {/* Inputs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label
            htmlFor="ladder-participants"
            className="block text-sm font-medium text-ink-1"
          >
            참가자{' '}
            <span className="font-mono text-xs text-ink-3">({participantCount}명)</span>
          </label>
          <textarea
            id="ladder-participants"
            rows={6}
            value={participantText}
            onChange={(e) => handleParticipantChange(e.target.value)}
            placeholder="한 줄에 한 명씩 입력"
            className="w-full resize-none rounded border border-line bg-surface-raised px-3 py-2 font-mono text-sm text-ink-1 placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="ladder-prizes"
            className="block text-sm font-medium text-ink-1"
          >
            당첨 항목{' '}
            <span className="font-mono text-xs text-ink-3">({prizeCount}개)</span>
          </label>
          <textarea
            id="ladder-prizes"
            rows={6}
            value={prizeText}
            onChange={(e) => handlePrizeChange(e.target.value)}
            placeholder="한 줄에 하나씩 입력"
            className="w-full resize-none rounded border border-line bg-surface-raised px-3 py-2 font-mono text-sm text-ink-1 placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      </div>

      {countMismatch && (
        <p className="text-sm text-warn">
          참가자 수({participantCount})와 당첨 항목 수({prizeCount})가 다릅니다. 맞춰 주세요.
        </p>
      )}

      {/* Draw button */}
      <div className="flex items-center gap-3">
        <Btn
          variant="primary"
          size="lg"
          onClick={handleDraw}
          disabled={countMismatch}
        >
          사다리 타기
        </Btn>
        {result && (
          <Btn
            variant="ghost"
            size="lg"
            onClick={() => setResult(null)}
          >
            초기화
          </Btn>
        )}
      </div>

      {/* Error */}
      {error && (
        <p className="rounded border border-danger bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-ink-1">결과</h2>
          <div className="overflow-hidden rounded-lg border border-line">
            {result.map(({ participant, prize }, idx) => {
              const isCoffee = prize === '커피';
              return (
                <div
                  key={`${participant}-${idx}`}
                  className={`flex items-center justify-between px-4 py-3 text-sm ${
                    idx < result.length - 1 ? 'border-b border-line-subtle' : ''
                  } ${isCoffee ? 'bg-accent-soft' : 'bg-surface-raised'}`}
                >
                  <span className="font-medium text-ink-1">{participant}</span>
                  <span
                    className={`font-mono font-semibold ${
                      isCoffee ? 'text-accent' : 'text-ink-3'
                    }`}
                  >
                    {prize}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-ink-3">
            커피 당첨:{' '}
            {result
              .filter((r) => r.prize === '커피')
              .map((r) => r.participant)
              .join(', ') || '없음'}
          </p>
        </div>
      )}
    </div>
  );
}
