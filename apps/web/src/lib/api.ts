/**
 * 极薄的一层 API 客户端：
 * - 统一带上 Bearer token（存 localStorage，演示环境够用）
 * - 统一把后端 {detail: "..."} 转成 Error，页面不用到处判 res.ok
 * - SSE 问答单独走 fetch + ReadableStream，避免 EventSource 不能带 header 的限制
 */
import type {
  BoardResp, ChatTurn, Citation, DocDetail, DocSummary, DocTemplate, EstimateResp,
  KbDoc, LoginResp, MeetingDetail, MeetingSummary, Overview, TraceResp, WeeklyDigest, WriteResult,
  RunInfo, Task,
} from '@/types';

const TOKEN_KEY = 'agentdesk.token';
const USER_KEY = 'agentdesk.user';

export const auth = {
  get token() {
    return localStorage.getItem(TOKEN_KEY) || '';
  },
  get user() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },
  save(resp: LoginResp) {
    localStorage.setItem(TOKEN_KEY, resp.token);
    localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (auth.token) headers.set('Authorization', `Bearer ${auth.token}`);

  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    auth.clear();
    if (!location.pathname.startsWith('/login')) location.assign('/login');
    throw new ApiError('登录已过期，请重新登录', 401);
  }
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`;
    try {
      const data = await res.json();
      msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* 后端异常时可能不是 JSON，保留状态码提示 */
    }
    throw new ApiError(msg, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: 'DELETE' });

export const api = {
  health: () => request<{ ok: boolean; provider: string; model: string; mock: boolean; has_key: boolean }>('/api/health'),

  login: (email: string, password: string) =>
    post<LoginResp>('/api/auth/login', { email, password }),

  overview: () => request<Overview>('/api/insights/overview'),
  runs: () => request<{ items: RunInfo[] }>('/api/runs'),
  run: (id: number) => request<TraceResp>(`/api/runs/${id}`),

  meetings: () => request<{ items: MeetingSummary[]; total: number }>('/api/meetings'),
  meeting: (id: number) => request<MeetingDetail>(`/api/meetings/${id}`),
  createMeeting: (body: { title: string; meeting_date?: string; attendees?: string[]; source_type?: string }) =>
    post<{ id: number }>('/api/meetings', body),
  addSegments: (id: number, segments: { idx: number; speaker: string; start_ms: number; end_ms: number; text: string }[]) =>
    post<{ ok: boolean; total: number }>(`/api/meetings/${id}/segments`, { segments }),
  analyze: (id: number, sync = false) => post<{ ok: boolean; status: string }>(`/api/meetings/${id}/analyze?sync=${sync ? 1 : 0}`),
  meetingTrace: (id: number) => request<TraceResp>(`/api/meetings/${id}/trace`),
  meetingExportUrl: (id: number, fmt: 'md' | 'docx') => `/api/meetings/${id}/export?fmt=${fmt}`,

  docs: () => request<{ items: DocSummary[] }>('/api/docs'),
  templates: () => request<{ items: DocTemplate[] }>('/api/docs/templates'),
  doc: (id: number) => request<DocDetail>(`/api/docs/${id}`),
  createDoc: (body: { title: string; content: string }) => post<{ id: number }>('/api/docs', body),
  saveDoc: (id: number, body: { title?: string; content?: string }) => put<{ ok: boolean; version: number }>(`/api/docs/${id}`, body),
  writeDoc: (id: number, instruction: string) => post<WriteResult>(`/api/docs/${id}/write`, { instruction }),
  applyDoc: (id: number, body: { blocks: WriteResult['blocks']; accepted: number[] }) =>
    post<{ ok: boolean; version: number; content: string }>(`/api/docs/${id}/apply`, body),

  kb: () => request<{ items: KbDoc[]; total_chunks: number }>('/api/kb'),
  uploadKb: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/kb/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: form,
    });
    if (!res.ok) throw new ApiError('上传失败', res.status);
    return (await res.json()) as { id: number; title: string; chunk_count: number };
  },
  deleteKb: (id: number) => del<{ ok: boolean }>(`/api/kb/${id}`),
  chatHistory: () => request<{ items: ChatTurn[] }>('/api/kb/chat/history'),
  clearChat: () => del<{ ok: boolean }>('/api/kb/chat/history'),

  tasks: () => request<BoardResp>('/api/tasks?view=board'),
  createTask: (body: Partial<Task>) => post<{ id: number }>('/api/tasks', body),
  updateTask: (id: number, body: Partial<Task>) => patch<{ ok: boolean }>(`/api/tasks/${id}`, body),
  deleteTask: (id: number) => del<{ ok: boolean }>(`/api/tasks/${id}`),
  estimate: (body: { text: string; priority?: string; deps?: number; due_date?: string; owner_name?: string }) =>
    post<EstimateResp>('/api/tasks/estimate', body),
  tasksFromMeeting: (id: number) => post<{ created: number }>(`/api/tasks/from-meeting/${id}`),
  weekly: (generate = 0) => request<WeeklyDigest>(`/api/tasks/weekly?generate=${generate}`),

  runtime: () => request<import('@/types').RuntimeInfo>('/api/settings/runtime'),
  setRuntime: (body: { tier?: string; pii_mask?: boolean; semantic_cache?: boolean; fast_thinking?: boolean }) =>
    put<{ ok: boolean }>('/api/settings/runtime', body),
  cache: () => request<{ entries: number; hits: number; misses: number; hit_rate: number; threshold: number }>('/api/settings/cache'),
  clearCache: () => post<{ cleared: number }>('/api/settings/cache/clear'),
};

/** 知识库问答：逐步消费 SSE，把检索、增量 token、最终引用分别交给回调。 */
export async function askStream(
  question: string,
  handlers: {
    onRetrieval?: (payload: { question: string; chunks: number }) => void;
    onToken?: (text: string) => void;
    onDone?: (payload: { answer: string; citations: Citation[] }) => void;
    onError?: (msg: string) => void;
  },
) {
  const res = await fetch('/api/kb/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
    body: JSON.stringify({ question }),
  });
  if (!res.ok || !res.body) {
    handlers.onError?.(`问答失败（${res.status}）`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === '[DONE]') continue;
      try {
        const evt = JSON.parse(raw);
        if (evt.type === 'retrieval') handlers.onRetrieval?.(evt);
        else if (evt.type === 'token') handlers.onToken?.(evt.text);
        else if (evt.type === 'done') handlers.onDone?.(evt);
        else if (evt.type === 'error') handlers.onError?.(evt.message || '生成中断');
      } catch {
        /* 单条事件解析失败不打断整轮回答 */
      }
    }
  }
}

/** 触发浏览器下载（导出用）。后端返回 401 时无法弹窗，需先确认已登录。 */
export function downloadWithToken(url: string, filename: string) {
  fetch(url, { headers: { Authorization: `Bearer ${auth.token}` } })
    .then((res) => res.blob())
    .then((blob) => {
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
    });
}
