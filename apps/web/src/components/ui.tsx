import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react';
import { CheckCircle2, Info, X, AlertTriangle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { hueOf, initials } from '@/lib/format';

/* ----------------------------- 全局轻提示 ----------------------------- */

type ToastKind = 'success' | 'error' | 'info';
type ToastItem = { id: number; kind: ToastKind; text: string };

const ToastCtx = createContext<{ push: (kind: ToastKind, text: string) => void }>({ push: () => {} });

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = (seq.current += 1);
    setItems((prev) => [...prev, { id, kind, text }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 3200);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={clsx(
              'pointer-events-auto flex max-w-sm items-start gap-2 rounded-lg border px-3.5 py-2.5 text-[13px] shadow-pop',
              'animate-fade-up bg-white',
              t.kind === 'success' && 'border-emerald-200 text-emerald-700',
              t.kind === 'error' && 'border-rose-200 text-rose-700',
              t.kind === 'info' && 'border-ink-200 text-ink-700',
            )}
          >
            {t.kind === 'success' && <CheckCircle2 size={15} className="mt-0.5 shrink-0" />}
            {t.kind === 'error' && <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
            {t.kind === 'info' && <Info size={15} className="mt-0.5 shrink-0" />}
            <span className="leading-5">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------- 弹窗 ------------------------------- */

export function Modal({
  open, onClose, title, desc, children, footer, width = 'max-w-lg',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  desc?: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/30 p-4 pt-[8vh] backdrop-blur-[2px]">
      <div className={clsx('w-full animate-fade-up rounded-xl bg-white shadow-pop', width)}>
        <div className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4">
          <div>
            <h3 className="text-[15px] font-semibold text-ink-900">{title}</h3>
            {desc && <p className="mt-0.5 text-xs text-ink-500">{desc}</p>}
          </div>
          <button className="btn-ghost -mr-1 h-8 w-8 !p-0" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-ink-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

/* ------------------------------ 状态块 ------------------------------ */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('shimmer rounded-md bg-ink-100', className)} />;
}

export function Loading({ label = '加载中' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-400">
      <Loader2 size={16} className="animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({
  icon, title, desc, action,
}: { icon?: ReactNode; title: string; desc?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      {icon && <div className="mb-1 text-ink-300">{icon}</div>}
      <p className="text-sm font-medium text-ink-600">{title}</p>
      {desc && <p className="max-w-md text-xs leading-5 text-ink-400">{desc}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-rose-100 bg-rose-50/60 py-10 text-center">
      <AlertTriangle size={20} className="text-rose-400" />
      <p className="text-sm text-rose-600">{message}</p>
      {onRetry && (
        <button className="btn-outline btn-sm" onClick={onRetry}>
          重新加载
        </button>
      )}
    </div>
  );
}

/* ------------------------------ 小组件 ------------------------------ */

export function Avatar({ name, size = 28 }: { name?: string; size?: number }) {
  const hue = hueOf(name);
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-medium text-white"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        background: `linear-gradient(135deg, hsl(${hue} 62% 60%), hsl(${(hue + 28) % 360} 58% 48%))`,
      }}
      title={name}
    >
      {initials(name)}
    </span>
  );
}

export function Segmented<T extends string>({
  value, options, onChange, size = 'md',
}: {
  value: T;
  options: { value: T; label: string; icon?: ReactNode }[];
  onChange: (v: T) => void;
  size?: 'sm' | 'md';
}) {
  return (
    <div className="inline-flex rounded-lg bg-ink-100 p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            'inline-flex items-center gap-1.5 rounded-[7px] font-medium transition',
            size === 'sm' ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-xs',
            value === opt.value ? 'bg-white text-ink-800 shadow-sm' : 'text-ink-500 hover:text-ink-700',
          )}
        >
          {opt.icon}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function Progress({ value, tone = 'brand' }: { value: number; tone?: 'brand' | 'emerald' | 'amber' | 'rose' }) {
  const toneCls = {
    brand: 'bg-brand-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    rose: 'bg-rose-500',
  }[tone];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
      <div className={clsx('h-full rounded-full transition-all duration-500', toneCls)} style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} />
    </div>
  );
}

export function SectionTitle({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between">
      <h2 className="text-[15px] font-semibold text-ink-900">{children}</h2>
      {extra}
    </div>
  );
}

export function CopyButton({ text, label = '复制' }: { text: string; label?: string }) {
  const { push } = useToast();
  return (
    <button
      className="btn-ghost btn-sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          push('success', '已复制到剪贴板');
        } catch {
          push('error', '浏览器拒绝了剪贴板写入');
        }
      }}
    >
      {label}
    </button>
  );
}
