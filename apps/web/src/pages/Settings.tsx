import { useState } from 'react';
import { CheckCircle2, Database, Gauge, Loader2, RefreshCw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtPct } from '@/lib/format';
import { ErrorBox, Loading, SectionTitle, useToast } from '@/components/ui';

const TIERS: { key: string; name: string; desc: string; detail: string }[] = [
  { key: 'quality', name: '质量优先', desc: '关键 Agent 走大模型', detail: '决议与拆解用 v4-pro，其余降级；适合对外交付前跑一遍。' },
  { key: 'balanced', name: '均衡（默认）', desc: '全部走快模型', detail: '实测抽取质量与 pro 持平，延迟从 410s 降到约 130s。' },
  { key: 'cheap', name: '成本优先', desc: '压低温度与预算', detail: '适合批量回溯历史会议，个别条目可能需要人工补。' },
  { key: 'local', name: '本地模型', desc: 'Ollama 兼容端点', detail: '数据不出内网；质量取决于本地模型规模。' },
];

export function SettingsPage() {
  const runtime = useAsync(() => api.runtime(), []);
  const cache = useAsync(() => api.cache(), []);
  const { push } = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  async function patch(body: Record<string, unknown>, key: string) {
    setBusy(key);
    try {
      await api.setRuntime(body);
      await runtime.reload();
      push('success', '设置已生效');
    } catch (e) {
      push('error', e instanceof Error ? e.message : '保存失败');
    } finally {
      setBusy(null);
    }
  }

  if (runtime.loading) return <Loading label="读取运行时配置" />;
  if (runtime.error) return <ErrorBox message={runtime.error} onRetry={runtime.reload} />;
  const rt = runtime.data!;

  return (
    <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
      <div className="space-y-4">
        <section className="card-pad">
          <SectionTitle extra={<span className="text-[10.5px] text-ink-400">切换后下一次调用立即生效</span>}>模型路由档位</SectionTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            {TIERS.map((t) => {
              const active = rt.tier === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => patch({ tier: t.key }, t.key)}
                  disabled={busy !== null}
                  className={clsx(
                    'rounded-lg border p-3 text-left transition',
                    active ? 'border-brand-300 bg-brand-50/50' : 'border-ink-200 hover:border-ink-300',
                  )}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-[13px] font-medium text-ink-800">{t.name}</span>
                    {active && <CheckCircle2 size={13} className="text-brand-600" />}
                    {busy === t.key && <Loader2 size={12} className="animate-spin text-ink-400" />}
                  </div>
                  <p className="mt-0.5 text-[11px] font-medium text-ink-500">{t.desc}</p>
                  <p className="mt-1 text-[10.5px] leading-4 text-ink-400">{t.detail}</p>
                </button>
              );
            })}
          </div>
        </section>

        <section className="card-pad">
          <SectionTitle>Agent 路由表</SectionTitle>
          <table className="table-base">
            <thead>
              <tr>
                <th>Agent</th>
                <th className="w-40">模型</th>
                <th className="w-20 text-right">温度</th>
                <th className="w-24 text-right">思考链</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(rt.table).map(([agent, row]) => (
                <tr key={agent}>
                  <td className="font-mono text-[11.5px] text-ink-600">{agent}</td>
                  <td>
                    <span
                      className={clsx(
                        'rounded px-1.5 py-0.5 font-mono text-[10px]',
                        row.model.includes('pro') ? 'bg-brand-50 text-brand-600' : 'bg-ink-100 text-ink-500',
                      )}
                    >
                      {row.model}
                    </span>
                  </td>
                  <td className="text-right tabular-nums text-[12px]">{row.temperature}</td>
                  <td className="text-right text-[11px] text-ink-500">
                    {row.thinking === 'on' ? '开启' : '关闭'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[10.5px] leading-5 text-ink-400">
            抽取类 Agent 关闭思考链是实测结论：v4-pro 开启思考时 4000 token 预算会被推理过程吃光，正文返回为空；
            关掉之后同一条提示词 3.9 秒出结果，决议条数与质量都不掉。
          </p>
        </section>
      </div>

      <div className="space-y-4">
        <section className="card-pad">
          <SectionTitle extra={<Gauge size={13} className="text-ink-300" />}>服务状态</SectionTitle>
          <dl className="space-y-2 text-[12px]">
            {[
              ['Provider', rt.provider],
              ['接入地址', rt.base_url],
              ['离线模式', rt.mock ? '是（使用内置样例）' : '否'],
              ['单次 Token 预算', `${rt.budget}`],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <dt className="text-ink-400">{k}</dt>
                <dd className="truncate font-medium text-ink-700">{v}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="card-pad">
          <SectionTitle>隐私与缓存</SectionTitle>
          <div className="space-y-3">
            <Toggle
              icon={<ShieldCheck size={14} />}
              title="PII 脱敏网关"
              desc="身份证、银行卡、手机号、邮箱在进入模型前替换成占位符，返回后再还原。"
              checked={rt.pii_mask}
              busy={busy === 'pii'}
              onChange={(v) => patch({ pii_mask: v }, 'pii')}
            />
            <Toggle
              icon={<Database size={14} />}
              title="语义缓存"
              desc={`相似度 ≥ ${rt.cache_threshold} 的重复请求直接复用上次结果，省 token 也省等待。`}
              checked={rt.semantic_cache}
              busy={busy === 'cache'}
              onChange={(v) => patch({ semantic_cache: v }, 'cache')}
            />
            <Toggle
              icon={<Sparkles size={14} />}
              title="快模型关闭思考链"
              desc="抽取类任务默认关闭；需要更强推理时再打开。"
              checked={rt.fast_thinking ?? true}
              busy={busy === 'think'}
              onChange={(v) => patch({ fast_thinking: v }, 'think')}
            />
          </div>
        </section>

        <section className="card-pad">
          <SectionTitle extra={
            <button
              className="text-[10.5px] text-ink-400 hover:text-rose-500"
              onClick={async () => {
                await api.clearCache();
                cache.reload();
                push('info', '缓存已清空');
              }}
            >
              <Trash2 size={11} className="mr-0.5 inline" /> 清空
            </button>
          }>缓存命中</SectionTitle>
          {cache.data && (
            <>
              <div className="flex items-end gap-2">
                <span className="text-2xl font-semibold tabular-nums text-ink-900">{fmtPct(cache.data.hit_rate, 0)}</span>
                <span className="pb-1 text-[11px] text-ink-400">命中率</span>
                <button className="btn-ghost btn-sm ml-auto" onClick={() => cache.reload()}>
                  <RefreshCw size={11} /> 刷新
                </button>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
                {[['条目', cache.data.entries], ['命中', cache.data.hits], ['未命中', cache.data.misses]].map(([k, v]) => (
                  <div key={String(k)} className="rounded-lg bg-ink-50 py-1.5">
                    <p className="text-ink-400">{k}</p>
                    <p className="font-semibold text-ink-700">{v}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function Toggle({
  icon, title, desc, checked, busy, onChange,
}: {
  icon: React.ReactNode; title: string; desc: string; checked: boolean; busy: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 text-ink-400">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-[12.5px] font-medium text-ink-800">{title}</p>
        <p className="mt-0.5 text-[10.5px] leading-4 text-ink-400">{desc}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        disabled={busy}
        className={clsx(
          'mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition',
          checked ? 'bg-brand-600' : 'bg-ink-200',
        )}
        aria-pressed={checked}
      >
        <span className={clsx('block h-4 w-4 rounded-full bg-white shadow transition', checked && 'translate-x-4')} />
      </button>
    </div>
  );
}
