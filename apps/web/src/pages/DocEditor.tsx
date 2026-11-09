import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Check, ChevronDown, ChevronUp, Loader2, Save, Sparkles, SplitSquareHorizontal, TriangleAlert,
} from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import type { DiffBlock, StyleProfile, WriteResult } from '@/types';
import { EmptyState, ErrorBox, Loading, Segmented, SectionTitle, useToast } from '@/components/ui';

const PRESETS = [
  '把语言改得更口语、更像人写的，去掉「赋能、闭环」这类词',
  '压缩到 300 字以内，保留所有数字与结论',
  '给每一段补一句结论句，方便领导快速扫读',
  '把待办拆成「谁 / 做什么 / 什么时候」三要素',
];

export function DocEditorPage() {
  const { id } = useParams();
  const did = Number(id);
  const nav = useNavigate();
  const { push } = useToast();
  const doc = useAsync(() => api.doc(did), [did]);
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [instruction, setInstruction] = useState(PRESETS[0]);
  const [result, setResult] = useState<WriteResult | null>(null);
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState<'write' | 'apply' | 'save' | null>(null);
  const [view, setView] = useState<'edit' | 'preview'>('edit');

  useEffect(() => {
    if (doc.data) {
      setContent(doc.data.content);
      setTitle(doc.data.title);
    }
  }, [doc.data]);

  const dirty = doc.data ? content !== doc.data.content : false;

  // 只有 replace / insert / delete 可以勾选；equal 与 skip 是上下文
  const changes = useMemo(
    () =>
      (result?.blocks || [])
        .map((block, idx) => ({ block, idx }))
        .filter((x) => x.block.type !== 'equal' && x.block.type !== 'skip'),
    [result],
  );

  async function runWrite() {
    if (!instruction.trim()) return;
    setBusy('write');
    try {
      const r = await api.writeDoc(did, instruction.trim());
      setResult(r);
      // 默认全选，用户可以逐条取消——比起「全部照做」，逐条确认更贴近真实编辑习惯
      setAccepted(new Set(r.blocks.map((b, i) => (b.type === 'equal' || b.type === 'skip' ? -1 : i)).filter((i) => i >= 0)));
      const n = r.blocks.filter((b) => b.type !== 'equal' && b.type !== 'skip').length;
      push(n ? 'success' : 'info', n ? `生成 ${n} 处修改建议` : '模型认为这段文字不用改');
    } catch (e) {
      push('error', e instanceof Error ? e.message : '改写失败');
    } finally {
      setBusy(null);
    }
  }

  async function applyBlocks() {
    setBusy('apply');
    try {
      const r = await api.applyDoc(did, { blocks: result!.blocks, accepted: [...accepted] });
      setContent(r.content);
      setResult(null);
      doc.reload();
      push('success', `已应用并升级到 v${r.version}`);
    } catch (e) {
      push('error', e instanceof Error ? e.message : '应用失败');
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy('save');
    try {
      await api.saveDoc(did, { title, content });
      doc.reload();
      push('success', '已保存');
    } catch (e) {
      push('error', e instanceof Error ? e.message : '保存失败');
    } finally {
      setBusy(null);
    }
  }

  if (doc.loading) return <Loading label="打开文档" />;
  if (doc.error) return <ErrorBox message={doc.error} onRetry={doc.reload} />;

  const stats = result?.stats;
  const riskList: string[] = (result?.risks || []).map((r) =>
    typeof r === 'string' ? r : String((r as Record<string, unknown>).text ?? (r as Record<string, unknown>).detail ?? JSON.stringify(r)),
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button className="btn-ghost btn-sm -ml-2 text-ink-500" onClick={() => nav('/docs')}>
          <ArrowLeft size={14} /> 文档列表
        </button>
        <input
          className="ml-1 min-w-0 flex-1 truncate border-none bg-transparent text-[15px] font-semibold text-ink-900 outline-none focus:ring-0"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <span className="shrink-0 text-[11px] text-ink-400">v{doc.data!.version} · {content.length} 字</span>
        <button className="btn-outline btn-sm" onClick={save} disabled={busy !== null || !dirty}>
          {busy === 'save' ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} 保存
        </button>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.45fr_1fr]">
        {/* 左：编辑器 */}
        <section className="card flex min-h-[70vh] flex-col">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-2">
            <Segmented
              size="sm"
              value={view}
              onChange={setView}
              options={[
                { value: 'edit', label: '编辑' },
                { value: 'preview', label: '预览' },
              ]}
            />
            {dirty && <span className="text-[10.5px] text-amber-600">有未保存修改</span>}
          </div>
          {view === 'edit' ? (
            <textarea
              className="flex-1 resize-none rounded-b-xl border-none bg-white p-5 font-mono text-[13px] leading-7 text-ink-800 outline-none"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <div className="prose-doc flex-1 overflow-y-auto p-6">
              <MarkdownLite text={content} />
            </div>
          )}
        </section>

        {/* 右：AI 改写 */}
        <section className="space-y-3">
          <div className="card-pad">
            <SectionTitle extra={<Sparkles size={13} className="text-brand-400" />}>一句指令改写</SectionTitle>
            <textarea
              className="input h-20 resize-none text-[12.5px] leading-6"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="例如：把第二段改成给领导看的汇报口吻，控制在 100 字"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  onClick={() => setInstruction(p)}
                  className="rounded-full bg-ink-100 px-2 py-0.5 text-[10.5px] text-ink-500 transition hover:bg-brand-100 hover:text-brand-700"
                >
                  {p.slice(0, 14)}…
                </button>
              ))}
            </div>
            <button className="btn-primary mt-3 w-full" onClick={runWrite} disabled={busy !== null}>
              {busy === 'write' ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {busy === 'write' ? '模型正在改写…' : '生成修改建议'}
            </button>
          </div>

          {result && (
            <>
              <div className="card-pad">
                <div className="flex items-center justify-between">
                  <SectionTitle>文本体检</SectionTitle>
                  <span className="mb-3 text-[10.5px] text-ink-400">规则算的，不花 token</span>
                </div>
                <StyleCompare before={result.style_before} after={result.style_after} />
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                  <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-600">+{stats?.added ?? 0} 行</span>
                  <span className="rounded bg-rose-50 px-1.5 py-0.5 text-rose-600">−{stats?.removed ?? 0} 行</span>
                  <span>改动比例 {Math.round((stats?.edit_ratio ?? 0) * 100)}%</span>
                  <span>句长变化 {stats?.avg_sentence_delta ?? 0}</span>
                </div>
                {!!result.notes?.length && (
                  <ul className="mt-2 space-y-1 text-[11.5px] leading-5 text-ink-500">
                    {result.notes.map((n, i) => (
                      <li key={i}>· {n}</li>
                    ))}
                  </ul>
                )}
                {!!riskList.length && (
                  <div className="mt-2 rounded-lg bg-amber-50 p-2.5">
                    <p className="flex items-center gap-1 text-[11px] font-medium text-amber-700">
                      <TriangleAlert size={11} /> 复核提醒
                    </p>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11px] leading-5 text-amber-700">
                      {riskList.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              <div className="card">
                <div className="flex items-center justify-between border-b border-ink-100 px-4 py-2.5">
                  <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-800">
                    <SplitSquareHorizontal size={13} className="text-brand-500" />
                    差异确认
                    <span className="text-[10.5px] font-normal text-ink-400">
                      {accepted.size}/{changes.length} 已选
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button className="btn-ghost btn-sm" onClick={() => setAccepted(new Set(changes.map((c) => c.idx)))}>全选</button>
                    <button className="btn-ghost btn-sm" onClick={() => setAccepted(new Set())}>清空</button>
                  </div>
                </div>
                <div className="max-h-[42vh] space-y-2 overflow-y-auto p-3">
                  {!changes.length && (
                    <EmptyState title="模型认为无需修改" desc="可以换一条更具体的指令，例如指出要改哪一段、改成什么口吻。" />
                  )}
                  {changes.map(({ block, idx }) => (
                    <DiffCard
                      key={idx}
                      idx={idx}
                      block={block}
                      checked={accepted.has(idx)}
                      onToggle={() =>
                        setAccepted((prev) => {
                          const next = new Set(prev);
                          if (next.has(idx)) next.delete(idx);
                          else next.add(idx);
                          return next;
                        })
                      }
                    />
                  ))}
                </div>
                <div className="flex justify-end gap-2 border-t border-ink-100 px-4 py-3">
                  <button className="btn-ghost" onClick={() => setResult(null)}>放弃</button>
                  <button className="btn-primary" onClick={applyBlocks} disabled={!accepted.size || busy !== null}>
                    {busy === 'apply' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    应用所选修改
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

const TYPE_META: Record<string, { name: string; cls: string }> = {
  replace: { name: '改写', cls: 'bg-brand-50 text-brand-600' },
  insert: { name: '新增', cls: 'bg-emerald-50 text-emerald-600' },
  delete: { name: '删除', cls: 'bg-rose-50 text-rose-600' },
};

function DiffCard({
  idx, block, checked, onToggle,
}: { idx: number; block: DiffBlock; checked: boolean; onToggle: () => void }) {
  const [open, setOpen] = useState(false);
  const meta = TYPE_META[block.type] || TYPE_META.replace;
  const after = (block.new || []).join('\n');
  const before = (block.old || []).join('\n');

  return (
    <div className={clsx('rounded-lg border p-2.5 transition', checked ? 'border-brand-200 bg-brand-50/30' : 'border-ink-100')}>
      <div className="flex items-start gap-2">
        <button
          onClick={onToggle}
          className={clsx(
            'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition',
            checked ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-300 bg-white',
          )}
          aria-label="选择此修改"
        >
          {checked && <Check size={11} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className={clsx('chip', meta.cls)}>{meta.name}</span>
            <span className="text-[10.5px] text-ink-400">第 {idx} 块</span>
            <button className="ml-auto text-ink-400 hover:text-ink-600" onClick={() => setOpen((o) => !o)}>
              {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
          </div>
          <p className={clsx('mt-1 whitespace-pre-wrap text-[12px] leading-5 text-ink-700', !open && 'line-clamp-2')}>
            {after || before || '（空行）'}
          </p>
          {open && before && (
            <p className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-rose-50/60 px-2 py-1 text-[11.5px] leading-5 text-rose-700 line-through decoration-rose-300">
              {before}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function StyleCompare({ before, after }: { before: StyleProfile; after: StyleProfile }) {
  const rows: { k: string; v: (s: StyleProfile) => string }[] = [
    { k: '平均句长', v: (s) => `${(s.avg_sentence ?? 0).toFixed(1)} 字` },
    { k: '最长句', v: (s) => `${s.max_sentence ?? 0} 字` },
    { k: '程度副词/套话', v: (s) => `${s.fillers ?? 0} 处` },
    { k: '规则问题', v: (s) => `${(s.issues || []).length} 条` },
  ];
  return (
    <div className="space-y-2">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-ink-400">
            <th className="pb-1 text-left font-normal">指标</th>
            <th className="pb-1 text-right font-normal">改写前</th>
            <th className="pb-1 text-right font-normal">改写后</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const a = r.v(before);
            const b = r.v(after);
            return (
              <tr key={r.k} className="border-t border-ink-100">
                <td className="py-1 text-ink-500">{r.k}</td>
                <td className="py-1 text-right text-ink-400">{a}</td>
                <td className={clsx('py-1 text-right font-medium', a === b ? 'text-ink-500' : 'text-emerald-600')}>{b}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!!(after.issues || []).length && (
        <ul className="space-y-0.5 rounded-lg bg-ink-50 p-2 text-[10.5px] leading-4 text-ink-500">
          {after.issues.slice(0, 3).map((i, n) => <li key={n}>· {i}</li>)}
        </ul>
      )}
    </div>
  );
}

/** 极简 Markdown 渲染：只处理标题、列表、粗体、行内代码，够演示用且不引依赖。 */
function MarkdownLite({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, i) => {
        const lines = block.split('\n');
        if (lines[0]?.startsWith('### ')) return <h3 key={i}>{inline(lines[0].slice(4))}</h3>;
        if (lines[0]?.startsWith('## ')) return <h2 key={i}>{inline(lines[0].slice(3))}</h2>;
        if (lines[0]?.startsWith('# ')) return <h1 key={i}>{inline(lines[0].slice(2))}</h1>;
        if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
          return (
            <ul key={i}>
              {lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*]\s+/, ''))}</li>)}
            </ul>
          );
        }
        if (lines.every((l) => /^\s*\d+[.、]\s*/.test(l))) {
          return (
            <ol key={i}>
              {lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*\d+[.、]\s*/, ''))}</li>)}
            </ol>
          );
        }
        return <p key={i}>{inline(block)}</p>;
      })}
    </>
  );
}

function inline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith('`') && p.endsWith('`')) return <code key={i}>{p.slice(1, -1)}</code>;
    return <span key={i}>{p}</span>;
  });
}

export { MarkdownLite };
