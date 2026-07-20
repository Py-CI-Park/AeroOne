'use client';

import { useEffect, useState } from 'react';

import { HelpManualButton } from '@/components/layout/help-manual-button';
import { fetchAeroWorkPrefs, fetchAiStatus, updateAeroWorkPrefs } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { AiStatusResponse } from '@/lib/types';

// Aero Work P4 환경설정 — 업무대화·지식폴더가 함께 쓰는 로컬 AI(폐쇄망 Ollama/OpenAI 호환)
// 연결 상태를 실시간으로 보여주고, 전체 사용법(HelpManualButton 재사용)을 연다. 연결/모델의
// 실제 등록·전환은 관리자 콘솔이 진실 원천이므로 여기서는 상태 확인 + 안내로 한정한다.

const STATUS_META: Record<AiStatusResponse['status'], { label: string; tone: string }> = {
  ok: { label: '정상 연결', tone: 'text-emerald-600' },
  disabled: { label: '비활성화됨', tone: 'text-ink-3' },
  unavailable: { label: '연결 불가', tone: 'text-rose-600' },
  model_missing: { label: '모델 미설치', tone: 'text-amber-600' },
};

export function SettingsPanel() {
  const [aiStatus, setAiStatus] = useState<AiStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const status = await fetchAiStatus();
        if (alive) {
          setAiStatus(status);
        }
      } catch {
        if (alive) {
          setAiStatus(null);
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const [llmMode, setLlmMode] = useState<'default' | 'local'>('default');
  const [savingMode, setSavingMode] = useState(false);
  const [modeMessage, setModeMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void fetchAeroWorkPrefs()
      .then((prefs) => {
        if (alive && (prefs.llm_mode === 'default' || prefs.llm_mode === 'local')) {
          setLlmMode(prefs.llm_mode);
        }
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const switchMode = async (mode: 'default' | 'local') => {
    setSavingMode(true);
    setModeMessage(null);
    try {
      const result = await updateAeroWorkPrefs(mode, getCsrfCookie());
      setLlmMode(result.llm_mode as 'default' | 'local');
      setModeMessage(mode === 'local' ? '이 계정은 로컬 AI(Ollama)만 사용합니다.' : '관리자 선택 provider 를 따릅니다.');
    } catch {
      setModeMessage('프로필 전환 실패. 로그인 상태를 확인할 것.');
    } finally {
      setSavingMode(false);
    }
  };

  const meta = aiStatus ? STATUS_META[aiStatus.status] : null;

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">AI 연결 상태</p>
        {loading ? (
          <p className="mt-2 text-sm text-ink-3">확인 중…</p>
        ) : aiStatus && meta ? (
          <div className="mt-2 space-y-1 text-sm">
            <p>
              상태: <span className={`font-medium ${meta.tone}`}>{meta.label}</span>
            </p>
            <p className="text-ink-2">모델: <span className="font-mono text-ink-1">{aiStatus.model}</span></p>
            <p className="break-all text-ink-2">엔드포인트: <span className="font-mono text-ink-3">{aiStatus.base_url}</span></p>
            {aiStatus.detail ? <p className="text-xs text-ink-3">{aiStatus.detail}</p> : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-3">AI 상태를 불러오지 못함. 로그인 상태를 확인할 것.</p>
        )}
        <p className="mt-3 text-xs leading-relaxed text-ink-3">
          업무대화와 지식폴더가 이 로컬 AI(폐쇄망 Ollama / OpenAI 호환)를 함께 사용합니다. 연결
          엔드포인트·모델의 등록과 전환은 관리자 콘솔에서 관리합니다.
        </p>
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">사용법</p>
        <p className="mt-1 text-xs text-ink-2">AeroOne 전체 사용법을 단계별로 다시 볼 수 있습니다.</p>
        <div className="mt-3">
          <HelpManualButton />
        </div>
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">LLM 프로필 (내 계정)</p>
        <p className="mt-1 text-xs text-ink-2">업무대화 근거 답변·문서 AI 생성에 쓸 모델 경로를 고릅니다.</p>
        <div className="mt-2 flex gap-1">
          {[
            ['default', '관리자 선택 따름'],
            ['local', '로컬 AI 강제'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              disabled={savingMode}
              onClick={() => void switchMode(value as 'default' | 'local')}
              className={`rounded-full px-3 py-1 text-xs font-medium disabled:opacity-50 ${
                llmMode === value ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2 hover:bg-accent-soft'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        {modeMessage ? <p className="mt-2 text-xs text-ink-3">{modeMessage}</p> : null}
        <p className="mt-2 text-xs leading-relaxed text-ink-3">
          '로컬 AI 강제'는 이 계정의 요청을 폐쇄망 로컬 Ollama 로만 보냅니다(내부서버·외부 API 미사용).
          연결 등록·기본 선택은 관리자 콘솔이 관리합니다.
        </p>
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">Aero Work 워크스페이스</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-2">
          홈 브리핑 · 업무대화 · 일정 · 문서작성(HWPX) · 지식폴더 · 실행기록을 한 자리에서
          사용합니다. 화면 테마는 AeroOne 앱 전역 설정을 따릅니다.
        </p>
      </div>
    </div>
  );
}
