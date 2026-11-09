import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, CheckCheck, ChevronRight, Download, FileText, GitBranch, Loader2, Mic, Play, Quote,
  RefreshCw, Sparkles, TriangleAlert, Users, Wand2, Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import { api, downloadWithToken } from '@/lib/api';
import { useAsync, usePoll } from '@/lib/hooks';
import { fmtDate, fmtDateTime, fmtDuration, fmtLatency, fmtPct, fmtStamp, KIND_META, PRIORITY_META, STATUS_META } from '@/lib/format';
import { Avatar, CopyButton, EmptyState, ErrorBox, Loading, SectionTitle, Segmented, useToast } from '@/components/ui';

type Tab = 'summary' | 'evidence' | 'transcript' | 'trace';

export function MeetingDetailPage() {
  const { id } = useParams();
  const mid = Number(id);
  const nav = useNavigate();
  const { push } = useToast();
  const detail = useAsync(() => api.meeting(mid), [mid]);
  const [tab, setTab] = useState<Tab>('summary');
  const [activeSeg, setActiveSeg] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const status = detail.data?.status;
  usePoll(() => detail.reload(), 2600, status === 'processing');

  const trace = useAsync(
    () => (detail.data?.trace_id ? api.meetingTrace(mid) : Promise.resolve(null)),
    [mid, detail.data?.trace_id],
  );

  const groundedCount = useMemo(
    () => (detail.data?.decisions || []).filter((d) => d.grounded).length,
    [detail.data],
  );

  if (detail.loading) return <Loading label="加载会议详情" />;
  if (detail.error) return <ErrorBox message={detail.error} onRetry={detail.reload} />;
  const m = detail.data!;

  async function reanalyze() {
    setBusy(true);
    try {
      await api.analyze(mid, false);
      push('info', '已重新提交分析，页面会自动刷新');
      detail.reload();
    } catch (e) {
      push('error', e instanceof Error ? e.message : '提交失败');
    } finally {
      setBusy(false);
    }
  }

  async function toTasks() {
    setBusy(true);
    try {
      const r = await api.tasksFromMeeting(mid);
      push('success', `已生成 ${r.created} 条任务，去任务看板查看`);
    } catch (e) {
      push('error', e instanceof Error ? e.message : '生成失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <button className="btn-ghost btn-sm -ml-2 text-ink-500" onClick={() => nav('/meetings')}>
        <ArrowLeft size={14} /> 返回列表
      </button>

      {/* 头部 */}
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={clsx('chip', STATUS_META[m.status]?.cls)}>{STATUS_META[m.status]?.name}</span>
              <span className="text-[11px] text-ink-400">{fmtDate(m.meeting_date)}</span>
              <span className="text-[11px] text-ink-300">·</span>
              <span className="text-[11px] text-ink-400">{fmtDuration(m.duration_ms)}</span>
              <span className="text-[11px] text-ink-300">·</span>
              <span className="text-[11px] text-ink-400">{m.counts.segments} 段转写</span>
            </div>
            <h2 className="mt-1.5 text-lg font-semibold text-ink-900">{m.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
              <Users size={12} />
              {(m.attendees || []).map((a) => (
                <span key={a} className="inline-flex items-center gap-1 rounded bg-ink-50 px-1.5 py-0.5">
                  <Avatar name={a} size={14} /> {a}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-outline btn-sm" onClick={() => downloadWithToken(api.meetingExportUrl(mid, 'md'), `${m.title}.md`)}>
              <Download size={13} /> Markdown
            </button>
            <button className="btn-outline btn-sm" onClick={() => downloadWithToken(api.meetingExportUrl(mid, 'docx'), `${m.title}.docx`)}>
              <FileText size={13} /> Word
            </button>
            <button className="btn-outline btn-sm" onClick={toTasks} disabled={busy || !m.action_items.length}>
              <CheckCheck size={13} /> 转为任务
            </button>
            <button className="btn-primary btn-sm" onClick={reanalyze} disabled={busy || m.status === 'processing'}>
              {busy || m.status === 'processing' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
              重新分析
            </button>
          </div>
        </div>

        {m.status === 'processing' && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-[11px] text-brand-700">
            <span className="pulseline h-1.5 w-1.5 rounded-full bg-brand-500" />
            六个 Agent 正在依次处理，页面每 2.6 秒自动刷新一次…
          </div>
        )}
        {m.status === 'failed' && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
            <TriangleAlert size={13} /> 上次分析失败，检查模型服务或转写内容后重试。
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3 border-t border-ink-100 pt-3 sm:grid-cols-4">
          {[
            ['决议', m.counts.decisions, 'text-brand-600'],
            ['待办', m.counts.actions, 'text-amber-600'],
            ['证据覆盖', `${groundedCount}/${m.decisions.length || 0}`, 'text-emerald-600'],
            ['成本', trace.data ? `$${trace.data.run.cost_usd.toFixed(4)}` : '—', 'text-ink-700'],
          ].map(([k, v, cls]) => (
            <div key={String(k)}>
              <p className="text-[11px] text-ink-400">{k}</p>
              <p className={clsx('mt-0.5 text-base font-semibold tabular-nums', cls)}>{v}</p>
            </div>
          ))}
        </div>
      </section>

      <Segmented<Tab>
        value={tab}
        onChange={setTab}
        options={[
          { value: 'summary', label: '纪要概览' },
          { value: 'evidence', label: '证据链' },
          { value: 'transcript', label: `原始转写 ${m.segments.length}` },
          { value: 'trace', label: 'Agent Trace' },
        ]}
      />

      {tab === 'summary' && <SummaryTab m={m} onJump={(idx) => { setActiveSeg(idx); setTab('transcript'); }} />}
      {tab === 'evidence' && <EvidenceTab m={m} onJump={(idx) => { setActiveSeg(idx); setTab('transcript'); }} />}
      {tab === 'transcript' && <TranscriptTab m={m} active={activeSeg} />}
      {tab === 'trace' && <TraceTab trace={trace.data} loading={trace.loading} runId={m.trace_id} />}
    </div>
  );
}

/* ------------------------------ 概览 ------------------------------ */

function SummaryTab({ m, onJump }: { m: import('@/types').MeetingDetail; onJump: (idx: number) => void }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
      <div className="space-y-4">
        <section className="card-pad">
          <SectionTitle extra={<CopyButton text={m.summary || ''} label="复制纪要" />}>会议摘要</SectionTitle>
          <p className="whitespace-pre-wrap text-[13.5px] leading-7 text-ink-700">{m.summary || '暂无摘要'}</p>
        </section>

        <section className="card-pad">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">按话题聚类</span>}>议题脉络</SectionTitle>
          {!m.topics?.length ? (
            <EmptyState title="尚无议题划分" desc="分析完成后会自动按时间窗聚类成议题。" />
          ) : (
            <ol className="space-y-3">
              {m.topics.map((t, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[11px] font-semibold text-brand-600">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-ink-800">{t.title}</p>
                    <p className="mt-0.5 text-[11.5px] leading-5 text-ink-500">{t.summary}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {(t.segments || []).slice(0, 6).map((idx) => (
                        <button
                          key={idx}
                          onClick={() => onJump(idx)}
                          className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-500 hover:bg-brand-100 hover:text-brand-700"
                        >
                          #{idx}
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="card">
        <div className="px-5 pt-4">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">含负责人与截止日</span>}>行动项</SectionTitle>
        </div>
        {!m.action_items.length ? (
          <EmptyState title="没有识别到行动项" desc="会议里没有出现明确的「谁在什么时候做什么」。" />
        ) : (
          <ul className="divide-y divide-ink-100">
            {m.action_items.map((a) => (
              <li key={a.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[13px] leading-5 text-ink-800">{a.text}</p>
                  <span className={clsx('chip shrink-0', PRIORITY_META[a.priority]?.cls)}>{PRIORITY_META[a.priority]?.name}</span>
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[11px] text-ink-400">
                  <Avatar name={a.owner_name} size={16} />
                  <span>{a.owner_name || '未指派'}</span>
                  <span className="text-ink-200">·</span>
                  <span>截止 {fmtDate(a.due_date)}</span>
                  {a.task_id && (
                    <span className="ml-auto rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-600">
                      已建任务 #{a.task_id}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/* ----------------------------- 证据链 ----------------------------- */

function EvidenceTab({ m, onJump }: { m: import('@/types').MeetingDetail; onJump: (idx: number) => void }) {
  const groups: { kind: string; items: typeof m.decisions }[] = [
    { kind: 'decision', items: m.decisions.filter((d) => d.kind === 'decision') },
    { kind: 'risk', items: m.decisions.filter((d) => d.kind === 'risk') },
    { kind: 'open_question', items: m.decisions.filter((d) => d.kind === 'open_question') },
  ];
  const segMap = useMemo(() => new Map(m.segments.map((s) => [s.idx, s])), [m.segments]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-100 bg-emerald-50/60 px-4 py-2.5 text-[11.5px] leading-5 text-emerald-800">
        <Sparkles size={14} className="shrink-0" />
        每条结论都带引用语句；系统会用 difflib 把引文与原文逐句回查，命中率不足 0.9 的引文会被标记为「已校正」，
        完全没有证据的结论会被归入「未决」而不是硬凑一条决议。
      </div>

      {groups.map((g) => (
        <section key={g.kind} className="card">
          <div className="flex items-center gap-2 px-5 pt-4">
            <span className={clsx('h-2 w-2 rounded-full', KIND_META[g.kind].dot)} />
            <SectionTitle extra={<span className="text-[11px] text-ink-400">{g.items.length} 条</span>}>
              {KIND_META[g.kind].name}
            </SectionTitle>
          </div>
          {!g.items.length ? (
            <p className="px-5 pb-4 text-[12px] text-ink-400">本次会议没有此类条目。</p>
          ) : (
            <ul className="space-y-2 px-4 pb-4">
              {g.items.map((d) => (
                <li key={d.id} className="rounded-lg border border-ink-100 p-3">
                  <div className="flex items-start gap-2">
                    <p className="flex-1 text-[13px] leading-6 text-ink-800">{d.text}</p>
                    <span
                      className={clsx(
                        'chip shrink-0',
                        d.grounded ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
                      )}
                    >
                      {d.grounded ? '有据' : '待核'} · {fmtPct(d.confidence, 0)}
                    </span>
                  </div>
                  <ul className="mt-2 space-y-1.5 border-l-2 border-brand-100 pl-3">
                    {(d.evidence || []).map((ev, i) => (
                      <li key={i} className="text-[11.5px] leading-5">
                        <button
                          className="group flex w-full items-start gap-2 text-left"
                          onClick={() => ev.segment_id && onJump(ev.segment_id)}
                        >
                          <Quote size={11} className="mt-1 shrink-0 text-brand-400" />
                          <span className="flex-1 text-ink-600 group-hover:text-brand-700">
                            「{ev.quote}」
                            <span className="ml-1 inline-flex items-center gap-1 text-[10px] text-ink-400">
                              <span className="rounded bg-ink-100 px-1 font-mono">#{ev.segment_id}</span>
                              {ev.speaker && <span>{ev.speaker}</span>}
                              {ev.start_ms !== undefined && <span>{fmtStamp(ev.start_ms)}</span>}
                              {ev.recovered && (
                                <span className="rounded bg-amber-100 px-1 text-amber-700">已校正</span>
                              )}
                            </span>
                          </span>
                          <ChevronRight size={12} className="mt-1 shrink-0 text-ink-300 group-hover:text-brand-500" />
                        </button>
                      </li>
                    ))}
                    {!d.evidence?.length && (
                      <li className="text-[11px] text-ink-400">无引用语句 —— 已归入未决问题，等待人工确认。</li>
                    )}
                  </ul>
                  {d.evidence?.[0]?.segment_id && segMap.get(d.evidence[0].segment_id) && (
                    <p className="mt-1.5 text-[10.5px] text-ink-400">
                      原文时间 {fmtStamp(segMap.get(d.evidence[0].segment_id)!.start_ms)}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}

/* ----------------------------- 转写 ----------------------------- */

function TranscriptTab({ m, active }: { m: import('@/types').MeetingDetail; active: number | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (active === null || !ref.current) return;
    const el = ref.current.querySelector(`[data-idx="${active}"]`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [active]);

  return (
    <section className="card">
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3">
        <div className="flex items-center gap-2 text-[13px] font-medium text-ink-800">
          <Mic size={14} className="text-brand-500" /> 原始转写
          <span className="text-[11px] font-normal text-ink-400">{m.segments.length} 段 · {fmtDuration(m.duration_ms)}</span>
        </div>
        <button className="btn-outline btn-sm" onClick={() => setPlaying((p) => !p)}>
          <Play size={12} /> {playing ? '暂停跟随' : '逐段跟随'}
        </button>
      </div>
      <div ref={ref} className="max-h-[62vh] space-y-1 overflow-y-auto p-4">
        {m.segments.map((s) => {
          const hit = active === s.idx;
          return (
            <div
              key={s.idx}
              data-idx={s.idx}
              className={clsx(
                'flex gap-3 rounded-lg px-3 py-2 transition',
                hit ? 'bg-brand-50 ring-1 ring-brand-200' : 'hover:bg-ink-50',
              )}
            >
              <span className="w-11 shrink-0 pt-0.5 font-mono text-[10.5px] text-ink-400">{fmtStamp(s.start_ms)}</span>
              <Avatar name={s.speaker} size={22} />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-ink-500">{s.speaker || `发言人 ${s.idx}`}</p>
                <p className="mt-0.5 text-[13px] leading-6 text-ink-800">{s.text}</p>
              </div>
              {s.confidence !== undefined && (
                <span className="shrink-0 pt-0.5 text-[10px] text-ink-300">{fmtPct(s.confidence, 0)}</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ----------------------------- Trace ----------------------------- */

function TraceTab({ trace, loading, runId }: { trace: import('@/types').TraceResp | null; loading: boolean; runId?: number | null }) {
  if (loading) return <Loading label="读取运行轨迹" />;
  if (!trace) {
    return <EmptyState icon={<GitBranch size={22} />} title="还没有运行记录" desc="点「重新分析」跑一次，六个 Agent 的输入输出会完整记录下来。" />;
  }
  const maxLatency = Math.max(1, ...trace.steps.map((s) => s.latency_ms));
  const totalTokens = trace.run.tokens_in + trace.run.tokens_out;

  return (
    <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
      <section className="card">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink-800">
            <GitBranch size={14} className="text-brand-500" /> Agent 执行链
          </div>
          {runId && (
            <Link to={`/runs/${runId}`} className="text-[11px] text-brand-600 hover:underline">
              独立页面查看 →
            </Link>
          )}
        </div>
        <ol className="relative p-5">
          <div className="absolute bottom-8 left-[30px] top-8 w-px bg-ink-100" />
          {trace.steps.map((s, i) => (
            <li key={i} className="relative flex gap-3 pb-4">
              <span
                className={clsx(
                  'z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-white text-[11px] font-semibold',
                  s.status === 'ok' ? 'bg-brand-600 text-white' : 'bg-rose-500 text-white',
                )}
              >
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[13px] font-medium text-ink-800">{s.label || s.agent}</p>
                  {s.cache_hit && (
                    <span className="chip bg-emerald-50 text-emerald-600">
                      <Zap size={10} /> 命中语义缓存
                    </span>
                  )}
                  <span className="ml-auto font-mono text-[10.5px] text-ink-400">{fmtLatency(s.latency_ms)}</span>
                </div>
                <div className="mt-1.5 space-y-1 rounded-lg bg-ink-50/70 p-2.5 text-[11.5px] leading-5">
                  <p className="text-ink-500">
                    <span className="text-ink-400">输入 </span>
                    {s.input}
                  </p>
                  <p className="text-ink-700">
                    <span className="text-ink-400">输出 </span>
                    {s.output}
                  </p>
                </div>
                <div className="mt-1 flex items-center gap-3 text-[10px] text-ink-400">
                  <span>{s.tokens_in} → {s.tokens_out} tok</span>
                  <span>证据 {s.evidence_count}</span>
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100">
                    <div className="h-full rounded-full bg-brand-400" style={{ width: `${(s.latency_ms / maxLatency) * 100}%` }} />
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <div className="space-y-4">
        <section className="card-pad">
          <SectionTitle>运行汇总</SectionTitle>
          <dl className="space-y-2 text-[12px]">
            {[
              ['模型', trace.run.model],
              ['状态', trace.run.status],
              ['总耗时', fmtLatency(trace.run.latency_ms)],
              ['Token', `${trace.run.tokens_in} 输入 / ${trace.run.tokens_out} 输出`],
              ['合计', `${totalTokens} tok`],
              ['成本', `$${trace.run.cost_usd.toFixed(4)}`],
              ['缓存命中', `${trace.run.cache_hits} 次`],
              ['开始时间', fmtDateTime(trace.run.created_at)],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <dt className="text-ink-400">{k}</dt>
                <dd className="truncate font-medium text-ink-700">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="card-pad">
          <SectionTitle extra={<Wand2 size={13} className="text-ink-300" />}>质量指标</SectionTitle>
          {(() => {
            const metrics = (trace.run.meta as { metrics?: { grounded_rate?: number; critic_score?: number } } | undefined)?.metrics || {};
            return (
              <div className="space-y-2 text-[12px]">
                <div className="flex items-center justify-between">
                  <span className="text-ink-400">证据覆盖率</span>
                  <span className="font-semibold text-emerald-600">{fmtPct(metrics.grounded_rate ?? 0, 1)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-400">评审 Agent 打分</span>
                  <span className="font-semibold text-brand-600">{((metrics.critic_score ?? 0) * 100).toFixed(0)}</span>
                </div>
                <p className="pt-1 text-[10.5px] leading-5 text-ink-400">
                  评审 Agent 会对决议逐条打分：是否可执行、是否与议题相关、是否有引用支撑，低于阈值的条目会被退回重写一轮。
                </p>
              </div>
            );
          })()}
        </section>
      </div>
    </div>
  );
}
