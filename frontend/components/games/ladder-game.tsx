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
const BOARD_HEIGHT = 360;
const BOARD_PADDING_X = 58;
const BOARD_TOP_Y = 56;
const BOARD_BOTTOM_Y = 292;

type Mapping = { participant: string; prize: string };
type Rung = { left: number; y: number };
type LadderVisual = {
  width: number;
  xs: number[];
  rungs: Rung[];
  paths: { participant: string; prize: string; d: string; accent: boolean; targetSlot: number }[];
};

function buildDefaultPrizes(count: number): string[] {
  return Array.from({ length: count }, (_, i) => (i === 0 ? '커피' : '꽝'));
}

function parseLines(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
}

function compactLabel(label: string): string {
  return label.length > 10 ? `${label.slice(0, 9)}…` : label;
}

function buildTargetSlots(mapping: Mapping[], prizes: string[]): number[] {
  const used = new Set<number>();

  return mapping.map(({ prize }) => {
    const slot = prizes.findIndex((candidate, idx) => candidate === prize && !used.has(idx));
    if (slot === -1) {
      return 0;
    }
    used.add(slot);
    return slot;
  });
}

function buildRungColumns(targetSlots: number[]): number[] {
  const finalOccupants = Array.from({ length: targetSlots.length }, () => -1);
  targetSlots.forEach((slot, participantIdx) => {
    finalOccupants[slot] = participantIdx;
  });

  const occupants = Array.from({ length: targetSlots.length }, (_, idx) => idx);
  const rungColumns: number[] = [];

  finalOccupants.forEach((participantIdx, targetCol) => {
    let currentCol = occupants.indexOf(participantIdx);
    while (currentCol > targetCol) {
      rungColumns.push(currentCol - 1);
      [occupants[currentCol - 1], occupants[currentCol]] = [
        occupants[currentCol],
        occupants[currentCol - 1],
      ];
      currentCol -= 1;
    }
    while (currentCol < targetCol) {
      rungColumns.push(currentCol);
      [occupants[currentCol], occupants[currentCol + 1]] = [
        occupants[currentCol + 1],
        occupants[currentCol],
      ];
      currentCol += 1;
    }
  });

  return rungColumns;
}

function tracePath(startCol: number, xs: number[], rungs: Rung[]): string {
  let col = startCol;
  const commands = [`M ${xs[col]} ${BOARD_TOP_Y}`];

  rungs.forEach((rung) => {
    commands.push(`L ${xs[col]} ${rung.y}`);
    if (col === rung.left) {
      col += 1;
      commands.push(`L ${xs[col]} ${rung.y}`);
    } else if (col === rung.left + 1) {
      col -= 1;
      commands.push(`L ${xs[col]} ${rung.y}`);
    }
  });

  commands.push(`L ${xs[col]} ${BOARD_BOTTOM_Y}`);
  return commands.join(' ');
}

function buildLadderVisual(participants: string[], prizes: string[], mapping: Mapping[]): LadderVisual {
  const count = participants.length;
  const width = Math.max(440, BOARD_PADDING_X * 2 + Math.max(count - 1, 1) * 112);
  const span = width - BOARD_PADDING_X * 2;
  const xs = Array.from({ length: count }, (_, idx) =>
    count === 1 ? width / 2 : BOARD_PADDING_X + (span / (count - 1)) * idx,
  );
  const targetSlots = buildTargetSlots(mapping, prizes);
  const rungColumns = buildRungColumns(targetSlots);
  const usableHeight = BOARD_BOTTOM_Y - BOARD_TOP_Y;
  const rungs = rungColumns.map((left, idx) => ({
    left,
    y: BOARD_TOP_Y + ((idx + 1) * usableHeight) / (rungColumns.length + 1),
  }));

  return {
    width,
    xs,
    rungs,
    paths: mapping.map(({ participant, prize }, idx) => ({
      participant,
      prize,
      d: tracePath(idx, xs, rungs),
      accent: prize === '커피',
      targetSlot: targetSlots[idx],
    })),
  };
}

