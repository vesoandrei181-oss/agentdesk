import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronUp, GitBranch } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtCost, fmtDateTime, fmtLatency } from '@/lib/format';
import { ErrorBox, Loading, SectionTitle } from '@/components/ui';

export function RunDetailPage() {
  const { id } = useParams();
  const rid = Number(id);
  const nav = useNavigate();
  const run = useAsync(() => api.run(rid), [rid]);
  const [open, setOpen] = useState<number | null>(0);

  if (run.loading) return <Loading label="读取运行轨迹" />;
  if (run.error) return <ErrorBox message={run.error} onRetry={run.reload} />;
  const { run: r, steps } = run.data!;
  const maxLatency = Math.max(1, ...steps.map((s) => s.latency_ms));

  return (
    <div className="space-y-4">
      <button className="btn-ghost btn-sm -ml-2 text-ink-500" onClick={() => nav('/insights')}>
        <ArrowLeft size={14} /> 运行观测
      </button>

      <section className="card-pad">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] text-ink-400">Run #{r.id} · {r.kind}</p>
            <h2 className="mt-0.5 text-[16px] font-semibold text-ink-900">{r.title}</h2>
            <p className="mt-1 font-mono text-[10.5px] text-ink-400">
              {r.model} · {fmtDateTime(r.created_at)} · {r.status}
            </p>
          </div>
          <div className="grid grid-cols-4 gap-4 text-right">
            {[
              ['Token', `${r.tokens_in + r.tokens_out}`],
              ['耗时', fmtLatency(r.latency_ms)],
              ['成本', fmtCost(r.cost_usd)],
              ['缓存', `${r.cache_hits}`],
            ].map(([k, v]) => (
              <div key={k}>
                <p className="text-[10px] text-ink-400">{k}</p>
                <p className="text-[13px] font-semibold tabular-nums text-ink-800">{v}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card">
        <div className="flex items-center gap-2 border-b border-ink-100 px-5 py-3 text-[13px] font-medium text-ink-800">
          <GitBranch size={14} className="text-brand-500" /> 执行步骤（{steps.length}）
        </div>
        <ul className="divide-y divide-ink-100">
          {steps.map((s, i) => {
            const expanded = open === i;
            return (
              <li key={i}>
                <button className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-ink-50/60" onClick={() => setOpen(expanded ? null : i)}>
                  <span
                    className={clsx(
                      'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                      s.status === 'ok' ? 'bg-brand-600 text-white' : 'bg-rose-500 text-white',
                    )}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium text-ink-800">{s.label || s.agent}</span>
                      <span className="font-mono text-[10px] text-ink-400">{s.agent}</span>
                      {s.cache_hit && <span className="chip bg-emerald-50 text-emerald-600">缓存命中</span>}
                    </div>
                    <p className="mt-0.5 line-clamp-1 text-[11px] text-ink-400">{s.output}</p>
                  </div>
                  <div className="hidden w-32 shrink-0 items-center gap-2 sm:flex">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100">
                      <div className="h-full rounded-full bg-brand-400" style={{ width: `${(s.latency_ms / maxLatency) * 100}%` }} />
                    </div>
                    <span className="w-10 text-right font-mono text-[10px] text-ink-400">{fmtLatency(s.latency_ms)}</span>
                  </div>
                  {expanded ? <ChevronUp size={14} className="text-ink-300" /> : <ChevronDown size={14} className="text-ink-300" />}
                </button>
                {expanded && (
                  <div className="space-y-2 bg-ink-50/40 px-5 pb-4 pt-1">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="rounded-lg bg-white p-2.5">
                        <p className="mb-1 text-[10px] font-medium text-ink-400">输入摘要</p>
                        <p className="text-[11.5px] leading-5 text-ink-600">{s.input}</p>
                      </div>
                      <div className="rounded-lg bg-white p-2.5">
                        <p className="mb-1 text-[10px] font-medium text-ink-400">输出摘要</p>
                        <p className="text-[11.5px] leading-5 text-ink-700">{s.output}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3 text-[10.5px] text-ink-400">
                      <span>输入 {s.tokens_in} tok</span>
                      <span>输出 {s.tokens_out} tok</span>
                      <span>证据 {s.evidence_count} 条</span>
                      <span>状态 {s.status}</span>
                    </div>
                    {s.payload && Object.keys(s.payload).length > 0 && (
                      <div>
                        <p className="mb-1 text-[10px] font-medium text-ink-400">结构化返回</p>
                        <pre className="max-h-56 overflow-auto rounded-lg bg-ink-900/95 p-3 font-mono text-[10.5px] leading-5 text-ink-100">
                          {JSON.stringify(s.payload, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {r.meta && Object.keys(r.meta).length > 0 && (
        <section className="card-pad">
          <SectionTitle>运行元数据</SectionTitle>
          <pre className="overflow-auto rounded-lg bg-ink-50 p-3 font-mono text-[10.5px] leading-5 text-ink-600">
            {JSON.stringify(r.meta, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
}
