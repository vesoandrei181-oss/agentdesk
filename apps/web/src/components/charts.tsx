/**
 * 轻量 SVG 图表：不引第三方图表库，避免打包体积和 SSR 兼容问题。
 * 三个组件覆盖了看板需要的全部图形：趋势面积图、占比环图、横向条形。
 */
import { useId } from 'react';

export function AreaChart({
  data, height = 72, color = '#6366f1', labelKey = 'date', valueKey = 'runs',
}: {
  data: Record<string, unknown>[];
  height?: number;
  color?: string;
  labelKey?: string;
  valueKey?: string;
}) {
  const gid = useId().replace(/:/g, '');
  if (!data.length) return <div style={{ height }} className="rounded bg-ink-50" />;

  const values = data.map((d) => Number(d[valueKey] ?? 0));
  const max = Math.max(1, ...values);
  const w = 100;
  const step = data.length > 1 ? w / (data.length - 1) : w;
  const pts = values.map((v, i) => [i * step, height - (v / max) * (height - 6) - 3] as const);
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const area = `${line} L${w},${height} L0,${height} Z`;

  return (
    <div style={{ height }} className="w-full">
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="h-full w-full">
        <defs>
          <linearGradient id={`g${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.26" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#g${gid})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="1.4" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {pts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={values[i] ? 1.6 : 0} fill={color} vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-ink-400">
        <span>{String(data[0]?.[labelKey] ?? '').slice(5)}</span>
        <span>{String(data[data.length - 1]?.[labelKey] ?? '').slice(5)}</span>
      </div>
    </div>
  );
}

export function Donut({
  segments, size = 96, thickness = 10, center,
}: {
  segments: { value: number; color: string; name: string }[];
  size?: number;
  thickness?: number;
  center?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef0f4" strokeWidth={thickness} />
        {total > 0 &&
          segments.map((seg, i) => {
            const len = (seg.value / total) * c;
            const dash = `${Math.max(0, len - 2)} ${c - Math.max(0, len - 2)}`;
            const el = (
              <circle
                key={i}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth={thickness}
                strokeDasharray={dash}
                strokeDashoffset={-offset}
                strokeLinecap="round"
              />
            );
            offset += len;
            return el;
          })}
      </svg>
      {center && <span className="absolute text-sm font-semibold text-ink-800">{center}</span>}
    </div>
  );
}

export function BarRow({
  name, value, max, suffix, color = 'bg-brand-500',
}: { name: string; value: number; max: number; suffix?: string; color?: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-20 shrink-0 truncate text-ink-500">{name}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-14 shrink-0 text-right font-medium tabular-nums text-ink-700">
        {value}
        {suffix}
      </span>
    </div>
  );
}
