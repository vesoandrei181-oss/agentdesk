import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileUp, Loader2, Mic, Plus, Search, Sparkles, Users } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync, useDebounced } from '@/lib/hooks';
import { fmtDate, fmtDuration, fmtStamp, STATUS_META } from '@/lib/format';
import { DEMO_TRANSCRIPT, parseTranscript } from '@/lib/transcript';
import { Avatar, EmptyState, ErrorBox, Loading, Modal, SectionTitle, useToast } from '@/components/ui';

export function MeetingsPage() {
  const list = useAsync(() => api.meetings(), []);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const query = useDebounced(q, 200);

  const items = (list.data?.items || []).filter(
    (m) => !query || m.title.includes(query) || (m.summary || '').includes(query),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            className="input w-64 pl-8"
            placeholder="搜索会议标题或摘要"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <span className="text-xs text-ink-400">
          共 {list.data?.total ?? 0} 场，已完成 {list.data?.items.filter((m) => m.status === 'ready').length ?? 0} 场
        </span>
        <button className="btn-primary ml-auto" onClick={() => setOpen(true)}>
          <Plus size={15} /> 新建会议
        </button>
      </div>

      {list.loading && <Loading />}
      {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}

      {!list.loading && !list.error && (
        <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {items.map((m) => (
            <Link key={m.id} to={`/meetings/${m.id}`} className="card group p-4 transition hover:border-brand-200 hover:shadow-pop">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={clsx('chip', STATUS_META[m.status]?.cls)}>{STATUS_META[m.status]?.name}</span>
                    <span className="text-[11px] text-ink-400">{fmtDate(m.meeting_date)}</span>
                    <span className="text-[11px] text-ink-300">·</span>
                    <span className="text-[11px] text-ink-400">{fmtDuration(m.duration_ms)}</span>
                  </div>
                  <h3 className="mt-2 truncate text-[14px] font-semibold text-ink-900 group-hover:text-brand-700">
                    {m.title}
                  </h3>
                </div>
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <Mic size={16} />
                </div>
              </div>

              <p className="mt-2 line-clamp-2 min-h-[34px] text-[12px] leading-[17px] text-ink-500">
                {m.summary || '尚未生成摘要'}
              </p>

              <div className="mt-3 flex items-center gap-3 border-t border-ink-100 pt-2.5 text-[11px] text-ink-400">
                <span className="inline-flex items-center gap-1">
                  <Users size={11} /> {m.attendees?.length || 0} 人
                </span>
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-600">决议 {m.counts.decisions}</span>
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-600">待办 {m.counts.actions}</span>
                <span className="ml-auto inline-flex items-center gap-1">
                  {m.counts.segments} 段
                </span>
              </div>

              <div className="mt-2 flex items-center -space-x-1.5">
                {(m.attendees || []).slice(0, 5).map((a) => (
                  <span key={a} className="ring-2 ring-white">
                    <Avatar name={a} size={20} />
                  </span>
                ))}
              </div>
            </Link>
          ))}
          {!items.length && (
            <div className="col-span-full">
              <EmptyState
                icon={<Mic size={22} />}
                title={query ? '没有匹配的会议' : '还没有会议记录'}
                desc={query ? '换个关键词试试。' : '粘贴一段转写文本，六个 Agent 会帮你把决议和待办抽出来。'}
                action={<button className="btn-outline btn-sm" onClick={() => setOpen(true)}>新建会议</button>}
              />
            </div>
          )}
        </div>
      )}

      <CreateMeetingModal open={open} onClose={() => setOpen(false)} onCreated={() => list.reload()} />
    </div>
  );
}

function CreateMeetingModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const nav = useNavigate();
  const { push } = useToast();
  const [title, setTitle] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [attendees, setAttendees] = useState('孟嘉祺, 杜春晓, 赵鹏');
  const [raw, setRaw] = useState(DEMO_TRANSCRIPT);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState('');

  const parsed = useMemo(() => (raw.trim() ? parseTranscript(raw) : []), [raw]);

  async function submit(sync = false) {
    if (!title.trim() || !parsed.length) return;
    setBusy(true);
    setStage('正在创建会议…');
    try {
      const people = attendees.split(/[,，、\s]+/).map((s) => s.trim()).filter(Boolean);
      const { id } = await api.createMeeting({
        title: title.trim(),
        meeting_date: date,
        attendees: people,
        source_type: 'paste',
      });
      setStage(`正在写入 ${parsed.length} 段转写…`);
      await api.addSegments(id, parsed);
      setStage(sync ? '正在同步分析（约 30–60 秒）…' : '已提交后台分析…');
      await api.analyze(id, sync);
      push('success', sync ? '分析完成' : '已提交分析，进入详情页可看实时进度');
      onCreated();
      onClose();
      nav(`/meetings/${id}`);
    } catch (e) {
      push('error', e instanceof Error ? e.message : '创建失败');
    } finally {
      setBusy(false);
      setStage('');
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建会议纪要"
      desc="支持粘贴转写文本；也接受带 [mm:ss] 时间戳与「说话人：」前缀的格式。"
      width="max-w-3xl"
      footer={
        <>
          <button className="btn-ghost" onClick={onClose} disabled={busy}>取消</button>
          <button className="btn-outline" onClick={() => submit(false)} disabled={busy || !parsed.length}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />} 后台分析
          </button>
          <button className="btn-primary" onClick={() => submit(true)} disabled={busy || !parsed.length}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} 立即分析
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">会议标题</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：九月上线准备会" />
          </div>
          <div>
            <label className="label">会议日期</label>
            <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">参会人（逗号分隔）</label>
          <input className="input" value={attendees} onChange={(e) => setAttendees(e.target.value)} />
        </div>
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="label !mb-0">转写文本</label>
            <span className="text-[11px] text-ink-400">
              已解析 {parsed.length} 段
              {parsed.length > 0 && ` · ${fmtStamp(parsed[0].start_ms)} → ${fmtStamp(parsed[parsed.length - 1].end_ms)}`}
            </span>
          </div>
          <textarea
            className="input h-56 resize-none font-mono text-[12px] leading-6"
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder={'[00:12] 孟嘉祺：先定一下九月上线的范围…'}
          />
        </div>
        {parsed.length > 0 && (
          <div className="rounded-lg border border-ink-100 bg-ink-50/50 p-3">
            <SectionTitle extra={<span className="text-[10px] text-ink-400">前 4 段预览</span>}>解析结果</SectionTitle>
            <ul className="space-y-1.5">
              {parsed.slice(0, 4).map((p) => (
                <li key={p.idx} className="flex gap-2 text-[11px] leading-5">
                  <span className="w-10 shrink-0 font-mono text-ink-400">{fmtStamp(p.start_ms)}</span>
                  <span className="w-14 shrink-0 truncate font-medium text-ink-600">{p.speaker || '未标注'}</span>
                  <span className="line-clamp-1 text-ink-500">{p.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {stage && <p className="text-[11px] text-brand-600">{stage}</p>}
      </div>
    </Modal>
  );
}
