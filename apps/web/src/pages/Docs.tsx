import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FilePlus2, FileText, Loader2, Plus, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtDateTime } from '@/lib/format';
import { EmptyState, ErrorBox, Loading, Modal, SectionTitle, useToast } from '@/components/ui';

export function DocsPage() {
  const list = useAsync(() => api.docs(), []);
  const templates = useAsync(() => api.templates(), []);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<'blank' | 'template'>('template');
  const [title, setTitle] = useState('');
  const [tplId, setTplId] = useState('');
  const [busy, setBusy] = useState(false);
  const { push } = useToast();
  const nav = useNavigate();

  const tpl = templates.data?.items.find((t) => t.id === tplId);

  async function create() {
    setBusy(true);
    try {
      const content = mode === 'template' ? tpl?.content || '' : '# 未命名文档\n\n';
      const finalTitle = title.trim() || tpl?.name || '未命名文档';
      const { id } = await api.createDoc({ title: finalTitle, content });
      setOpen(false);
      push('success', '文档已创建');
      nav(`/docs/${id}`);
    } catch (e) {
      push('error', e instanceof Error ? e.message : '创建失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-500">
          模板生成 → 一句话指令改写 → 逐句差异确认。每一步改动都能看到「改了什么、为什么改」。
        </p>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <Plus size={15} /> 新建文档
        </button>
      </div>

      {list.loading && <Loading />}
      {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}

      {!list.loading && !list.error && (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {(list.data?.items || []).map((d) => (
            <Link key={d.id} to={`/docs/${d.id}`} className="card group p-4 transition hover:border-brand-200 hover:shadow-pop">
              <div className="flex items-start justify-between gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
                  <FileText size={15} />
                </div>
                <span className="text-[10px] text-ink-400">v{d.version}</span>
              </div>
              <h3 className="mt-2.5 truncate text-[14px] font-semibold text-ink-900 group-hover:text-brand-700">{d.title}</h3>
              <p className="mt-1 line-clamp-2 min-h-[32px] text-[11.5px] leading-4 text-ink-400">
                {d.preview.replace(/[#*`]/g, '').slice(0, 90) || '空白文档'}
              </p>
              <div className="mt-2.5 flex items-center justify-between border-t border-ink-100 pt-2 text-[10.5px] text-ink-400">
                <span>{d.word_count} 字</span>
                <span>{fmtDateTime(d.updated_at)}</span>
              </div>
            </Link>
          ))}
          {!list.data?.items.length && (
            <div className="col-span-full">
              <EmptyState
                icon={<FileText size={22} />}
                title="还没有文档"
                desc="从周报、会议纪要、项目方案或通知模板开始，也可以建一篇空白文档。"
              />
            </div>
          )}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="新建文档"
        desc="模板只是起点，后续可以用一句话指令逐段重写。"
        width="max-w-2xl"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setOpen(false)}>取消</button>
            <button className="btn-primary" onClick={create} disabled={busy}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <FilePlus2 size={14} />} 创建并打开
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {(['template', 'blank'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`rounded-lg border px-3 py-2.5 text-left transition ${
                  mode === m ? 'border-brand-300 bg-brand-50/60' : 'border-ink-200 hover:border-ink-300'
                }`}
              >
                <p className="text-[13px] font-medium text-ink-800">{m === 'template' ? '从模板开始' : '空白文档'}</p>
                <p className="mt-0.5 text-[11px] text-ink-400">
                  {m === 'template' ? '周报 / 纪要 / 方案 / 通知' : 'Markdown 空白页'}
                </p>
              </button>
            ))}
          </div>

          {mode === 'template' && (
            <div>
              <label className="label">选择模板</label>
              <div className="grid gap-2 sm:grid-cols-2">
                {(templates.data?.items || []).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTplId(t.id)}
                    className={`rounded-lg border px-3 py-2 text-left transition ${
                      tplId === t.id ? 'border-brand-300 bg-brand-50/50' : 'border-ink-200 hover:border-ink-300'
                    }`}
                  >
                    <p className="text-[12.5px] font-medium text-ink-800">{t.name}</p>
                    <p className="mt-0.5 line-clamp-2 text-[10.5px] leading-4 text-ink-400">{t.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="label">文档标题（留空用模板名）</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="第 35 周项目周报" />
          </div>

          {mode === 'template' && tpl && (
            <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-3">
              <SectionTitle extra={<span className="text-[10px] text-ink-400">{tpl.content.length} 字</span>}>模板预览</SectionTitle>
              <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 text-ink-500">{tpl.content}</pre>
            </div>
          )}
          <p className="flex items-center gap-1.5 text-[11px] text-ink-400">
            <Sparkles size={12} /> 创建后可以用「把第二段改得更像人写的」「压缩到 300 字」这类指令直接改写。
          </p>
        </div>
      </Modal>
    </div>
  );
}
