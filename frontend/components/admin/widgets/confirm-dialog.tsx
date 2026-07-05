'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

type ConfirmOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'danger' | 'default';
  inputLabel?: string;
  inputPlaceholder?: string;
  inputType?: string;
};

type ConfirmResult = { confirmed: false } | { confirmed: true; value?: string };

type PendingConfirm = ConfirmOptions & {
  resolve: (result: ConfirmResult) => void;
};

const ConfirmContext = createContext<((options: ConfirmOptions) => Promise<ConfirmResult>) | null>(null);

export function useConfirm() {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error('useConfirm must be used inside ConfirmProvider');
  return confirm;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const [inputValue, setInputValue] = useState('');

  const confirm = useCallback((options: ConfirmOptions) => new Promise<ConfirmResult>((resolve) => {
    setInputValue('');
    setPending({ ...options, resolve });
  }), []);

  const close = useCallback((result: ConfirmResult) => {
    setPending((current) => {
      current?.resolve(result);
      return null;
    });
  }, []);

  useEffect(() => {
    if (!pending) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close({ confirmed: false });
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [close, pending]);

  const value = useMemo(() => confirm, [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <div role="dialog" aria-modal="true" aria-label={pending.title} className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">{pending.title}</h2>
            <p className="mt-2 whitespace-pre-line text-sm text-slate-600">{pending.message}</p>
            {pending.inputLabel ? (
              <label className="mt-4 block text-sm font-medium text-slate-700">
                {pending.inputLabel}
                <input
                  autoFocus
                  aria-label={pending.inputLabel}
                  type={pending.inputType ?? 'text'}
                  value={inputValue}
                  placeholder={pending.inputPlaceholder}
                  onChange={(event) => setInputValue(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </label>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => close({ confirmed: false })} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700">
                {pending.cancelLabel ?? '취소'}
              </button>
              <button
                type="button"
                onClick={() => close({ confirmed: true, value: inputValue })}
                disabled={Boolean(pending.inputLabel) && !inputValue.trim()}
                className={`rounded-md px-3 py-2 text-sm font-semibold text-white disabled:opacity-40 ${pending.tone === 'danger' ? 'bg-rose-600' : 'bg-slate-900'}`}
              >
                {pending.confirmLabel ?? '확인'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </ConfirmContext.Provider>
  );
}
