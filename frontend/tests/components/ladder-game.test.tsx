import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import { computeLadderMapping, LadderGame } from '@/components/games/ladder-game';

// ---------------------------------------------------------------------------
// computeLadderMapping — pure function tests
// ---------------------------------------------------------------------------

describe('computeLadderMapping', () => {
  it('returns a deterministic mapping given rng = () => 0', () => {
    // With rng always returning 0, Fisher–Yates always swaps index i with index 0.
    // prizes = ['커피', '꽝', '꽝']
    // i=2: j=0 → swap idx0↔idx2 → ['꽝','꽝','커피']
    // i=1: j=0 → swap idx0↔idx1 → ['꽝','꽝','커피']  (idx0='꽝', idx1='꽝' — same)
    // result shuffled: ['꽝', '꽝', '커피']
    const participants = ['Alice', 'Bob', 'Carol'];
    const prizes = ['커피', '꽝', '꽝'];
    const rng = () => 0;

    const result = computeLadderMapping(participants, prizes, rng);

    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ participant: 'Alice', prize: '꽝' });
    expect(result[1]).toEqual({ participant: 'Bob', prize: '꽝' });
    expect(result[2]).toEqual({ participant: 'Carol', prize: '커피' });
  });

  it('returns deterministic mapping with a scripted rng sequence', () => {
    // prizes = ['A', 'B', 'C']
    // rng sequence: [0.9, 0.1] (used for i=2 and i=1)
    // i=2: j = floor(0.9 * 3) = 2 → swap idx2↔idx2 → ['A','B','C']
    // i=1: j = floor(0.1 * 2) = 0 → swap idx0↔idx1 → ['B','A','C']
    // shuffled = ['B', 'A', 'C']
    const sequence = [0.9, 0.1];
    let call = 0;
    const rng = () => sequence[call++];

    const result = computeLadderMapping(['X', 'Y', 'Z'], ['A', 'B', 'C'], rng);

    expect(result[0]).toEqual({ participant: 'X', prize: 'B' });
    expect(result[1]).toEqual({ participant: 'Y', prize: 'A' });
    expect(result[2]).toEqual({ participant: 'Z', prize: 'C' });
  });

  it('throws when participant and prize counts differ', () => {
    expect(() =>
      computeLadderMapping(['Alice', 'Bob'], ['커피'], Math.random),
    ).toThrow();
  });

  it('invariant: result is a bijection — every participant appears once', () => {
    const participants = ['P1', 'P2', 'P3', 'P4', 'P5'];
    const prizes = ['커피', '꽝', '꽝', '꽝', '꽝'];
    const result = computeLadderMapping(participants, prizes);

    const resultParticipants = result.map((r) => r.participant);
    expect(resultParticipants.sort()).toEqual([...participants].sort());
  });

  it('invariant: result is a bijection — every prize is used exactly once', () => {
    const participants = ['P1', 'P2', 'P3'];
    const prizes = ['커피', '꽝', '꽝'];
    const result = computeLadderMapping(participants, prizes);

    const resultPrizes = result.map((r) => r.prize).sort();
    expect(resultPrizes).toEqual([...prizes].sort());
  });

  it('invariant: exactly one "커피" and two "꽝" when prizes = ["커피","꽝","꽝"]', () => {
    const participants = ['Alice', 'Bob', 'Carol'];
    const prizes = ['커피', '꽝', '꽝'];
    const result = computeLadderMapping(participants, prizes);

    const coffeeCount = result.filter((r) => r.prize === '커피').length;
    const boomCount = result.filter((r) => r.prize === '꽝').length;

    expect(coffeeCount).toBe(1);
    expect(boomCount).toBe(2);
  });

  it('works for a single participant', () => {
    const result = computeLadderMapping(['Solo'], ['커피']);
    expect(result).toEqual([{ participant: 'Solo', prize: '커피' }]);
  });
});

// ---------------------------------------------------------------------------
// LadderGame component — render + interaction tests
// ---------------------------------------------------------------------------

describe('LadderGame component', () => {
  it('renders the draw button', () => {
    render(<LadderGame />);
    expect(screen.getByRole('button', { name: '사다리 타기' })).toBeInTheDocument();
  });

  it('renders participant and prize textareas', () => {
    render(<LadderGame />);
    expect(screen.getByLabelText(/참가자/)).toBeInTheDocument();
    expect(screen.getByLabelText(/당첨 항목/)).toBeInTheDocument();
  });

  it('shows result mapping after clicking draw', () => {
    render(<LadderGame />);

    // Default has 4 participants: Alice, Bob, Carol, Dave with 커피 + 꽝×3
    fireEvent.click(screen.getByRole('button', { name: '사다리 타기' }));

    // Result section heading appears
    expect(screen.getByRole('heading', { name: '결과' })).toBeInTheDocument();

    // All default participants should appear in result
    expect(screen.getAllByText('Alice').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Bob').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Carol').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Dave').length).toBeGreaterThanOrEqual(1);
  });

  it('shows error when participant textarea is cleared', () => {
    render(<LadderGame />);

    // Clearing participants triggers auto-resize: prizes resets to '' (count=0),
    // so no mismatch, button stays enabled, handleDraw fires the empty-list guard.
    const participantArea = screen.getByLabelText(/참가자/);
    fireEvent.change(participantArea, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '사다리 타기' }));

    expect(screen.getByText(/참가자를 한 명 이상 입력하세요/)).toBeInTheDocument();
  });

  it('preserves custom prize lines when participant count changes', () => {
    render(<LadderGame />);

    const participantArea = screen.getByLabelText(/참가자/);
    const prizeArea = screen.getByLabelText(/당첨 항목/) as HTMLTextAreaElement;

    fireEvent.change(prizeArea, { target: { value: '아메리카노\n라떼\n꽝\n꽝' } });
    fireEvent.change(participantArea, { target: { value: 'Alice\nBob\nCarol\nDave\nEve' } });

    expect(prizeArea.value).toBe('아메리카노\n라떼\n꽝\n꽝\n꽝');
  });

  it('reset button hides the result', () => {
    render(<LadderGame />);

    fireEvent.click(screen.getByRole('button', { name: '사다리 타기' }));
    expect(screen.getByRole('heading', { name: '결과' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '초기화' }));
    expect(screen.queryByRole('heading', { name: '결과' })).not.toBeInTheDocument();
  });
});
