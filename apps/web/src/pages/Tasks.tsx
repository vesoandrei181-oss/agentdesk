import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Calculator, Loader2, Plus, Timer, Trash2, TriangleAlert } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtDate, PRIORITY_META } from '@/lib/format';
import type { EstimateResp, Task } from '@/types';
import { Avatar, ErrorBox, Loading, Modal, Segmented, useToast } from '@/components/ui';

const FLOW: Record<Task['status'], Task['status'][]> = {
  todo: ['doing'],
  doing: ['review', 'todo'],
  review: ['done', 'doing'],
  done: ['review'],
};
const STATUS_NAME: Record<Task['status'], string> = { todo: '待开始', doing: '进行中', review: '待验收', done: '已完成' };

export function TasksPage() {
  const board = useAsync(() => api.tasks(), []);
  const { push } = useToast();
  const [view, setView] = useState<'board' | 'table'>('board');
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);

  const columns = useMemo(() => {
    const cols = board.data?.columns || [];
    return cols.map((c) => ({ ...c, items: c.items.filter((t) => !filter || t.owner_name === filter) }));
  }, [board.data, filter]);

  async function move(task: Task, to: Task['status']) {
    try {
      await api.updateTask(task.id, { status: to });
      board.reload();
    } catch (e) {
      push('error', e instanceof Error ? e.message : '更新失败');
    }
  }

  if (board.loading) return <Loading label="加载任务看板" />;
  if (board.error) return <ErrorBox message={board.error} onRetry={board.reload} />;

  const allTasks = board.data!.columns.flatMap((c) => c.items);
  const risk = allTasks.filter((t) => t.status !== 'done' && t.risk_score >= 0.35);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          size="sm"
          value={view}
          onChange={setView}
          options={[
            { value: 'board', label: '看板' },
            { value: 'table', label: '表格' },
          ]}
        />
        <select className="input w-36 py-1.5 text-xs" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">全部负责人</option>
          {(board.data?.owners || []).map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <span className="text-[11px] text-ink-400">
          共 {board.data?.total ?? 0} 项 · 完成 {allTasks.filter((t) => t.status === 'done').length} 项
        </span>
        {!!risk.length && (
          <span className="chip bg-amber-50 text-amber-700">
            <TriangleAlert size={10} /> {risk.length} 项存在延期风险
          </span>
        )}
        <button className="btn-primary ml-auto" onClick={() => setCreating(true)}>
          <Plus size={15} /> 新建任务
        </button>
      </div>

      {view === 'board' ? (
        <div className="grid gap-3 lg:grid-cols-4">
          {columns.map((col) => (
            <div key={col.key} className="rounded-xl bg-ink-100/50 p-2">
              <div className="flex items-center justify-between px-1.5 py-1.5">
                <span className="text-[12px] font-medium text-ink-600">{col.name}</span>
                <span className="rounded bg-white px-1.5 text-[10px] text-ink-400">{col.items.length}</span>
              </div>
              <div className="space-y-2">
                {col.items.map((t) => (
                  <div key={t.id} className="group rounded-lg border border-ink-200/70 bg-white p-2.5 shadow-sm transition hover:shadow-card">
                    <div className="flex items-start justify-between gap-1.5">
                      <p className="text-[12.5px] font-medium leading-5 text-ink-800">{t.title}</p>
                      <span className={clsx('chip shrink-0', PRIORITY_META[t.priority]?.cls)}>{PRIORITY_META[t.priority]?.name}</span>
                    </div>
                    {t.description && (
                      <p className="mt-1 line-clamp-2 text-[10.5px] leading-4 text-ink-400">{t.description}</p>
                    )}
                    <div className="mt-2 flex items-center gap-1.5 text-[10px] text-ink-400">
                      <Avatar name={t.owner_name} size={14} />
                      <span className="truncate">{t.owner_name || '未指派'}</span>
                      <span className="ml-auto">{fmtDate(t.due_date)}</span>
                    </div>
                    {t.p90_days > 0 && (
                      <div className="mt-1.5 flex items-center gap-1">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100">
                          <div
                            className={clsx('h-full rounded-full', t.risk_score >= 0.5 ? 'bg-rose-400' : t.risk_score >= 0.3 ? 'bg-amber-400' : 'bg-emerald-400')}
                            style={{ width: `${Math.min(100, (t.p50_days / Math.max(t.p90_days, 0.1)) * 100)}%` }}
                          />
                        </div>
                        <span className="text-[9.5px] text-ink-400" title="P50 常见工期 / P90 保守工期">
                          P50 {t.p50_days} / P90 {t.p90_days} 天
                        </span>
                      </div>
                    )}
                    <div className="mt-1.5 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
                      {FLOW[t.status].includes('todo') && (
                        <button className="btn-ghost h-5 !px-1" onClick={() => move(t, 'todo')} title="移到待开始">
                          <ArrowLeft size={11} />
                        </button>
                      )}
                      {FLOW[t.status].map((next) => (
                        <button
                          key={next}
                          className="btn-ghost h-5 !px-1 text-[9.5px]"
                          onClick={() => move(t, next)}
                          title={`移到${STATUS_NAME[next]}`}
                        >
                          移到{STATUS_NAME[next]} <ArrowRight size={10} />
                        </button>
                      ))}
                      <button
                        className="btn-ghost ml-auto h-5 !px-1"
                        onClick={async () => {
                          await api.deleteTask(t.id);
                          board.reload();
                        }}
                      >
                        <Trash2 size={11} className="text-ink-300 hover:text-rose-500" />
                      </button>
                    </div>
                  </div>
                ))}
                {!col.items.length && (
                  <p className="px-2 py-6 text-center text-[11px] text-ink-400">暂无任务</p>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead>
              <tr>
                <th>任务</th>
                <th className="w-24">负责人</th>
                <th className="w-24">状态</th>
                <th className="w-20">优先级</th>
                <th className="w-24">截止</th>
                <th className="w-28">工期 P50 / P90</th>
                <th className="w-20">风险</th>
              </tr>
            </thead>
            <tbody>
              {columns.flatMap((c) => c.items).map((t) => (
                <tr key={t.id} className="hover:bg-ink-50/60">
                  <td>
                    <p className="text-[13px] font-medium text-ink-800">{t.title}</p>
                    {t.description && <p className="mt-0.5 line-clamp-1 text-[11px] text-ink-400">{t.description}</p>}
                  </td>
                  <td className="text-[12px]">{t.owner_name || '—'}</td>
                  <td>
                    <span className="chip bg-ink-100 text-ink-600">{STATUS_NAME[t.status]}</span>
                  </td>
                  <td>
                    <span className={clsx('chip', PRIORITY_META[t.priority]?.cls)}>{PRIORITY_META[t.priority]?.name}</span>
                  </td>
                  <td className="text-[12px] text-ink-500">{fmtDate(t.due_date)}</td>
                  <td className="text-[12px] tabular-nums text-ink-600">
                    {t.p50_days ? `${t.p50_days} / ${t.p90_days} 天` : '—'}
                  </td>
                  <td>
                    <span
                      className={clsx(
                        'text-[12px] font-medium tabular-nums',
                        t.risk_score >= 0.5 ? 'text-rose-600' : t.risk_score >= 0.3 ? 'text-amber-600' : 'text-emerald-600',
                      )}
                    >
                      {t.risk_score ? t.risk_score.toFixed(2) : '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateTaskModal
        open={creating}
        onClose={() => setCreating(false)}
        owners={board.data?.owners || []}
        onCreated={() => {
          board.reload();
          setCreating(false);
        }}
      />
    </div>
  );
}

function CreateTaskModal({
  open, onClose, owners, onCreated,
}: { open: boolean; onClose: () => void; owners: string[]; onCreated: () => void }) {
  const { push } = useToast();
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [owner, setOwner] = useState(owners[0] || '');
  const [priority, setPriority] = useState<Task['priority']>('medium');
  const [due, setDue] = useState('');
  const [estimate, setEstimate] = useState<EstimateResp | null>(null);
  const [busy, setBusy] = useState(false);

  async function runEstimate() {
    if (!title.trim()) return;
    try {
      const r = await api.estimate({ text: `${title} ${desc}`, priority, due_date: due || undefined, owner_name: owner });
      setEstimate(r);
    } catch (e) {
      push('error', e instanceof Error ? e.message : '预测失败');
    }
  }

  async function submit() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.createTask({
        title: title.trim(),
        description: desc,
        owner_name: owner,
        priority,
        due_date: due,
        p50_days: estimate?.p50_days ?? 0,
        p90_days: estimate?.p90_days ?? 0,
        risk_score: estimate ? (estimate.risk === 'high' ? 0.7 : estimate.risk === 'medium' ? 0.4 : 0.15) : 0,
        status: 'todo',
      });
      push('success', '任务已创建');
      setTitle('');
      setDesc('');
      setEstimate(null);
      onCreated();
    } catch (e) {
      push('error', e instanceof Error ? e.message : '创建失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建任务"
      desc="写清楚「做什么、做到什么程度」，工期预测会更准。"
      width="max-w-xl"
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>取消</button>
          <button className="btn-outline" onClick={runEstimate} disabled={!title.trim()}>
            <Calculator size={14} /> 预测工期
          </button>
          <button className="btn-primary" onClick={submit} disabled={busy || !title.trim()}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} 创建
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="label">任务标题</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="梳理会议纪要的验收口径" />
        </div>
        <div>
          <label className="label">描述（越具体，估算越准）</label>
          <textarea className="input h-20 resize-none" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="产出验收清单，覆盖三条主流程与两条异常分支" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="label">负责人</label>
            <select className="input" value={owner} onChange={(e) => setOwner(e.target.value)}>
              {owners.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <label className="label">优先级</label>
            <select className="input" value={priority} onChange={(e) => setPriority(e.target.value as Task['priority'])}>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>
          <div>
            <label className="label">截止日期</label>
            <input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </div>
        </div>

        {estimate && (
          <div className="rounded-lg border border-brand-100 bg-brand-50/50 p-3">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-brand-700">
              <Timer size={13} /> 工期预测
            </p>
            <div className="mt-2 grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-[10px] text-ink-400">P50</p>
                <p className="text-base font-semibold text-ink-800">{estimate.p50_days} 天</p>
              </div>
              <div>
                <p className="text-[10px] text-ink-400">P90</p>
                <p className="text-base font-semibold text-ink-800">{estimate.p90_days} 天</p>
              </div>
              <div>
                <p className="text-[10px] text-ink-400">置信度</p>
                <p className="text-base font-semibold text-ink-800">{(estimate.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
            {estimate.factors.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-[10.5px] leading-4 text-ink-500">
                {estimate.factors.map((f, i) => <li key={i}>· {f}</li>)}
              </ul>
            )}
            {estimate.slack_days !== null && (
              <p className={clsx('mt-1.5 text-[11px]', estimate.slack_days < 0 ? 'text-rose-600' : 'text-emerald-600')}>
                距截止日余量 {estimate.slack_days} 天
              </p>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
