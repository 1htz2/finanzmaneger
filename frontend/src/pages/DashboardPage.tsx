import {
  AlertTriangle,
  Banknote,
  CalendarClock,
  CalendarDays,
  Info,
  Landmark,
  OctagonAlert,
  PiggyBank,
  Plus,
  ShieldCheck,
} from 'lucide-react'
import { Link } from 'react-router'

import { useActions } from '@/components/Actions'
import { BalanceChart, BudgetRing, PeriodBars, UsageBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, StatTile } from '@/components/common'
import { TransactionRow } from '@/components/TransactionRow'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { BUCKETS, bucketOf } from '@/lib/domain'
import { formatDate, formatPercent, formatShortDate, periodRange } from '@/lib/format'
import { useDashboard } from '@/lib/queries'
import type { BudgetWarning, Dashboard, PeriodSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard()
  const { recordSalary } = useActions()

  if (isLoading) return <LoadingState rows={4} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  const period = data.active_period
  if (!period) {
    return (
      <EmptyState
        className="mt-10"
        icon={<Banknote />}
        title="Noch kein Budgetzeitraum"
        text="Ein Budgetzeitraum beginnt mit deinem Gehaltseingang. Erfasse dein letztes Nettogehalt, dann teilt die App es automatisch in Sparen, Fixkosten und Freizeit auf."
        action={
          <Button size="lg" onClick={recordSalary}>
            <Banknote /> Gehalt erfassen
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <p className="text-sm text-muted-foreground">
          Budgetzeitraum {periodRange(period.started_at, null)}
          {period.expected_next_payday && ` · nächster Zahltag ${formatDate(period.expected_next_payday)}`}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Wie viel darf ich noch ausgeben?</h1>
      </div>

      {data.warnings.length > 0 && <Warnings warnings={data.warnings} />}

      <div className="grid gap-4 lg:grid-cols-5">
        <LeisureHero data={data} period={period} />
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2 lg:grid-cols-1">
          <BucketCard period={period} bucket="fixed" openCents={data.fixed_open_cents} />
          <BucketCard period={period} bucket="savings" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Nettogehalt"
          icon={<Banknote />}
          value={<Money cents={period.net_salary_cents} />}
          hint={`eingegangen ${formatDate(period.started_at)}`}
        />
        <StatTile
          label="Gesamtbudget"
          icon={<CalendarDays />}
          value={<Money cents={period.total_budget_cents} />}
          hint={period.extra_income_cents ? <>inkl. <Money cents={period.extra_income_cents} /> weiterer Einnahmen</> : '20 / 50 / 30'}
        />
        <StatTile
          label="Reserve"
          icon={<ShieldCheck />}
          value={<Money cents={data.reserve_balance_cents} />}
          hint="virtueller Puffer-Topf"
        />
        <StatTile
          label="Ersparnisse"
          icon={<Landmark />}
          value={<Money cents={data.savings.balance_cents} />}
          hint={<>davon <Money cents={data.savings.allocated_cents} /> in Sparzielen</>}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Letzte Buchungen</CardTitle>
            <CardAction>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/transaktionen">Alle</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="px-3">
            {data.recent_transactions.length === 0 ? (
              <EmptyState title="Noch keine Buchungen" text="Erfasse deine erste Ausgabe über das Plus." />
            ) : (
              data.recent_transactions.map((t) => <TransactionRow key={t.id} t={t} />)
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Kommende Fixkosten</CardTitle>
            <CardDescription>
              Noch offen in diesem Zeitraum: <Money cents={data.fixed_open_cents} />
            </CardDescription>
            <CardAction>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/fixkosten">Verwalten</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {data.upcoming_fixed_costs.length === 0 ? (
              <EmptyState icon={<CalendarClock />} title="Keine offenen Fixkosten" text="Lege regelmäßige Kosten unter „Fixkosten“ an." />
            ) : (
              <ul className="divide-y">
                {data.upcoming_fixed_costs.map((u) => (
                  <li key={`${u.recurring_expense_id}-${u.due_date}`} className="flex items-center gap-3 py-2.5 text-sm">
                    <span className="w-16 shrink-0 text-xs text-muted-foreground">{formatShortDate(u.due_date)}</span>
                    <span className="flex-1 truncate">{u.name}</span>
                    <Money cents={u.amount_cents} className="font-medium" />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sparziele</CardTitle>
            <CardAction>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/sparziele">Alle</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.goals.length === 0 ? (
              <EmptyState icon={<PiggyBank />} title="Noch keine Sparziele" action={<Button asChild variant="outline" size="sm"><Link to="/sparziele"><Plus /> Sparziel anlegen</Link></Button>} />
            ) : (
              data.goals.map((g) => (
                <div key={g.id} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{g.title}</span>
                    <span className="text-muted-foreground">
                      <Money cents={g.saved_cents} /> / <Money cents={g.target_cents} />
                    </span>
                  </div>
                  <UsageBar bucket="savings" usedBp={g.progress_bp} />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Entwicklung der Reserve</CardTitle>
            <CardDescription>
              Aktuell <Money cents={data.reserve_balance_cents} />
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.reserve_history.length < 2 ? (
              <EmptyState icon={<ShieldCheck />} title="Noch wenig Verlauf" text="Nicht verbrauchtes Budget fließt beim Periodenwechsel automatisch in die Reserve." />
            ) : (
              <BalanceChart points={data.reserve_history} name="Reserve" height={200} />
            )}
          </CardContent>
        </Card>
      </div>

      {data.period_comparison.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Vergleich der Budgetperioden</CardTitle>
            <CardDescription>Ausgaben und Sparanteil je Gehaltsperiode</CardDescription>
            <CardAction>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/statistiken">Details</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <PeriodBars
              data={data.period_comparison.map((p) => ({
                label: formatShortDate(p.started_at),
                fixed: bucketOf(p, 'fixed').spent_cents,
                leisure: bucketOf(p, 'leisure').spent_cents,
                savings: bucketOf(p, 'savings').budget_cents,
              }))}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function LeisureHero({ data, period }: { data: Dashboard; period: PeriodSummary }) {
  const leisure = bucketOf(period, 'leisure')
  const pace = data.leisure_pace
  const over = leisure.available_cents < 0
  return (
    <Card className="lg:col-span-3">
      <CardContent className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <BudgetRing bucket="leisure" usedBp={leisure.used_bp} size={148}>
          <span className="text-xs text-muted-foreground">verbraucht</span>
          <span className="text-lg font-semibold tabular">{formatPercent(leisure.used_bp, 1)}</span>
        </BudgetRing>
        <div className="flex-1 space-y-3">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="size-2.5 rounded-full" style={{ background: BUCKETS.leisure.color }} />
              Freizeit · noch verfügbar
            </div>
            <Money
              cents={leisure.available_cents}
              className={cn('block text-4xl font-semibold tracking-tight sm:text-5xl', over && 'text-critical')}
            />
            <p className="mt-1 text-sm text-muted-foreground">
              <Money cents={leisure.spent_cents} /> von <Money cents={leisure.budget_cents} /> ausgegeben
            </p>
          </div>
          {pace ? (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-muted/60 p-3">
                <div className="text-xs text-muted-foreground">pro Tag</div>
                <Money cents={pace.per_day_cents} className="text-lg font-semibold" />
              </div>
              <div className="rounded-lg bg-muted/60 p-3">
                <div className="text-xs text-muted-foreground">pro 7 Tage</div>
                <Money cents={pace.per_week_cents} className="text-lg font-semibold" />
              </div>
              <p className="col-span-2 text-xs text-muted-foreground">
                Planungshilfe für {pace.days_left} Tage bis zum erwarteten Zahltag am {formatDate(pace.expected_next_payday)}.
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              {data.pace_unavailable_reason === 'payday_passed'
                ? 'Der erwartete Zahltag ist erreicht. Erfasse dein Gehalt, sobald es eingegangen ist.'
                : <>Kein erwarteter Zahltag hinterlegt, daher keine Tages- oder Wochenempfehlung. <Link className="underline" to="/budget">Zahltag eintragen</Link></>}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function BucketCard({
  period,
  bucket,
  openCents,
}: {
  period: PeriodSummary
  bucket: 'fixed' | 'savings'
  openCents?: number
}) {
  const s = bucketOf(period, bucket)
  const meta = BUCKETS[bucket]
  const Icon = meta.icon
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <span className="flex size-7 items-center justify-center rounded-md text-white" style={{ background: meta.color }}>
            <Icon className="size-4" />
          </span>
          {meta.label}
        </CardTitle>
        <CardAction className="text-sm text-muted-foreground">
          <Money cents={s.budget_cents} />
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-2">
        {bucket === 'savings' ? (
          <>
            <UsageBar bucket="savings" usedBp={10_000} />
            <p className="text-sm">
              <Money cents={s.budget_cents} className="font-semibold" /> zurückgelegt
              <span className="text-muted-foreground"> · {formatPercent(period.planned_savings_rate_bp, 0)} des Gehalts</span>
            </p>
          </>
        ) : (
          <>
            <UsageBar bucket={bucket} usedBp={s.used_bp} />
            <div className="flex justify-between text-sm">
              <span>
                <Money cents={s.available_cents} className="font-semibold" /> verfügbar
              </span>
              <span className="text-muted-foreground">{formatPercent(s.used_bp)}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              <Money cents={s.spent_cents} /> verwendet
              {openCents !== undefined && openCents > 0 && (
                <>
                  {' '}· <Money cents={openCents} /> noch offen geplant
                </>
              )}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

const SEVERITY = {
  critical: { icon: OctagonAlert, cls: 'border-critical/40 bg-critical/5', iconCls: 'text-critical', label: 'Kritisch' },
  warning: { icon: AlertTriangle, cls: 'border-warn/40 bg-warn/5', iconCls: 'text-warn', label: 'Warnung' },
  info: { icon: Info, cls: 'border-border bg-muted/40', iconCls: 'text-muted-foreground', label: 'Hinweis' },
} as const

function Warnings({ warnings }: { warnings: BudgetWarning[] }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2" aria-label="Budgetwarnungen">
      {warnings.map((w, i) => {
        const s = SEVERITY[w.severity]
        const Icon = s.icon
        return (
          <li key={`${w.code}-${i}`} className={cn('flex gap-3 rounded-xl border p-3', s.cls)}>
            <Icon className={cn('mt-0.5 size-4 shrink-0', s.iconCls)} aria-label={s.label} />
            <div className="text-sm">
              <div className="font-medium">{w.title}</div>
              <div className="text-muted-foreground">{w.message}</div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
