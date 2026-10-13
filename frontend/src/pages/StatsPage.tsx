import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { BalanceChart, GroupedBars, PeriodBars } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile } from '@/components/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { BUCKETS, bucketOf } from '@/lib/domain'
import { formatPercent, formatShortDate, periodRange } from '@/lib/format'
import { useCategoryBreakdown, useStats } from '@/lib/queries'

export function StatsPage() {
  const { data, isLoading, error, refetch } = useStats()
  const [periodId, setPeriodId] = useState('all')
  const [bucket, setBucket] = useState('all')
  const breakdown = useCategoryBreakdown({
    period_id: periodId === 'all' ? undefined : Number(periodId),
    bucket: bucket === 'all' ? undefined : bucket,
  })

  if (isLoading) return <LoadingState rows={4} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />
  if (data.periods.length === 0) {
    return (
      <>
        <PageHeader title="Statistiken" />
        <EmptyState title="Noch keine Daten" text="Statistiken entstehen, sobald du Gehälter und Ausgaben erfasst." />
      </>
    )
  }

  const a = data.averages
  const label = (iso: string) => formatShortDate(iso)
  const incomeData = data.periods.map((p) => ({ label: label(p.started_at), income: p.net_salary_cents + p.extra_income_cents }))
  const rateData = data.periods
    .filter((p) => p.actual_savings_rate_bp !== null)
    .map((p) => ({ label: label(p.started_at), rate: (p.actual_savings_rate_bp ?? 0) / 100 }))

  return (
    <div className="space-y-6">
      <PageHeader title="Statistiken" description="Alle Vergleiche beziehen sich auf deine tatsächlichen Gehaltsperioden." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Ø Einnahmen" value={a.avg_income_cents === null ? '–' : <Money cents={a.avg_income_cents} />} hint={`${a.closed_periods} abgeschlossene Perioden`} />
        <StatTile label="Ø Fixkosten" value={a.avg_fixed_spent_cents === null ? '–' : <Money cents={a.avg_fixed_spent_cents} />} />
        <StatTile label="Ø Freizeit" value={a.avg_leisure_spent_cents === null ? '–' : <Money cents={a.avg_leisure_spent_cents} />} />
        <StatTile
          label="Tatsächliche Sparquote"
          value={formatPercent(a.avg_actual_savings_rate_bp, 1)}
          hint={`geplant ${formatPercent(a.planned_savings_rate_bp, 0)} · inkl. nicht ausgegebenem Budget`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ausgaben je Budgetperiode</CardTitle>
          <CardDescription>Fixkosten und Freizeit tatsächlich ausgegeben, dazu der geplante Sparanteil.</CardDescription>
        </CardHeader>
        <CardContent>
          <PeriodBars
            data={data.periods.map((p) => ({
              label: label(p.started_at),
              fixed: bucketOf(p, 'fixed').spent_cents,
              leisure: bucketOf(p, 'leisure').spent_cents,
              savings: bucketOf(p, 'savings').budget_cents,
            }))}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Entwicklung der Einnahmen</CardTitle>
            <CardDescription>Nettogehalt plus weitere Einnahmen der Periode</CardDescription>
          </CardHeader>
          <CardContent>
            <GroupedBars data={incomeData} xKey="label" series={[{ key: 'income', name: 'Einnahmen', color: 'var(--muted-foreground)' }]} height={220} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sparquote: tatsächlich vs. geplant</CardTitle>
            <CardDescription>
              Tatsächlich = (Einnahmen − Ausgaben) ÷ Einnahmen je abgeschlossener Periode. Linie = geplante {formatPercent(a.planned_savings_rate_bp, 0)}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {rateData.length === 0 ? (
              <EmptyState title="Noch keine abgeschlossene Periode" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={rateData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={(v: number) => `${v} %`} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} width={48} />
                  <Tooltip
                    formatter={(v) => [`${Number(v).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`, 'Tatsächliche Sparquote']}
                    contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    cursor={{ fill: 'var(--muted)', opacity: 0.5 }}
                  />
                  <ReferenceLine y={a.planned_savings_rate_bp / 100} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
                  <Bar dataKey="rate" name="Tatsächliche Sparquote" fill="var(--savings)" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Entwicklung der Reserve</CardTitle>
          </CardHeader>
          <CardContent>
            {data.reserve_history.length < 2 ? (
              <EmptyState title="Noch wenig Verlauf" />
            ) : (
              <BalanceChart points={data.reserve_history} name="Reserve" height={220} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Entwicklung der Ersparnisse</CardTitle>
          </CardHeader>
          <CardContent>
            {data.savings_history.length < 2 ? (
              <EmptyState title="Noch wenig Verlauf" />
            ) : (
              <BalanceChart points={data.savings_history} name="Ersparnisse" color="var(--savings)" height={220} />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ausgaben nach Kategorie</CardTitle>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <Select value={periodId} onValueChange={setPeriodId}>
              <SelectTrigger className="w-full sm:w-64" aria-label="Zeitraum">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Perioden</SelectItem>
                {[...data.periods].reverse().map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {periodRange(p.started_at, p.ended_at)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={bucket} onValueChange={setBucket}>
              <SelectTrigger className="w-full sm:w-44" aria-label="Topf">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Töpfe</SelectItem>
                <SelectItem value="leisure">Freizeit</SelectItem>
                <SelectItem value="fixed">Fixkosten</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {!breakdown.data || breakdown.data.items.length === 0 ? (
            <EmptyState title="Keine Ausgaben im gewählten Zeitraum" />
          ) : (
            <ul className="space-y-3">
              {breakdown.data.items.map((i) => {
                const kind = i.category?.kind
                const color = kind === 'fixed' ? BUCKETS.fixed.color : BUCKETS.leisure.color
                return (
                  <li key={i.category?.id ?? 'none'} className="space-y-1">
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="flex items-center gap-2">
                        <span className="size-2 rounded-full" style={{ background: i.category?.color ?? color }} />
                        {i.category?.name ?? 'Ohne Kategorie'}
                        <span className="text-xs text-muted-foreground">{i.count}×</span>
                      </span>
                      <span>
                        <Money cents={i.total_cents} className="font-medium" />{' '}
                        <span className="text-xs text-muted-foreground">{formatPercent(i.share_bp, 1)}</span>
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full" style={{ width: `${(i.share_bp ?? 0) / 100}%`, background: color }} />
                    </div>
                  </li>
                )
              })}
              <li className="flex justify-between border-t pt-2 text-sm font-medium">
                Summe <Money cents={breakdown.data.total_cents} />
              </li>
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
