import type { ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import { BUCKETS } from '@/lib/domain'
import { formatDate, formatEur, formatEurCompact, formatShortDate } from '@/lib/format'
import type { BalancePoint, Bucket } from '@/lib/types'

const AXIS = { fontSize: 12, fill: 'var(--muted-foreground)' }

/** Ring showing how much of a bucket is used. Overspending turns the ring critical. */
export function BudgetRing({
  bucket,
  usedBp,
  size = 112,
  children,
}: {
  bucket: Bucket
  usedBp: number | null
  size?: number
  children?: ReactNode
}) {
  const stroke = 10
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const ratio = Math.min(Math.max((usedBp ?? 0) / 10_000, 0), 1)
  const over = (usedBp ?? 0) > 10_000
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={over ? 'var(--critical)' : BUCKETS[bucket].color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * ratio} ${c}`}
          className="transition-[stroke-dasharray] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>
    </div>
  )
}

export function UsageBar({ bucket, usedBp }: { bucket: Bucket; usedBp: number | null }) {
  const pct = Math.min(Math.max((usedBp ?? 0) / 100, 0), 100)
  const over = (usedBp ?? 0) > 10_000
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{ width: `${pct}%`, background: over ? 'var(--critical)' : BUCKETS[bucket].color }}
      />
    </div>
  )
}

interface TipProps {
  active?: boolean
  payload?: readonly { dataKey?: unknown; name?: unknown; value?: unknown; color?: string }[]
  label?: unknown
  formatLabel?: (l: unknown) => string
}

function ChartTooltip({ active, payload, label, formatLabel }: TipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium">{formatLabel ? formatLabel(label) : String(label)}</div>
      {payload.map((p) => (
        <div key={String(p.dataKey)} className="flex items-center gap-2">
          <span className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{String(p.name)}</span>
          <span className="ml-auto pl-3 font-medium tabular">{formatEur(Number(p.value))}</span>
        </div>
      ))}
    </div>
  )
}

/** Balance over time as a step area (balances change in jumps, not continuously). */
export function BalanceChart({
  points,
  color = 'var(--foreground)',
  name,
  height = 220,
}: {
  points: BalancePoint[]
  color?: string
  name: string
  height?: number
}) {
  const data = points.map((p) => ({ at: p.at, value: p.balance_cents }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey="at" tickFormatter={(v: string) => formatShortDate(v)} tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tickFormatter={(v: number) => formatEurCompact(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} />
        <Tooltip
          content={(props: TooltipContentProps<ValueType, NameType>) => (
            <ChartTooltip active={props.active} payload={props.payload} label={props.label} formatLabel={(l) => formatDate(String(l))} />
          )}
          cursor={{ stroke: 'var(--border)' }}
        />
        <Area
          type="stepAfter"
          dataKey="value"
          name={name}
          stroke={color}
          strokeWidth={2}
          fill={color}
          fillOpacity={0.1}
          activeDot={{ r: 4, stroke: 'var(--card)', strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export interface PeriodBarDatum {
  label: string
  fixed: number
  leisure: number
  savings: number
}

/** Grouped bars per budget period. Three series, legend always shown. */
export function PeriodBars({ data, height = 260 }: { data: PeriodBarDatum[]; height?: number }) {
  const series: Bucket[] = ['fixed', 'leisure', 'savings']
  const names: Record<Bucket, string> = {
    fixed: 'Fixkosten ausgegeben',
    leisure: 'Freizeit ausgegeben',
    savings: 'Gespart (geplant)',
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="24%">
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={(v: number) => formatEurCompact(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} />
        <Tooltip content={(props: TooltipContentProps<ValueType, NameType>) => (
            <ChartTooltip active={props.active} payload={props.payload} label={props.label} />
          )} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
        {series.map((b) => (
          <Bar
            key={b}
            dataKey={b}
            name={names[b]}
            fill={BUCKETS[b].color}
            maxBarSize={24}
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

export interface SeriesDef {
  key: string
  name: string
  color: string
}

/** Generic grouped bars with an explicit series list (one y-axis, legend for >= 2 series). */
export function GroupedBars({
  data,
  series,
  xKey,
  height = 260,
}: {
  data: Record<string, string | number>[]
  series: SeriesDef[]
  xKey: string
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="24%">
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={(v: number) => formatEurCompact(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} />
        <Tooltip content={(props: TooltipContentProps<ValueType, NameType>) => (
            <ChartTooltip active={props.active} payload={props.payload} label={props.label} />
          )} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />
        {series.length > 1 && <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
