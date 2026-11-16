import { useEffect, useRef, useState } from 'react';
import {
  BookOpen, FileText, Loader2, Send, Sparkles, Trash2, UploadCloud, ShieldCheck,
} from 'lucide-react';
import { clsx } from 'clsx';
import { api, askStream } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import type { ChatTurn, Citation } from '@/types';
import { EmptyState, ErrorBox, Loading, SectionTitle, useToast } from '@/components/ui';

const SUGGESTIONS = [
  '会议纪要模块的验收口径是什么？',
  '引用校验的阈值为什么从 0.55 调到 0.45？',
  '演示环境现在是什么配置，扛得住多少并发？',
  '模型路由的四个档位分别用在什么场景？',
];

export function KbPage() {
  const { push } = useToast();
  const docs = useAsync(() => api.kb(), []);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [question, setQuestion] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [stage, setStage] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.chatHistory().then((r) => setTurns(r.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, streaming]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || streaming) return;
    setQuestion('');
    setCitations([]);
    setStage('正在检索知识库…');
    setTurns((prev) => [...prev, { role: 'user', content: q }, { role: 'assistant', content: '' }]);
    setStreaming(true);

    await askStream(q, {
      onRetrieval: (p) => {
        const names = (p.sources || []).slice(0, 3).map((s) => `${s.doc} 第${s.page}页`);
        setStage(
          `召回 ${p.count ?? p.chunks} 段${names.length ? '：' + names.join('、') + (p.count > 3 ? ' 等' : '') : ''}，正在精排…`,
        );
      },
      onToken: (t) => {
        setStage('');
        setTurns((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + t };
          return next;
        });
      },
      onDone: (p) => {
        setCitations(p.citations || []);
        setTurns((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: p.answer || last.content, citations: p.citations };
          return next;
        });
        setStreaming(false);
        setStage('');
      },
      onError: (msg) => {
        push('error', msg);
        setStreaming(false);
        setStage('');
      },
    });
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    for (const f of Array.from(files)) {
      try {
        const r = await api.uploadKb(f);
        push('success', `${r.title} 已入库，切了 ${r.chunk_count} 段`);
      } catch (e) {
        push('error', `${f.name} 上传失败：${e instanceof Error ? e.message : '未知错误'}`);
      }
    }
    docs.reload();
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
      {/* 对话区 */}
      <section className="card flex min-h-[74vh] flex-col">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink-800">
            <Sparkles size={14} className="text-brand-500" />
            知识库问答
            <span className="chip bg-emerald-50 text-emerald-600">
              <ShieldCheck size={10} /> 逐句带引用
            </span>
            {citations.length > 0 && (
              <span className="chip bg-ink-100 text-ink-500">本轮召回 {citations.length} 段</span>
            )}
          </div>
          <button
            className="btn-ghost btn-sm"
            onClick={async () => {
              await api.clearChat();
              setTurns([]);
              setCitations([]);
            }}
          >
            <Trash2 size={12} /> 清空对话
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {!turns.length && (
            <div className="mx-auto max-w-xl pt-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <BookOpen size={22} />
              </div>
              <h3 className="mt-3 text-[15px] font-semibold text-ink-900">问问你的资料</h3>
              <p className="mt-1 text-[12px] leading-6 text-ink-500">
                先用 BM25 与向量各自召回，再用 RRF 融合、模型精排；回答里的每一句都会回查是否被引用片段支撑，
                支撑不足的句子会被标注出来而不是悄悄丢掉。
              </p>
              <div className="mt-4 grid gap-2 text-left sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="rounded-lg border border-ink-200 px-3 py-2 text-[11.5px] leading-5 text-ink-600 transition hover:border-brand-300 hover:bg-brand-50/40"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) => (
            <div key={i} className={clsx('flex gap-2.5', t.role === 'user' ? 'justify-end' : 'justify-start')}>
              {t.role === 'assistant' && (
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
                  <Sparkles size={13} />
                </span>
              )}
              <div
                className={clsx(
                  'max-w-[86%] rounded-xl px-3.5 py-2.5 text-[13px] leading-6',
                  t.role === 'user' ? 'bg-brand-600 text-white' : 'bg-ink-50 text-ink-800',
                )}
              >
                {t.content ? (
                  <p className="whitespace-pre-wrap">{t.content}</p>
                ) : (
                  <span className="inline-flex items-center gap-2 text-ink-400">
                    <Loader2 size={13} className="animate-spin" /> {stage || '思考中…'}
                  </span>
                )}
                {t.citations && t.citations.length > 0 && (
                  <div className="mt-2 border-t border-ink-200/70 pt-2">
                    <p className="mb-1 text-[10.5px] font-medium text-ink-500">引用来源 {t.citations.length} 处</p>
                    <div className="space-y-1">
                      {t.citations.slice(0, 4).map((c) => (
                        <div key={c.n} className="flex items-start gap-1.5 text-[10.5px] leading-4 text-ink-500">
                          <span className="shrink-0 rounded bg-white px-1 font-mono text-brand-600">[{c.n}]</span>
                          <span className="truncate">
                            《{c.doc}》 第 {c.page} 页 · {c.section}
                          </span>
                          <span
                            className={clsx(
                              'ml-auto shrink-0 rounded px-1',
                              c.support === 'strong' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700',
                            )}
                          >
                            {c.support === 'strong' ? '强支撑' : '弱支撑'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form
          className="flex items-center gap-2 border-t border-ink-100 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
        >
          <input
            className="input flex-1"
            placeholder="基于已入库资料提问，例如「引用校验阈值改成多少了」"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={streaming}
          />
          <button className="btn-primary" disabled={streaming || !question.trim()}>
            {streaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            提问
          </button>
        </form>
      </section>

      {/* 资料栏 */}
      <aside className="space-y-3">
        <section className="card-pad">
          <SectionTitle extra={<span className="text-[10.5px] text-ink-400">{docs.data?.total_chunks ?? 0} 片段</span>}>
            知识库资料
          </SectionTitle>
          <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed border-ink-300 px-3 py-5 text-center transition hover:border-brand-400 hover:bg-brand-50/30">
            <UploadCloud size={18} className="text-ink-400" />
            <span className="text-[11.5px] text-ink-600">点击上传 PDF / Word / Markdown</span>
            <span className="text-[10px] text-ink-400">单文件建议 20MB 以内</span>
            <input type="file" multiple className="hidden" accept=".pdf,.docx,.md,.txt,.html" onChange={(e) => upload(e.target.files)} />
          </label>

          {docs.loading && <Loading label="" />}
          {docs.error && <ErrorBox message={docs.error} onRetry={docs.reload} />}
          <ul className="mt-3 space-y-1.5">
            {(docs.data?.items || []).map((d) => (
              <li key={d.id} className="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-50">
                <FileText size={13} className="shrink-0 text-ink-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] text-ink-700">{d.title}</p>
                  <p className="text-[10px] text-ink-400">
                    {d.ext.toUpperCase()} · {d.chunk_count} 段 · {d.pages} 页
                  </p>
                </div>
                <button
                  className="opacity-0 transition group-hover:opacity-100"
                  onClick={async () => {
                    await api.deleteKb(d.id);
                    docs.reload();
                    push('info', '已删除');
                  }}
                >
                  <Trash2 size={12} className="text-ink-400 hover:text-rose-500" />
                </button>
              </li>
            ))}
            {!docs.loading && !docs.data?.items.length && (
              <EmptyState title="还没有资料" desc="上传一份产品文档或运维手册，问答会立刻基于它回答。" />
            )}
          </ul>
        </section>

        <section className="card-pad">
          <SectionTitle>回答是怎么来的</SectionTitle>
          <ol className="space-y-2 text-[11px] leading-5 text-ink-500">
            {[
              '把问题切成检索词，BM25 与向量各自召回 12 条',
              'RRF 融合两路排名，得到候选片段',
              '模型精排取前 6 条，拼成带页码的上下文',
              '流式生成答案，同时逐句回查引用支撑度',
            ].map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ink-100 text-[9px] font-semibold text-ink-500">
                  {i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
        </section>
      </aside>
    </div>
  );
}
