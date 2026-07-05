'use client';

import React, { useEffect, useRef } from 'react';

export type AdminToast = {
  id: number;
  type: 'success' | 'error';
  text: string;
};

function ToastItem({ toast, onDismiss }: { toast: AdminToast; onDismiss: (id: number) => void }) {
  const onDismissRef = useRef(onDismiss);

  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    const timer = window.setTimeout(() => onDismissRef.current(toast.id), 4000);
    return () => window.clearTimeout(timer);
  }, [toast.id]);

  return (
    <div
      role={toast.type === 'error' ? 'alert' : 'status'}
      aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
      className={`rounded-lg border p-3 text-sm shadow-lg ${toast.type === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-blue-200 bg-blue-50 text-blue-700'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <span>{toast.text}</span>
        <button type="button" onClick={() => onDismiss(toast.id)} className="rounded px-1 text-xs font-semibold" aria-label="알림 닫기">
          닫기
        </button>
      </div>
    </div>
  );
}

export function ToastStack({ toasts, onDismiss }: { toasts: AdminToast[]; onDismiss: (id: number) => void }) {

  if (!toasts.length) return null;

  return (
    <div className="fixed right-4 top-4 z-40 flex w-full max-w-sm flex-col gap-2" aria-label="알림">
      {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />)}
    </div>
  );
}
