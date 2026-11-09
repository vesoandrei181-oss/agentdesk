import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Cpu, Database, Timer, Zap } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/hooks';
import { fmtCost, fmtDateTime, fmtLatency, fmtNum, fmtPct } from '@/lib/format';
import { AreaChart } from '@/components/charts';
import { ErrorBox, Loading, SectionTitle } from '@/components/ui';

export function InsightsPage() {
  const overview = useAsync(() => api.overview(), []);
  const runs = useAsync(() => api.runs(), []);

  if (overview.loading) return <Loading label="汇总运行指标" />;
  if (overview.error) return <ErrorBox message={overview.error} onRetry={overview.reload} />;
  const o = overview.data!;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: '运行次数', value: o.kpi.runs, icon: Activity, unit: '次' },
          { label: 'Token 消耗', value: fmtNum(o.kpi.tokens), icon: Cpu, unit: '' },
          { label: '累计成本', value: fmtCost(o.kpi.cost_usd), icon: Database, unit: '' },
          { label: '缓存命中', value: o.kpi.cache_hits, icon: Zap, unit: '次' },
        ].map((c) => (
          <div key={c.label} className="card-pad">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-500">{c.label}</span>
              <c.icon size={14} className="text-ink-300" />
            </div>
            <p className="mt-1.5 text-xl font-semibold tabular-nums text-ink-900">
              {c.value}
              <span className="ml-0.5 text-[11px] font-normal text-ink-400">{c.unit}</span>
            </p>
          </div>
        ))}
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <section className="card-pad">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">近 14 天</span>}>调用趋势</SectionTitle>
          <AreaChart data={o.timeline as unknown as Record<string, unknown>[]} valueKey="runs" height={120} />
        </section>

        <section className="card-pad">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">当前档位 {o.runtime.tier}</span>}>路由分配</SectionTitle>
          <table className="w-full text-[11.5px]">
            <thead>
              <tr className="text-ink-400">
                <th className="pb-1 text-left font-normal">Agent</th>
                <th className="pb-1 text-right font-normal">模型</th>
                <th className="pb-1 text-right font-normal">温度</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(o.runtime.table).map(([agent, row]) => (
                <tr key={agent} className="border-t border-ink-100">
                  <td className="py-1 text-ink-600">{agent}</td>
                  <td className="py-1 text-right">
                    <span
                      className={clsx(
                        'rounded px-1.5 py-0.5 text-[10px]',
                        row.model.includes('pro') ? 'bg-brand-50 text-brand-600' : 'bg-ink-100 text-ink-500',
                      )}
                    >
                      {row.model}
                    </span>
                  </td>
                  <td className="py-1 text-right tabular-nums text-ink-500">{row.temperature}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <section className="card">
        <div className="px-5 pt-4">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">按调用次数统计</span>}>Agent 性能</SectionTitle>
        </div>
        <table className="table-base">
          <thead>
            <tr>
              <th>Agent</th>
              <th className="w-20 text-right">调用</th>
              <th className="w-24 text-right">Token</th>
              <th className="w-24 text-right">平均耗时</th>
              <th className="w-20 text-right">缓存</th>
              <th className="w-20 text-right">失败</th>
              <th className="w-32">耗时占比</th>
            </tr>
          </thead>
          <tbody>
            {o.agents.map((a) => {
              const maxLatency = Math.max(1, ...o.agents.map((x) => x.avg_latency));
              return (
                <tr key={a.agent}>
                  <td>
                    <span className="text-[13px] font-medium text-ink-800">{a.label}</span>
                    <span className="ml-1.5 font-mono text-[10px] text-ink-400">{a.agent}</span>
                  </td>
                  <td className="text-right tabular-nums text-[12.5px]">{a.calls}</td>
                  <td className="text-right tabular-nums text-[12.5px]">{fmtNum(a.tokens)}</td>
                  <td className="text-right tabular-nums text-[12.5px]">{fmtLatency(a.avg_latency)}</td>
                  <td className="text-right text-[12.5px] text-emerald-600">{a.cache}</td>
                  <td className={clsx('text-right text-[12.5px]', a.errors ? 'text-rose-600' : 'text-ink-400')}>{a.errors}</td>
                  <td>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                      <div className="h-full rounded-full bg-brand-400" style={{ width: `${(a.avg_latency / maxLatency) * 100}%` }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="card">
        <div className="flex items-center justify-between px-5 pt-4">
          <SectionTitle extra={<span className="text-[11px] text-ink-400">点开看每一步的输入输出</span>}>运行记录</SectionTitle>
          <div className="mb-3 flex items-center gap-3 text-[10.5px] text-ink-400">
            <span className="inline-flex items-center gap-1">
              <Timer size={11} /> 总耗时
            </span>
            <span>缓存命中率 {fmtPct(o.cache.hit_rate, 0)}</span>
          </div>
        </div>
        {runs.loading ? (
          <Loading label="" />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>任务</th>
                <th className="w-24">类型</th>
                <th className="w-24">模型</th>
                <th className="w-28 text-right">Token</th>
                <th className="w-24 text-right">耗时</th>
                <th className="w-20 text-right">成本</th>
                <th className="w-32">时间</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {(runs.data?.items || []).map((r) => (
                <tr key={r.id} className="hover:bg-ink-50/60">
                  <td className="text-[12.5px] text-ink-800">{r.title}</td>
                  <td className="text-[11.5px] text-ink-500">{r.kind}</td>
                  <td className="font-mono text-[10.5px] text-ink-500">{r.model}</td>
                  <td className="text-right tabular-nums text-[12px]">{r.tokens_in + r.tokens_out}</td>
                  <td className="text-right tabular-nums text-[12px]">{fmtLatency(r.latency_ms)}</td>
                  <td className="text-right tabular-nums text-[12px]">{fmtCost(r.cost_usd)}</td>
                  <td className="text-[11px] text-ink-400">{fmtDateTime(r.created_at)}</td>
                  <td>
                    <Link to={`/runs/${r.id}`} className="text-ink-300 hover:text-brand-600">
                      <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
