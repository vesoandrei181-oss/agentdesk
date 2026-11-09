import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowUpRight, Clock3, FileCheck2, Gauge, Mic, Sparkles, TrendingUp, Wand2, AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtCost, fmtDate, fmtNum, fmtPct, KIND_META, STATUS_META, PRIORITY_META } from '@/lib/format';
import { AreaChart, BarRow } from '@/components/charts';
import { Avatar, EmptyState, ErrorBox, Loading, SectionTitle } from '@/components/ui';
import { clsx } from 'clsx';

export function DashboardPage() {
  const nav = useNavigate();
  const overview = useAsync(() => api.overview(), []);
  const meetings = useAsync(() => api.meetings(), []);
  const board = useAsync(() => api.tasks(), []);

  if (overview.loading) return <Loading label="正在汇总工作区数据" />;
  if (overview.error) return <ErrorBox message={overview.error} onRetry={overview.reload} />;
  const kpi = overview.data!.kpi;
  const maxAgent = Math.max(1, ...overview.data!.agents.map((a) => a.calls));

  const cards = [
    { label: '累计会议', value: kpi.meetings, suffix: '场', icon: Mic, tone: 'text-brand-600 bg-brand-50' },
    { label: '沉淀决议', value: kpi.decisions, suffix: '条', icon: FileCheck2, tone: 'text-emerald-600 bg-emerald-50' },
    { label: '证据覆盖率', value: fmtPct(kpi.grounded_rate, 1), suffix: '', icon: Gauge, tone: 'text-sky-600 bg-sky-50' },
    { label: '节省整理工时', value: kpi.saved_minutes, suffix: '分钟', icon: Clock3, tone: 'text-amber-600 bg-amber-50' },
  ];

  const atRisk = (board.data?.columns.flatMap((c) => c.items) || [])
    .filter((t) => t.status !== 'done' && (t.risk_score >= 0.35 || t.priority === 'high'))
    .slice(0, 4);

  return (
    <div className="space-y-5">
      {/* 顶部欢迎 + 快捷入口 */}
      <section className="card relative overflow-hidden p-5">
        <div className="absolute -right-10 -top-16 h-48 w-48 rounded-full bg-brand-100/60 blur-2xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs text-ink-400">2026 秋季 · 智协实验室</p>
            <h2 className="mt-1 text-lg font-semibold text-ink-900">
              今天有 <span className="text-brand-600">{board.data?.total ? board.data.total - kpi.tasks_done : 0}</span> 项任务待推进
            </h2>
            <p className="mt-1 max-w-xl text-xs leading-5 text-ink-500">
              把一段会议录音或转写文本丢进来，六个 Agent 会依次完成清洗、分块、决议抽取、待办拆解、
              质量复核与纪要成文；每条结论都带原始语句引用，没有证据的条目会被单独标出来。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary" onClick={() => nav('/meetings')}>
              <Mic size={15} /> 新建会议纪要
            </button>
            <button className="btn-outline" onClick={() => nav('/kb')}>
              <Sparkles size={15} /> 知识库问答
            </button>
            <button className="btn-outline" onClick={() => nav('/weekly')}>
              <Wand2 size={15} /> 生成本周周报
            </button>
          </div>
        </div>
      </section>

      {/* KPI */}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="card-pad">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-500">{c.label}</span>
              <span className={clsx('flex h-7 w-7 items-center justify-center rounded-lg', c.tone)}>
                <c.icon size={14} />
              </span>
            </div>
            <p className="mt-2 text-2xl font-semibold tabular-nums text-ink-900">
              {c.value}
              <span className="ml-1 text-xs font-normal text-ink-400">{c.suffix}</span>
            </p>
          </div>
        ))}
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        {/* 近 14 天运行趋势 */}
        <section className="card-pad">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">近 14 天 · 次</span>}>
            分析任务趋势
          </SectionTitle>
          <AreaChart data={overview.data!.timeline as unknown as Record<string, unknown>[]} valueKey="runs" height={110} />
          <div className="mt-3 grid grid-cols-3 gap-3 border-t border-ink-100 pt-3 text-center">
            <div>
              <p className="text-[11px] text-ink-400">Agent 调用</p>
              <p className="text-sm font-semibold text-ink-800">
                {overview.data!.agents.reduce((s, a) => s + a.calls, 0)} 次
              </p>
            </div>
            <div>
              <p className="text-[11px] text-ink-400">Token 消耗</p>
              <p className="text-sm font-semibold text-ink-800">{fmtNum(kpi.tokens)}</p>
            </div>
            <div>
              <p className="text-[11px] text-ink-400">累计成本</p>
              <p className="text-sm font-semibold text-ink-800">{fmtCost(kpi.cost_usd)}</p>
            </div>
          </div>
        </section>

        {/* Agent 调用分布 */}
        <section className="card-pad">
          <SectionTitle extra={<Link className="text-[11px] text-brand-600 hover:underline" to="/insights">运行观测</Link>}>
            Agent 调用分布
          </SectionTitle>
          <div className="space-y-2.5">
            {overview.data!.agents.map((a) => (
              <BarRow key={a.agent} name={a.label} value={a.calls} max={maxAgent} suffix=" 次" />
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between rounded-lg bg-ink-50 px-3 py-2 text-[11px] text-ink-500">
            <span>语义缓存命中</span>
            <span className="font-medium text-ink-700">
              {kpi.cache_hits} 次 · {fmtPct(overview.data!.cache.hit_rate, 0)}
            </span>
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        {/* 最近会议 */}
        <section className="card">
          <div className="flex items-center justify-between px-5 pt-4">
            <SectionTitle>最近会议</SectionTitle>
            <Link to="/meetings" className="mb-3 inline-flex items-center gap-0.5 text-[11px] text-brand-600 hover:underline">
              全部 <ArrowUpRight size={11} />
            </Link>
          </div>
          {meetings.loading ? (
            <Loading label="" />
          ) : !meetings.data?.items.length ? (
            <EmptyState title="还没有会议记录" desc="从「会议纪要」页粘贴一段转写文本试试。" />
          ) : (
            <ul className="divide-y divide-ink-100">
              {meetings.data.items.slice(0, 5).map((m) => (
                <li key={m.id}>
                  <Link to={`/meetings/${m.id}`} className="flex items-start gap-3 px-5 py-3 transition hover:bg-ink-50/70">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                      <Mic size={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-[13px] font-medium text-ink-800">{m.title}</p>
                        <span className={clsx('chip', STATUS_META[m.status]?.cls || 'bg-ink-100 text-ink-500')}>
                          {STATUS_META[m.status]?.name || m.status}
                        </span>
                      </div>
                      <p className="mt-0.5 line-clamp-1 text-[11px] leading-5 text-ink-400">{m.summary || '暂无摘要'}</p>
                      <div className="mt-1 flex items-center gap-3 text-[10px] text-ink-400">
                        <span>{fmtDate(m.meeting_date)}</span>
                        <span>{m.counts.decisions} 条决议</span>
                        <span>{m.counts.actions} 项待办</span>
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 风险与待办 */}
        <section className="card">
          <div className="flex items-center justify-between px-5 pt-4">
            <SectionTitle>需要关注</SectionTitle>
            <Link to="/tasks" className="mb-3 inline-flex items-center gap-0.5 text-[11px] text-brand-600 hover:underline">
              看板 <ArrowUpRight size={11} />
            </Link>
          </div>
          {!atRisk.length ? (
            <EmptyState icon={<TrendingUp size={20} />} title="暂无高风险任务" desc="所有高优任务的工时预测都在可用余量内。" />
          ) : (
            <ul className="space-y-2 px-4 pb-4">
              {atRisk.map((t) => (
                <li key={t.id} className="rounded-lg border border-ink-100 px-3 py-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[13px] font-medium leading-5 text-ink-800">{t.title}</p>
                    <span className={clsx('chip shrink-0', PRIORITY_META[t.priority]?.cls)}>
                      {PRIORITY_META[t.priority]?.name}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-[11px] text-ink-400">
                    <Avatar name={t.owner_name} size={16} />
                    <span>{t.owner_name || '未指派'}</span>
                    <span className="text-ink-200">·</span>
                    <span>截止 {fmtDate(t.due_date)}</span>
                    {t.p90_days > 0 && (
                      <>
                        <span className="text-ink-200">·</span>
                        <span className={t.risk_score >= 0.5 ? 'text-rose-500' : 'text-ink-400'}>
                          P90 {t.p90_days} 天
                        </span>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mx-4 mb-4 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-700">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            风险评分来自工期分布与截止日余量的比较，用于提示而不是下结论。
          </div>
        </section>
      </div>

      {/* 决议流：最新 4 条，展示证据链能力 */}
      <section className="card-pad">
        <SectionTitle extra={<span className="text-[11px] text-ink-400">按证据覆盖率排序</span>}>最新决议摘要</SectionTitle>
        <div className="grid gap-3 md:grid-cols-2">
          {(meetings.data?.items || []).slice(0, 2).map((m) => (
            <Link
              key={m.id}
              to={`/meetings/${m.id}`}
              className="group rounded-lg border border-ink-100 p-3.5 transition hover:border-brand-200 hover:bg-brand-50/30"
            >
              <div className="flex items-center gap-2 text-[11px] text-ink-400">
                <span className={clsx('chip', STATUS_META[m.status]?.cls)}>{STATUS_META[m.status]?.name}</span>
                <span>{fmtDate(m.meeting_date)}</span>
              </div>
              <p className="mt-2 line-clamp-2 text-[13px] font-medium leading-5 text-ink-800">{m.title}</p>
              <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-ink-500">{m.summary}</p>
              <div className="mt-2 flex items-center gap-2 text-[10px] text-ink-400">
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-600">
                  {KIND_META.decision.name} {m.counts.decisions}
                </span>
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-600">待办 {m.counts.actions}</span>
                <span className="ml-auto text-brand-600 opacity-0 transition group-hover:opacity-100">查看证据链 →</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
