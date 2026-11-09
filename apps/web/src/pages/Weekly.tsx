import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarRange, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtDate, fmtPct } from '@/lib/format';
import { Avatar, CopyButton, ErrorBox, Loading, Progress, SectionTitle, useToast } from '@/components/ui';
import { BarRow } from '@/components/charts';

export function WeeklyPage() {
  // 首屏只取数据面板，正文由「生成」按钮触发，避免每次进页面都等模型
  const weekly = useAsync(() => api.weekly(0), []);
  const { push } = useToast();
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const fresh = await api.weekly(1);
      weekly.setData(fresh);
      push('success', '已按当前任务状态重新生成');
    } catch (e) {
      push('error', e instanceof Error ? e.message : '生成失败');
    } finally {
      setBusy(false);
    }
  }

  if (weekly.loading) return <Loading label="汇总本周数据" />;
  if (weekly.error) return <ErrorBox message={weekly.error} onRetry={weekly.reload} />;
  const data = weekly.data!;
  const d = data.digest;
  const report = data.report;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <section className="card flex flex-col">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink-800">
            <CalendarRange size={14} className="text-brand-500" />
            自动生成的周报
            <span className="chip bg-brand-50 text-brand-600">
              <Sparkles size={10} /> 覆盖 {fmtPct(d.coverage, 0)} 任务
            </span>
          </div>
          <div className="flex gap-1.5">
            {report && <CopyButton text={data.text} label="复制全文" />}
            <button className="btn-outline btn-sm" onClick={generate} disabled={busy}>
              {busy ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {report ? '重新生成' : '生成本周周报'}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {busy && !report && (
            <div className="flex items-center gap-2 py-16 text-[12px] text-ink-400">
              <Loader2 size={14} className="animate-spin" />
              正在把 {d.totals.tasks} 条任务、{d.meetings.length} 场会议汇成正文，约需 20-40 秒
            </div>
          )}

          {!busy && !report && (
            <div className="mx-auto max-w-md py-14 text-center">
              <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <CalendarRange size={20} />
              </div>
              <h3 className="mt-3 text-[14px] font-semibold text-ink-900">本周还没有生成正文</h3>
              <p className="mt-1.5 text-[12px] leading-6 text-ink-500">
                右侧数据是本地实时算出来的：按人聚合、覆盖率、风险任务都不用等模型。
                点右上角生成，模型会把同样的数字写成有主次的周报正文，并记一条可回查的调用轨迹。
              </p>
              <button className="btn-primary mt-4" onClick={generate}>
                <Sparkles size={13} /> 生成本周周报
              </button>
            </div>
          )}

          {report && (
            <article className="prose-doc">
              <h1 className="text-[19px] font-semibold leading-8 text-ink-900">{report.headline}</h1>
              {report.sections.map((s, i) => (
                <section key={i} className="mt-5">
                  <h2 className="flex items-center gap-1.5 text-[13.5px] font-semibold text-ink-800">
                    <span className="h-3 w-0.5 rounded bg-brand-500" />
                    {s.title}
                  </h2>
                  <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-7 text-ink-700">{s.content}</p>
                </section>
              ))}
            </article>
          )}
        </div>

        {data.trace_id && (
          <div className="border-t border-ink-100 px-5 py-2.5 text-[10.5px] text-ink-400">
            本次生成记录为 Run #{data.trace_id}，
            <Link to={`/runs/${data.trace_id}`} className="text-brand-600 hover:underline">查看调用轨迹</Link>
          </div>
        )}
      </section>

      <aside className="space-y-3">
        <section className="card-pad">
          <SectionTitle extra={<span className="text-[10.5px] text-ink-400">按人聚合</span>}>团队产出</SectionTitle>
          <ul className="space-y-3">
            {d.owners.map((o) => (
              <li key={o.owner}>
                <div className="flex items-center gap-2">
                  <Avatar name={o.owner} size={22} />
                  <span className="text-[12.5px] font-medium text-ink-800">{o.owner}</span>
                  <span className="ml-auto text-[10.5px] text-ink-400">
                    {o.done}/{o.total} 完成
                  </span>
                </div>
                <div className="mt-1.5">
                  <Progress value={o.total ? o.done / o.total : 0} tone={o.risk > 0 ? 'amber' : 'emerald'} />
                </div>
                <div className="mt-1 flex gap-2 text-[10px] text-ink-400">
                  <span>进行 {o.doing}</span>
                  <span>待开始 {o.todo}</span>
                  {o.risk > 0 && <span className="text-amber-600">风险 {o.risk}</span>}
                  <span className="ml-auto">剩余 {o.hours_left.toFixed(0)} 小时</span>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card-pad">
          <SectionTitle>本周会议</SectionTitle>
          <div className="space-y-1.5">
            {d.meetings.map((m) => (
              <Link
                key={m.id}
                to={`/meetings/${m.id}`}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-ink-600 transition hover:bg-ink-50"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
                <span className="truncate">{m.title}</span>
                <span className="ml-auto shrink-0 text-[10px] text-ink-400">{fmtDate(m.date)}</span>
              </Link>
            ))}
            {!d.meetings.length && <p className="text-[11px] text-ink-400">本周没有会议记录。</p>}
          </div>
        </section>

        <section className="card-pad">
          <SectionTitle>任务分布</SectionTitle>
          <div className="space-y-2">
            <BarRow name="已完成" value={d.totals.done} max={d.totals.tasks} suffix={` / ${d.totals.tasks}`} color="bg-emerald-500" />
            <BarRow name="有风险" value={d.totals.risk} max={d.totals.tasks} suffix={` / ${d.totals.tasks}`} color="bg-amber-500" />
          </div>
          <p className={clsx('mt-3 rounded-lg px-2.5 py-2 text-[10.5px] leading-4',
            d.coverage >= 0.8 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>
            任务覆盖率指「有负责人且写了截止日」的比例。覆盖率低的时候，周报里的数字会偏乐观，建议先补齐字段。
          </p>
        </section>
      </aside>
    </div>
  );
}
