import {
  Archive,
  ArrowRightLeft,
  HandCoins,
  LineChart,
  Pencil,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { BalanceChart } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ACCOUNT_ENTRY_LABELS, ACCOUNT_KINDS, accountColor } from '@/lib/accounts'
import { api, newIdempotencyKey } from '@/lib/api'
import { bucketOf } from '@/lib/domain'
import { centsToInput, formatDate, formatDateTime, formatEur, formatPercent, parseEuroInput } from '@/lib/format'
import { useActivePeriod, useFinanceMutation, useWealth } from '@/lib/queries'
import type { Account, AccountKind, Wealth } from '@/lib/types'
import { cn } from '@/lib/utils'

type DialogState =
  | { type: 'account'; account: Account | null; kind?: AccountKind }
  | { type: 'assign'; account: Account | null }
  | { type: 'move'; from: Account | null }
  | { type: 'valuation'; account: Account }
  | { type: 'split' }
  | null

const QUICK_START: { kind: AccountKind; name: string }[] = [
  { kind: 'savings_account', name: 'Tagesgeld' },
  { kind: 'brokerage', name: 'ETF-Depot' },
  { kind: 'cash', name: 'Bargeld' },
]

export function WealthPage() {
  const { data, isLoading, error, refetch } = useWealth()
  const [dialog, setDialogState] = useState<DialogState>(null)
  const [session, setSession] = useState(0)

  if (isLoading) return <LoadingState rows={4} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  const open = (d: DialogState) => {
    setSession((n) => n + 1)
    setDialogState(d)
  }
  const close = () => setDialogState(null)
  const active = data.accounts.filter((a) => !a.archived)
  const archived = data.accounts.filter((a) => a.archived)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vermögen"
        description="Wo dein Geld liegt: Ersparnisse und Reserve je Bank, Depot und Konto."
        actions={
          <>
            {active.length > 1 && (
              <Button variant="outline" onClick={() => open({ type: 'move', from: null })}>
                <ArrowRightLeft /> Verschieben
              </Button>
            )}
            <Button onClick={() => open({ type: 'account', account: null })}>
              <Plus /> Anlageort
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-5">
        <NetWorthHero data={data} className="lg:col-span-3" />
        <InstitutionsCard data={data} className="lg:col-span-2" />
      </div>

      {active.length === 0 ? (
        <EmptyState
          icon={<Wallet />}
          title="Wo liegt dein Geld?"
          text="Lege an, wo du sparst und investierst: Tagesgeld, ETF-Depot, Bargeld oder ein Konto bei einer anderen Bank. Danach verteilt die App deine Sparrate automatisch."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_START.map((q) => {
                const Icon = ACCOUNT_KINDS[q.kind].icon
                return (
                  <Button key={q.kind} variant="outline" onClick={() => open({ type: 'account', account: null, kind: q.kind })}>
                    <Icon /> {q.name}
                  </Button>
                )
              })}
            </div>
          }
        />
      ) : (
        <>
          {data.unassigned_cents > 0 && (
            <div className="flex flex-col gap-3 rounded-xl border border-dashed bg-card p-4 sm:flex-row sm:items-center">
              <div className="flex-1 text-sm">
                <span className="font-semibold">
                  <Money cents={data.unassigned_cents} /> ohne Anlageort
                </span>
                <span className="block text-muted-foreground">Ersparnisse, für die noch nicht feststeht, wo sie liegen.</span>
              </div>
              <Button variant="outline" onClick={() => open({ type: 'assign', account: null })}>
                Zuordnen
              </Button>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {active.map((a) => (
              <AccountCard
                key={a.id}
                account={a}
                total={data.total_assets_cents}
                onEdit={() => open({ type: 'account', account: a })}
                onAssign={() => open({ type: 'assign', account: a })}
                onMove={active.length > 1 ? () => open({ type: 'move', from: a }) : undefined}
                onValue={() => open({ type: 'valuation', account: a })}
              />
            ))}
          </div>

          <SplitCard data={data} onEdit={() => open({ type: 'split' })} />
        </>
      )}

      {data.history.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Entwicklung</CardTitle>
            <CardDescription>Ersparnisse und Reserve nach Buchungen. Kursgewinne sind nicht enthalten.</CardDescription>
          </CardHeader>
          <CardContent>
            <BalanceChart points={data.history} name="Ersparnisse und Reserve" color="var(--savings)" />
          </CardContent>
        </Card>
      )}

      {data.entries.length > 0 && <EntriesCard data={data} />}

      {archived.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Archiviert</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {archived.map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-2">
                  <span className="size-2.5 shrink-0 rounded-full opacity-50" style={{ background: accountColor(a) }} />
                  <span className="flex-1 text-muted-foreground">{a.name}</span>
                  <Button size="icon-sm" variant="ghost" aria-label={`${a.name} bearbeiten`} onClick={() => open({ type: 'account', account: a })}>
                    <Pencil />
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <AccountDialog key={`account-${session}`} state={dialog?.type === 'account' ? dialog : null} onClose={close} />
      <AssignDialog key={`assign-${session}`} state={dialog?.type === 'assign' ? dialog : null} data={data} onClose={close} />
      <MoveDialog key={`move-${session}`} state={dialog?.type === 'move' ? dialog : null} accounts={active} onClose={close} />
      <ValuationDialog key={`value-${session}`} account={dialog?.type === 'valuation' ? dialog.account : null} onClose={close} />
      <SplitDialog key={`split-${session}`} open={dialog?.type === 'split'} accounts={active} onClose={close} />
    </div>
  )
}

// ---------------------------------------------------------------- overview

interface Segment {
  key: string
  label: string
  cents: number
  color: string
  muted?: boolean
}

function segmentsOf(data: Wealth): Segment[] {
  const segments: Segment[] = data.accounts
    .filter((a) => !a.archived && a.total_cents > 0)
    .map((a) => ({ key: `a${a.id}`, label: a.name, cents: a.total_cents, color: accountColor(a) }))
  if (data.reserve_account_id === null && data.reserve_cents > 0) {
    segments.push({ key: 'reserve', label: 'Reserve ohne Ort', cents: data.reserve_cents, color: 'var(--muted-foreground)', muted: true })
  }
  if (data.unassigned_cents > 0) {
    segments.push({ key: 'free', label: 'Ersparnisse ohne Ort', cents: data.unassigned_cents, color: 'var(--chart-1)', muted: true })
  }
  return segments
}

function NetWorthHero({ data, className }: { data: Wealth; className?: string }) {
  const segments = segmentsOf(data)
  const total = segments.reduce((s, x) => s + x.cents, 0)
  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 -right-24 size-64 rounded-full opacity-[0.12] blur-3xl"
        style={{ background: 'var(--savings)' }}
      />
      <CardContent className="relative space-y-5">
        <div>
          <div className="text-sm text-muted-foreground">Nettovermögen</div>
          <Money cents={data.net_worth_cents} className={cn('block text-4xl font-semibold tracking-tight sm:text-5xl', data.net_worth_cents < 0 && 'text-critical')} />
          {data.gains_cents !== 0 && (
            <GainLine cents={data.gains_cents} className="mt-1 text-sm" suffix="Kursentwicklung laut deinen Depotwerten" />
          )}
        </div>

        {total > 0 && (
          <div className="space-y-3">
            <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full" role="img" aria-label="Verteilung deines Vermögens">
              {segments.map((s) => (
                <div
                  key={s.key}
                  title={`${s.label}: ${formatEur(s.cents)}`}
                  className={cn('h-full min-w-1 transition-[flex-grow] duration-700 first:rounded-l-full last:rounded-r-full', s.muted && 'opacity-60')}
                  style={{ flexGrow: s.cents, flexBasis: 0, background: s.color }}
                />
              ))}
            </div>
            <ul className="grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm min-[400px]:grid-cols-2">
              {segments.map((s) => (
                <li key={s.key} className="flex min-w-0 items-center gap-2">
                  <span className={cn('size-2.5 shrink-0 rounded-full', s.muted && 'opacity-60')} style={{ background: s.color }} />
                  <span className="min-w-0 flex-1 truncate">{s.label}</span>
                  <span className="text-muted-foreground tabular">{formatPercent(Math.round((s.cents * 10_000) / total), 0)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <dl className="grid grid-cols-3 gap-2 text-xs">
          <Figure label="Ersparnisse" cents={data.savings_balance_cents + data.gains_cents} />
          <Figure label="Reserve" cents={data.reserve_cents} icon={<ShieldCheck className="size-3" />} />
          <Figure
            label="Schulden"
            cents={-data.debt_cents}
            icon={<HandCoins className="size-3" />}
            to={data.debt_cents > 0 ? '/schulden' : undefined}
          />
        </dl>
      </CardContent>
    </Card>
  )
}

function Figure({ label, cents, icon, to }: { label: string; cents: number; icon?: ReactNode; to?: string }) {
  const body = (
    <>
      <dt className="flex items-center gap-1 text-muted-foreground">
        {icon} {label}
      </dt>
      <dd className="mt-0.5 text-sm font-semibold sm:text-base">
        <Money cents={cents} />
      </dd>
    </>
  )
  const cls = 'rounded-lg bg-muted/60 p-2.5 transition-colors'
  return to ? (
    <Link to={to} className={cn(cls, 'block hover:bg-muted')}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  )
}

function GainLine({ cents, bp, className, suffix }: { cents: number; bp?: number | null; className?: string; suffix?: string }) {
  const up = cents >= 0
  const Icon = up ? TrendingUp : TrendingDown
  return (
    <p className={cn('flex flex-wrap items-center gap-x-1.5', className)}>
      <span className={cn('inline-flex items-center gap-1 font-medium', up ? 'text-good' : 'text-critical')}>
        <Icon className="size-3.5" />
        <Money cents={cents} signed />
        {bp !== undefined && bp !== null && <span>({formatPercent(bp, 1)})</span>}
      </span>
      {suffix && <span className="text-muted-foreground">{suffix}</span>}
    </p>
  )
}

function InstitutionsCard({ data, className }: { data: Wealth; className?: string }) {
  const max = Math.max(...data.institutions.map((i) => i.total_cents), 1)
  const byId = new Map(data.accounts.map((a) => [a.id, a]))
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Nach Bank</CardTitle>
        <CardDescription>Wie viel bei welchem Anbieter liegt.</CardDescription>
      </CardHeader>
      <CardContent>
        {data.institutions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sobald du Anlageorte mit Bank anlegst, siehst du hier die Summen je Anbieter.</p>
        ) : (
          <ul className="space-y-4">
            {data.institutions.map((inst) => (
              <li key={inst.label} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="truncate font-medium">{inst.label}</span>
                  <Money cents={inst.total_cents} className="font-semibold" />
                </div>
                <div className="flex h-2 gap-0.5 overflow-hidden rounded-full bg-muted" style={{ width: `${Math.max((inst.total_cents / max) * 100, 2)}%` }}>
                  {inst.account_ids.map((id) => {
                    const a = byId.get(id)
                    if (!a || a.total_cents <= 0) return null
                    return (
                      <div
                        key={id}
                        title={`${a.name}: ${formatEur(a.total_cents)}`}
                        className="h-full first:rounded-l-full last:rounded-r-full"
                        style={{ flexGrow: a.total_cents, flexBasis: 0, background: accountColor(a) }}
                      />
                    )
                  })}
                </div>
                <div className="text-xs text-muted-foreground">
                  {inst.account_ids.map((id) => byId.get(id)?.name).filter(Boolean).join(' · ')}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function AccountCard({
  account: a,
  total,
  onEdit,
  onAssign,
  onMove,
  onValue,
}: {
  account: Account
  total: number
  onEdit: () => void
  onAssign: () => void
  onMove?: () => void
  onValue: () => void
}) {
  const kind = ACCOUNT_KINDS[a.kind]
  const Icon = kind.icon
  const color = accountColor(a)
  return (
    <Card className="relative gap-4 overflow-hidden">
      <div aria-hidden className="absolute inset-x-0 top-0 h-1" style={{ background: color }} />
      <CardHeader>
        <div className="flex min-w-0 items-center gap-3">
          <span
            className="grid size-10 shrink-0 place-items-center rounded-xl"
            style={{ background: `color-mix(in oklab, ${color} 16%, transparent)`, color }}
          >
            <Icon className="size-5" />
          </span>
          <div className="min-w-0">
            <CardTitle className="truncate">{a.name}</CardTitle>
            <CardDescription className="truncate">
              {[a.institution, kind.label].filter(Boolean).join(' · ')}
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Button variant="ghost" size="icon-sm" aria-label={`${a.name} bearbeiten`} onClick={onEdit}>
            <Pencil />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Money cents={a.total_cents} className="block text-3xl font-semibold tracking-tight" />
          <div className="text-xs text-muted-foreground">
            {total > 0 ? `${formatPercent(Math.round((a.total_cents * 10_000) / total), 0)} deines Vermögens` : ' '}
          </div>
        </div>
        {kind.investment && a.last_valued_at && (
          <div className="rounded-lg bg-muted/60 p-2.5 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Eingezahlt</span>
              <Money cents={a.booked_cents} />
            </div>
            <GainLine cents={a.gain_cents} bp={a.gain_bp} className="mt-1 justify-between" />
            <div className="mt-1 text-muted-foreground">Wert vom {formatDate(a.last_valued_at)}</div>
          </div>
        )}
        {a.holds_reserve && a.reserve_cents > 0 && (
          <p className="text-xs text-muted-foreground">
            davon <Money cents={a.reserve_cents} /> Reserve, <Money cents={a.value_cents} /> Ersparnisse
          </p>
        )}
        <div className="flex flex-wrap gap-1.5">
          {a.savings_share_bp > 0 && (
            <Badge variant="secondary">
              <SlidersHorizontal /> {formatPercent(a.savings_share_bp, 0)} der Sparrate
            </Badge>
          )}
          {a.holds_reserve && (
            <Badge variant="secondary">
              <ShieldCheck /> Reserve liegt hier
            </Badge>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" size="sm" onClick={onAssign}>
            Zuordnen
          </Button>
          {kind.investment ? (
            <Button variant="outline" size="sm" onClick={onValue}>
              <LineChart /> Wert
            </Button>
          ) : onMove ? (
            <Button variant="outline" size="sm" onClick={onMove}>
              <ArrowRightLeft /> Verschieben
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

function SplitCard({ data, onEdit }: { data: Wealth; onEdit: () => void }) {
  const period = useActivePeriod()
  const rate = period.data ? bucketOf(period.data, 'savings').budget_cents : null
  const shares = data.accounts.filter((a) => !a.archived && a.savings_share_bp > 0)
  const rest = 10_000 - data.shares_total_bp
  return (
    <Card>
      <CardHeader>
        <CardTitle>Aufteilung der Sparrate</CardTitle>
        <CardDescription>
          Bei jedem Gehalt wird dein Sparanteil automatisch so verteilt.
          {rate ? (
            <>
              {' '}
              Aktuell <Money cents={rate} /> pro Periode.
            </>
          ) : null}
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={onEdit}>
            <SlidersHorizontal /> Anpassen
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-muted" role="img" aria-label="Aufteilung der Sparrate">
          {shares.map((a) => (
            <div key={a.id} className="h-full first:rounded-l-full" style={{ width: `${a.savings_share_bp / 100}%`, background: accountColor(a) }} />
          ))}
        </div>
        <ul className="divide-y text-sm">
          {shares.map((a) => (
            <li key={a.id} className="flex items-center gap-2 py-2">
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: accountColor(a) }} />
              <span className="min-w-0 flex-1 truncate">{a.name}</span>
              <span className="font-medium tabular">{formatPercent(a.savings_share_bp, 0)}</span>
              {rate ? <span className="w-24 text-right text-muted-foreground tabular">≈ {formatEur(Math.floor((rate * a.savings_share_bp) / 10_000))}</span> : null}
            </li>
          ))}
          {rest > 0 && (
            <li className="flex items-center gap-2 py-2 text-muted-foreground">
              <span className="size-2.5 shrink-0 rounded-full bg-muted-foreground/40" />
              <span className="flex-1">{shares.length ? 'bleibt ohne Anlageort' : 'Noch keine Aufteilung festgelegt'}</span>
              <span className="tabular">{formatPercent(rest, 0)}</span>
              {rate ? <span className="w-24 text-right tabular">≈ {formatEur(Math.floor((rate * rest) / 10_000))}</span> : null}
            </li>
          )}
        </ul>
      </CardContent>
    </Card>
  )
}

function EntriesCard({ data }: { data: Wealth }) {
  const byId = new Map(data.accounts.map((a) => [a.id, a]))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bewegungen</CardTitle>
        <CardDescription>Jede Zuordnung ist eine eigene Zeile und wird nie verändert.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y text-sm">
          {data.entries.slice(0, 30).map((e) => {
            const a = byId.get(e.account_id)
            return (
              <li key={e.id} className="flex items-start gap-3 py-2.5">
                <span className="mt-1.5 size-2.5 shrink-0 rounded-full" style={{ background: a ? accountColor(a) : undefined }} />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{a?.name}</span>
                  <span className="text-muted-foreground"> · {ACCOUNT_ENTRY_LABELS[e.kind] ?? e.kind}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {formatDateTime(e.occurred_at)}
                    {e.note && ` · ${e.note}`}
                  </span>
                </span>
                <Money cents={e.amount_cents} signed className={cn('font-semibold', e.amount_cents > 0 && 'text-good')} />
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------- dialogs

function useDone(onClose: () => void) {
  return {
    done: (msg: string) => () => {
      toast.success(msg)
      onClose()
    },
    fail: (err: unknown) => toast.error(errorMessage(err)),
  }
}

function AccountSelect({ id, value, onChange, accounts, placeholder }: { id: string; value: string; onChange: (v: string) => void; accounts: Account[]; placeholder: string }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {accounts.map((a) => (
          <SelectItem key={a.id} value={String(a.id)}>
            <span className="size-2 rounded-full" style={{ background: accountColor(a) }} /> {a.name} · {formatEur(a.booked_cents)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function AccountDialog({ state, onClose }: { state: { account: Account | null; kind?: AccountKind } | null; onClose: () => void }) {
  const account = state?.account ?? null
  const initialKind = account?.kind ?? state?.kind ?? 'savings_account'
  const [name, setName] = useState(account?.name ?? (state?.kind ? QUICK_START.find((q) => q.kind === state.kind)?.name ?? '' : ''))
  const [institution, setInstitution] = useState(account?.institution ?? '')
  const [kind, setKind] = useState<AccountKind>(initialKind)
  const [share, setShare] = useState('')
  const [holdsReserve, setHoldsReserve] = useState(account?.holds_reserve ?? false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { done, fail } = useDone(onClose)

  const save = useFinanceMutation(() => {
    const body = { name, institution: institution.trim() || null, kind, holds_reserve: holdsReserve }
    if (account) return api.patch(`/accounts/${account.id}`, body)
    const pct = share.trim() === '' ? 0 : Number(share.replace(',', '.'))
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) throw new Error('Der Anteil muss zwischen 0 und 100 % liegen')
    return api.post('/accounts', { ...body, savings_share_bp: Math.round(pct * 100) })
  })
  const archive = useFinanceMutation(() => api.patch(`/accounts/${account!.id}`, { archived: !account!.archived }))
  const remove = useFinanceMutation(() => api.delete(`/accounts/${account!.id}`))

  return (
    <ResponsiveDialog
      open={state !== null}
      onOpenChange={(o) => !o && onClose()}
      title={account ? 'Anlageort bearbeiten' : 'Neuer Anlageort'}
      description={account ? undefined : 'Ein Ort, an dem Geld liegt: ein Konto, ein Depot oder Bargeld.'}
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {account && (
            <Button variant="ghost" onClick={() => archive.mutate(undefined, { onSuccess: done(account.archived ? 'Reaktiviert' : 'Archiviert'), onError: fail })}>
              <Archive /> {account.archived ? 'Reaktivieren' : 'Archivieren'}
            </Button>
          )}
          {account && (
            <Button
              variant="destructive"
              onClick={() => (confirmDelete ? remove.mutate(undefined, { onSuccess: done('Anlageort gelöscht'), onError: fail }) : setConfirmDelete(true))}
            >
              <Trash2 /> {confirmDelete ? 'Wirklich löschen' : 'Löschen'}
            </Button>
          )}
          <Button type="submit" form="account-form" disabled={save.isPending}>
            Speichern
          </Button>
        </div>
      }
    >
      <form
        id="account-form"
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          save.mutate(undefined, { onSuccess: done(account ? 'Anlageort gespeichert' : 'Anlageort angelegt'), onError: fail })
        }}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(Object.keys(ACCOUNT_KINDS) as AccountKind[]).map((k) => {
            const Icon = ACCOUNT_KINDS[k].icon
            const selected = k === kind
            return (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                aria-pressed={selected}
                className={cn(
                  'flex flex-col items-center gap-1 rounded-xl border p-2.5 text-center text-xs transition-colors',
                  selected ? 'border-foreground bg-muted font-medium' : 'hover:bg-muted/60',
                )}
              >
                <Icon className="size-5" />
                <span className="leading-tight">{ACCOUNT_KINDS[k].label.replace(' (ETF, Aktien)', '')}</span>
              </button>
            )
          })}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="acc-name">Name</Label>
            <Input id="acc-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={64} placeholder="z. B. ETF-Depot" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="acc-inst">Bank oder Anbieter (optional)</Label>
            <Input id="acc-inst" value={institution} onChange={(e) => setInstitution(e.target.value)} maxLength={64} placeholder="z. B. ING, Trade Republic" />
          </div>
          {!account && (
            <div className="space-y-1.5">
              <Label htmlFor="acc-share">Anteil der Sparrate in % (optional)</Label>
              <Input id="acc-share" inputMode="decimal" value={share} onChange={(e) => setShare(e.target.value)} placeholder="z. B. 60" />
            </div>
          )}
        </div>
        <label className="flex items-center justify-between gap-3 rounded-lg border p-3">
          <span className="text-sm">
            Hier liegt meine Reserve
            <span className="block text-xs text-muted-foreground">Die Notfallreserve wird diesem Ort zugerechnet. Nur ein Ort ist möglich.</span>
          </span>
          <Switch checked={holdsReserve} onCheckedChange={setHoldsReserve} />
        </label>
      </form>
    </ResponsiveDialog>
  )
}

function AssignDialog({ state, data, onClose }: { state: { account: Account | null } | null; data: Wealth; onClose: () => void }) {
  const accounts = data.accounts.filter((a) => !a.archived)
  const [accountId, setAccountId] = useState(state?.account ? String(state.account.id) : accounts.length === 1 ? String(accounts[0]!.id) : '')
  const [direction, setDirection] = useState<'in' | 'out'>(data.unassigned_cents > 0 ? 'in' : 'out')
  const [amount, setAmount] = useState(data.unassigned_cents > 0 ? centsToInput(data.unassigned_cents) : '')
  const [key] = useState(newIdempotencyKey)
  const { done, fail } = useDone(onClose)
  const selected = accounts.find((a) => String(a.id) === accountId)

  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    if (!accountId) throw new Error('Bitte einen Anlageort wählen')
    return api.post(`/accounts/${accountId}/assign`, { amount_cents: direction === 'in' ? cents : -cents }, key)
  })

  return (
    <ResponsiveDialog
      open={state !== null}
      onOpenChange={(o) => !o && onClose()}
      title="Ersparnisse zuordnen"
      description={
        <>
          Ohne Anlageort: <Money cents={data.unassigned_cents} />. Es wird kein Geld erzeugt, nur festgehalten, wo es liegt.
        </>
      }
      footer={
        <Button type="submit" form="assign-form" disabled={save.isPending}>
          {direction === 'in' ? 'Zuordnen' : 'Lösen'}
        </Button>
      }
    >
      <form id="assign-form" className="space-y-4" onSubmit={(e) => (e.preventDefault(), save.mutate(undefined, { onSuccess: done('Gespeichert'), onError: fail }))}>
        <Tabs value={direction} onValueChange={(v) => setDirection(v as 'in' | 'out')}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="in">Auf Anlageort</TabsTrigger>
            <TabsTrigger value="out">Zurück, ohne Ort</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="space-y-1.5">
          <Label htmlFor="assign-account">Anlageort</Label>
          <AccountSelect id="assign-account" value={accountId} onChange={setAccountId} accounts={accounts} placeholder="Anlageort wählen" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="assign-amount">Betrag</Label>
          <MoneyInput id="assign-amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
          {direction === 'out' && selected && (
            <p className="text-xs text-muted-foreground">
              Auf {selected.name}: <Money cents={selected.booked_cents} />
            </p>
          )}
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function MoveDialog({ state, accounts, onClose }: { state: { from: Account | null } | null; accounts: Account[]; onClose: () => void }) {
  const [from, setFrom] = useState(state?.from ? String(state.from.id) : '')
  const [to, setTo] = useState('')
  const [amount, setAmount] = useState('')
  const [key] = useState(newIdempotencyKey)
  const { done, fail } = useDone(onClose)

  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    if (!from || !to) throw new Error('Bitte Quelle und Ziel wählen')
    return api.post('/accounts/move', { from_account_id: Number(from), to_account_id: Number(to), amount_cents: cents }, key)
  })

  return (
    <ResponsiveDialog
      open={state !== null}
      onOpenChange={(o) => !o && onClose()}
      title="Geld verschieben"
      description="Zum Beispiel vom Tagesgeld ins Depot. Deine Ersparnisse bleiben gleich, nur der Ort ändert sich."
      footer={
        <Button type="submit" form="move-form" disabled={save.isPending}>
          Verschieben
        </Button>
      }
    >
      <form id="move-form" className="space-y-4" onSubmit={(e) => (e.preventDefault(), save.mutate(undefined, { onSuccess: done('Verschoben'), onError: fail }))}>
        <div className="space-y-1.5">
          <Label htmlFor="move-from">Von</Label>
          <AccountSelect id="move-from" value={from} onChange={setFrom} accounts={accounts} placeholder="Quelle wählen" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="move-to">Nach</Label>
          <AccountSelect id="move-to" value={to} onChange={setTo} accounts={accounts.filter((a) => String(a.id) !== from)} placeholder="Ziel wählen" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="move-amount">Betrag</Label>
          <MoneyInput id="move-amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function ValuationDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const [value, setValue] = useState(account ? centsToInput(account.value_cents) : '')
  const { done, fail } = useDone(onClose)
  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(value)
    if (cents === null) throw new Error('Bitte einen gültigen Wert eingeben')
    return api.post(`/accounts/${account!.id}/valuations`, { value_cents: cents })
  })
  const preview = parseEuroInput(value)
  return (
    <ResponsiveDialog
      open={account !== null}
      onOpenChange={(o) => !o && onClose()}
      title={account ? `Aktueller Wert: ${account.name}` : ''}
      description="Trag den Wert ein, den deine Bank oder App gerade anzeigt. Die App fragt keine Kurse aus dem Internet ab."
      footer={
        <Button type="submit" form="value-form" disabled={save.isPending}>
          Wert speichern
        </Button>
      }
    >
      <form id="value-form" className="space-y-4" onSubmit={(e) => (e.preventDefault(), save.mutate(undefined, { onSuccess: done('Wert gespeichert'), onError: fail }))}>
        <div className="space-y-1.5">
          <Label htmlFor="value-amount">Depotwert heute</Label>
          <MoneyInput id="value-amount" value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
        </div>
        {account && preview !== null && (
          <div className="rounded-lg bg-muted/60 p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Eingezahlt</span>
              <Money cents={account.booked_cents} />
            </div>
            <GainLine cents={preview - account.booked_cents} className="mt-1" suffix="Gewinn oder Verlust" />
          </div>
        )}
        {account && account.valuations.length > 0 && (
          <ul className="divide-y text-sm">
            {account.valuations.slice(0, 5).map((v) => (
              <li key={v.id} className="flex justify-between py-1.5 text-muted-foreground">
                <span>{formatDate(v.valued_at)}</span>
                <Money cents={v.value_cents} />
              </li>
            ))}
          </ul>
        )}
      </form>
    </ResponsiveDialog>
  )
}

function SplitDialog({ open, accounts, onClose }: { open: boolean; accounts: Account[]; onClose: () => void }) {
  const [shares, setShares] = useState<Record<number, number>>(() => Object.fromEntries(accounts.map((a) => [a.id, a.savings_share_bp / 100])))
  const { done, fail } = useDone(onClose)
  const sum = Object.values(shares).reduce((s, x) => s + x, 0)
  const over = sum > 100

  const save = useFinanceMutation(() =>
    api.put('/accounts/shares', {
      shares: accounts.map((a) => ({ account_id: a.id, share_bp: Math.round((shares[a.id] ?? 0) * 100) })),
    }),
  )

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title="Sparrate aufteilen"
      description="Gilt ab dem nächsten Gehalt. Was keinem Ort zugeteilt ist, bleibt als Ersparnis ohne Ort und kann später zugeordnet werden."
      footer={
        <Button type="submit" form="split-form" disabled={save.isPending || over}>
          Speichern
        </Button>
      }
    >
      <form id="split-form" className="space-y-5" onSubmit={(e) => (e.preventDefault(), save.mutate(undefined, { onSuccess: done('Aufteilung gespeichert'), onError: fail }))}>
        <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-muted">
          {accounts.map((a) => (
            <div key={a.id} className="h-full transition-[width] duration-200" style={{ width: `${Math.min(shares[a.id] ?? 0, 100)}%`, background: accountColor(a) }} />
          ))}
        </div>
        {accounts.map((a) => (
          <div key={a.id} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor={`share-${a.id}`} className="flex items-center gap-2">
                <span className="size-2.5 rounded-full" style={{ background: accountColor(a) }} /> {a.name}
              </Label>
              <span className="w-14 text-right text-sm font-semibold tabular">{shares[a.id] ?? 0} %</span>
            </div>
            <input
              id={`share-${a.id}`}
              type="range"
              min={0}
              max={100}
              step={1}
              value={shares[a.id] ?? 0}
              onChange={(e) => setShares((s) => ({ ...s, [a.id]: Number(e.target.value) }))}
              className="h-2 w-full cursor-pointer"
              style={{ accentColor: accountColor(a) }}
            />
          </div>
        ))}
        <p className={cn('rounded-lg p-3 text-sm', over ? 'bg-critical/10 text-critical' : 'bg-muted/60 text-muted-foreground')}>
          {over ? `Zusammen ${sum} %. Höchstens 100 % sind möglich.` : `Zusammen ${sum} %, ${100 - sum} % bleiben ohne Anlageort.`}
        </p>
      </form>
    </ResponsiveDialog>
  )
}
