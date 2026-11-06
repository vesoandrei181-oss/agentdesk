import { useCallback, useEffect, useRef, useState } from 'react';

type AsyncState<T> = { data: T | null; loading: boolean; error: string | null };

/**
 * 统一的数据加载 hook：
 * deps 变化自动重取；reload() 手动刷新；组件卸载后不再 setState（避免切页告警）。
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });
  const alive = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current();
      if (alive.current) setState({ data, loading: false, error: null });
    } catch (err) {
      if (alive.current) {
        setState({ data: null, loading: false, error: err instanceof Error ? err.message : '加载失败' });
      }
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    void run();
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, reload: run, setData: (d: T) => setState((s) => ({ ...s, data: d })) };
}

/** 输入防抖，用于搜索框避免每敲一个字就发一次请求。 */
export function useDebounced<T>(value: T, delay = 280): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setV(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return v;
}

/** 轮询：会议分析是后台任务，页面需要盯着 status 变化。 */
export function usePoll(cb: () => void, intervalMs: number, enabled: boolean) {
  const ref = useRef(cb);
  ref.current = cb;
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => ref.current(), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, enabled]);
}