function LadderBoard({ participants, prizes, result }: { participants: string[]; prizes: string[]; result: Mapping[] }) {
  const visual = buildLadderVisual(participants, prizes, result);

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface-raised shadow-sm">
      <style>{`
        @keyframes ladder-draw {
          from { stroke-dashoffset: 1; opacity: 0.18; }
          38% { opacity: 1; }
          to { stroke-dashoffset: 0; opacity: 1; }
        }
        @keyframes ladder-pop {
          0%, 70% { transform: scale(0.92); opacity: 0.45; }
          100% { transform: scale(1); opacity: 1; }
        }
        .ladder-route {
          stroke-dasharray: 1;
          stroke-dashoffset: 1;
          animation: ladder-draw 1.15s ease-out forwards;
        }
        .ladder-chip {
          transform-box: fill-box;
          transform-origin: center;
          animation: ladder-pop 0.48s ease-out forwards;
        }
      `}</style>
      <div className="border-b border-line-subtle bg-gradient-to-r from-accent-soft via-surface to-surface-raised px-4 py-3">
        <p className="text-sm font-semibold text-ink-1">사다리 진행</p>
        <p className="text-xs text-ink-3">선을 따라 내려가면 각 참가자의 당첨 항목이 나타납니다.</p>
      </div>
      <div className="overflow-x-auto px-3 py-4">
        <svg
          role="img"
          aria-label="사다리 타기 결과 애니메이션"
          viewBox={`0 0 ${visual.width} ${BOARD_HEIGHT}`}
          className="min-w-full"
          style={{ width: `${visual.width}px`, height: `${BOARD_HEIGHT}px` }}
        >
          <defs>
            <linearGradient id="ladderAccent" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="rgb(var(--color-accent-rgb, 37 99 235))" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
          </defs>

          <rect
            x="12"
            y="18"
            width={visual.width - 24}
            height={BOARD_HEIGHT - 36}
            rx="22"
            fill="rgba(255,255,255,0.03)"
            stroke="rgba(148,163,184,0.24)"
          />

          {visual.xs.map((x, idx) => (
            <g key={`rail-${idx}`}>
              <line
                x1={x}
                y1={BOARD_TOP_Y}
                x2={x}
                y2={BOARD_BOTTOM_Y}
                stroke="rgba(100,116,139,0.34)"
                strokeWidth="5"
                strokeLinecap="round"
              />
              <text
                x={x}
                y="34"
                textAnchor="middle"
                className="fill-ink-1 text-[12px] font-semibold"
              >
                {compactLabel(participants[idx])}
              </text>
              <text
                x={x}
                y="330"
                textAnchor="middle"
                className="fill-ink-2 text-[12px] font-semibold"
              >
                {compactLabel(prizes[idx] ?? '')}
              </text>
            </g>
          ))}

          {visual.rungs.map((rung, idx) => (
            <line
              key={`rung-${idx}`}
              x1={visual.xs[rung.left]}
              y1={rung.y}
              x2={visual.xs[rung.left + 1]}
              y2={rung.y}
              stroke="rgba(100,116,139,0.54)"
              strokeWidth="5"
              strokeLinecap="round"
            />
          ))}

          {visual.paths.map((path, idx) => (
            <path
              key={`${path.participant}-${idx}`}
              d={path.d}
              pathLength={1}
              className="ladder-route"
              style={{ animationDelay: `${idx * 170}ms` }}
              fill="none"
              stroke={path.accent ? 'url(#ladderAccent)' : 'rgba(59,130,246,0.46)'}
              strokeWidth={path.accent ? 7 : 4}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {visual.paths.map((path, idx) => (
            <g
              key={`chip-${path.participant}-${idx}`}
              className="ladder-chip"
              style={{ animationDelay: `${idx * 170 + 760}ms`, opacity: 0 }}
            >
              <circle
                cx={visual.xs[path.targetSlot]}
                cy="292"
                r={path.accent ? 10 : 7}
                fill={path.accent ? '#f59e0b' : '#60a5fa'}
                opacity="0.92"
              />
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

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

  const participants = parseLines(participantText);
  const prizes = parseLines(prizeText);
  const participantCount = participants.length;
  const prizeCount = prizes.length;
  const countMismatch = participantCount > 0 && prizeCount > 0 && participantCount !== prizeCount;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label
            htmlFor="ladder-participants"
            className="block text-sm font-medium text-ink-1"
          >
            참가자 <span className="font-mono text-xs text-ink-3">({participantCount}명)</span>
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
            당첨 항목 <span className="font-mono text-xs text-ink-3">({prizeCount}개)</span>
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

      {error && (
        <p className="rounded border border-danger bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-4">
          <LadderBoard participants={participants} prizes={prizes} result={result} />

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
        </div>
      )}
    </div>
  );
}
