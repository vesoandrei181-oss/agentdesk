/** 展示层的小工具：时间、时长、成本、百分比。集中放一处避免各页面写法不一致。 */

export function fmtDate(input?: string | null): string {
  if (!input) return '—';
  const d = new Date(input.includes('T') || input.includes('-') ? input : `${input}T00:00:00`);
  if (Number.isNaN(d.getTime())) return input;
  const now = new Date();
  const sameYear = d.getFullYear() === now.getFullYear();
  const mm = `${d.getMonth() + 1}`.padStart(2, '0');
  const dd = `${d.getDate()}`.padStart(2, '0');
  return sameYear ? `${mm}-${dd}` : `${d.getFullYear()}-${mm}-${dd}`;
}

export function fmtDateTime(input?: string | null): string {
  if (!input) return '—';
  const d = new Date(input);
  if (Number.isNaN(d.getTime())) return input;
  const p = (n: number) => `${n}`.padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 会议时长：秒级以下不显示，超过一小时折成 h m。 */
export function fmtDuration(ms?: number | null): string {
  if (!ms || ms <= 0) return '—';
  const total = Math.round(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h}h${m} 分`;
  if (m) return `${m} 分 ${s ? `${s} 秒` : ''}`.trim();
  return `${s} 秒`;
}

/** 转写时间戳 mm:ss，便于和音频对齐。 */
export function fmtStamp(ms?: number | null): string {
  if (ms === null || ms === undefined) return '--:--';
  const total = Math.round(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${`${m}`.padStart(2, '0')}:${`${s}`.padStart(2, '0')}`;
}

export function fmtPct(v?: number | null, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtCost(usd?: number | null): string {
  if (!usd) return '$0';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export function fmtNum(n?: number | null): string {
  if (n === null || n === undefined) return '—';
  if (n >= 10000) return `${(n / 1000).toFixed(1)}k`;
  return `${n}`;
}

export function fmtLatency(ms?: number | null): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

export const KIND_META: Record<string, { name: string; cls: string; dot: string }> = {
  decision: { name: '决议', cls: 'bg-brand-50 text-brand-700', dot: 'bg-brand-500' },
  risk: { name: '风险', cls: 'bg-amber-50 text-amber-700', dot: 'bg-amber-500' },
  open_question: { name: '未决', cls: 'bg-ink-100 text-ink-600', dot: 'bg-ink-400' },
};

export const PRIORITY_META: Record<string, { name: string; cls: string }> = {
  high: { name: '高', cls: 'bg-rose-50 text-rose-600' },
  medium: { name: '中', cls: 'bg-amber-50 text-amber-700' },
  low: { name: '低', cls: 'bg-ink-100 text-ink-500' },
};

export const STATUS_META: Record<string, { name: string; cls: string }> = {
  draft: { name: '草稿', cls: 'bg-ink-100 text-ink-500' },
  processing: { name: '分析中', cls: 'bg-brand-50 text-brand-600' },
  ready: { name: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
  failed: { name: '失败', cls: 'bg-rose-50 text-rose-600' },
};

/** 简单的中文姓名 → 头像底色，保证同一个人在列表里颜色稳定。 */
export function hueOf(name?: string): number {
  if (!name) return 220;
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

export function initials(name?: string): string {
  if (!name) return '?';
  return name.length <= 2 ? name : name.slice(-2);
}
