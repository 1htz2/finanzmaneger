import { ArrowDownToLine, ArrowLeftRight, ArrowUpFromLine, Info, Pencil, ShieldCheck, Target } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { useActions } from '@/components/Actions'
import { BalanceChart, ProgressBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, newIdempotencyKey } from '@/lib/api'
import { RESERVE_KIND_LABELS } from '@/lib/domain'
import { centsToInput, formatDateTime, formatEur, formatPercent, parseEuroInput } from '@/lib/format'
import { useFinanceMutation, useReserve } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function ReservePage() {
  const { data, isLoading, error, refetch } = useReserve()
  const { addTransaction } = useActions()
  const [dialog, setDialog] = useState<'deposit' | 'withdraw' | null>(null)
  const [setupSession, setSetupSession] = useState(0)
  const [setupOpen, setSetupOpen] = useState(false)

  if (isLoading) return <LoadingState rows={3} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />
  const hasTarget = data.minimum_cents > 0
  const reached = hasTarget && data.balance_cents >= data.minimum_cents
  const progressBp = hasTarget ? Math.round((Math.max(data.balance_cents, 0) * 10_000) / data.minimum_cents) : 0
  const openSetup = () => {
    setSetupSession((n) => n + 1)
    setSetupOpen(true)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reserve"
        description="Deine Notfallreserve für Unvorhergesehenes. Sie wächst automatisch mit nicht verbrauchtem Budget und ist getrennt von deinen Ersparnissen."
        actions={
          <>
            <Button variant="outline" onClick={() => setDialog('deposit')}>
              <ArrowDownToLine /> Zuführen
            </Button>
            <Button variant="outline" onClick={() => setDialog('withdraw')}>
              <ArrowUpFromLine /> Entnehmen
            </Button>
            <Button variant="outline" onClick={() => addTransaction({ tab: 'transfer' })}>
              <ArrowLeftRight /> Umbuchen
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1" role="region" aria-label="Notfallreserve">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-normal text-muted-foreground">
              <ShieldCheck className="size-4" /> Notfallreserve
            </CardTitle>
            {hasTarget && (
              <CardAction>
                <Button variant="ghost" size="icon-sm" aria-label="Ziel ändern" onClick={openSetup}>
                  <Pencil />
                </Button>
              </CardAction>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <Money cents={data.balance_cents} className={cn('block text-4xl font-semibold tracking-tight', data.balance_cents < 0 && 'text-critical')} />
            {hasTarget ? (
              <>
                <ProgressBar bp={progressBp} color="var(--good)" label="Notfallreserve aufgebaut" />
                <p className="flex justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {formatPercent(Math.min(progressBp, 10_000), 0)} von <Money cents={data.minimum_cents} />
                  </span>
                  <span className={cn(reached ? 'text-good' : 'text-muted-foreground')}>
                    {reached ? 'Ziel erreicht' : <>noch <Money cents={data.minimum_cents - data.balance_cents} /></>}
                  </span>
                </p>
              </>
            ) : (
              <div className="space-y-3 rounded-lg border border-dashed p-3">
                <p className="text-sm text-muted-foreground">
                  {data.balance_cents > 0
                    ? 'Lege ein Ziel fest, damit du siehst, wie weit deine Notfallreserve schon reicht.'
                    : 'Du hast noch keine Notfallreserve. Leg ein Ziel fest und trag ein, was du schon zur Seite gelegt hast.'}
                </p>
                <Button className="w-full" onClick={openSetup}>
                  <Target /> Notfallreserve einrichten
                </Button>
              </div>
            )}
            <p className="flex gap-2 rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" />
              Die Reserve ist ein virtueller Budgettopf. Sie entspricht nicht automatisch einem eigenen Bankkonto.
            </p>
          </CardContent>
        </Card>
        <div className="grid grid-cols-2 gap-3 lg:col-span-2">
          <StatTile label="Aus Periodenabschlüssen" value={<Money cents={data.total_from_periods_cents} />} hint="inkl. Korrekturen" />
          <StatTile label="Entnommen" value={<Money cents={data.total_withdrawn_cents} />} />
          <Card className="col-span-2 gap-2 py-4">
            <CardContent className="px-4">
              <div className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Wofür die Reserve gedacht ist</div>
              <div className="flex flex-wrap gap-2">
                {data.purposes.map((p) => (
                  <Badge key={p} variant="secondary">
                    {p}
                  </Badge>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">Anpassbar unter Einstellungen.</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Verlauf</CardTitle>
        </CardHeader>
        <CardContent>
          {data.history.length < 2 ? (
            <EmptyState title="Noch kein Verlauf" text="Beim nächsten Periodenabschluss wird nicht verbrauchtes Budget automatisch zugeführt." />
          ) : (
            <BalanceChart points={data.history} name="Reserve" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Alle Bewegungen</CardTitle>
          <CardDescription>Lückenloses Protokoll. Einträge werden nie verändert, Korrekturen erscheinen als eigene Zeilen.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.entries.length === 0 ? (
            <EmptyState title="Noch keine Bewegungen" />
          ) : (
            <ul className="divide-y text-sm">
              {data.entries.map((e) => (
                <li key={e.id} className="flex items-start gap-3 py-2.5">
                  <span className="flex-1">
                    <span className="font-medium">{RESERVE_KIND_LABELS[e.kind] ?? e.kind}</span>
                    {e.purpose && <Badge variant="outline" className="ml-2">{e.purpose}</Badge>}
                    <span className="block text-xs text-muted-foreground">
                      {formatDateTime(e.occurred_at)}
                      {e.note && ` · ${e.note}`}
                    </span>
                  </span>
                  <Money cents={e.amount_cents} signed className={cn('font-semibold', e.amount_cents > 0 && 'text-good')} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <SetupDialog
        key={`setup-${setupSession}`}
        open={setupOpen}
        firstTime={!hasTarget}
        currentTarget={data.minimum_cents}
        balance={data.balance_cents}
        monthlySpending={data.monthly_spending_cents}
        onClose={() => setSetupOpen(false)}
      />
      <ReserveDialog mode={dialog} purposes={data.purposes} balance={data.balance_cents} onClose={() => setDialog(null)} />
    </div>
  )
}

function ReserveDialog({
  mode,
  purposes,
  balance,
  onClose,
}: {
  mode: 'deposit' | 'withdraw' | null
  purposes: string[]
  balance: number
  onClose: () => void
}) {
  const [amount, setAmount] = useState('')
  const [purpose, setPurpose] = useState('')
  const [text, setText] = useState('')
  const key = useMemo(() => (mode ? newIdempotencyKey() : ''), [mode])

  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    return mode === 'deposit'
      ? api.post('/reserve/deposit', { amount_cents: cents, note: text }, key)
      : api.post('/reserve/withdraw', { amount_cents: cents, purpose, reason: text }, key)
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (mode === 'withdraw' && !purpose) return toast.error('Bitte einen Verwendungszweck wählen')
    save.mutate(undefined, {
      onSuccess: () => {
        toast.success(mode === 'deposit' ? 'Reserve aufgestockt' : 'Entnahme gebucht')
        setAmount('')
        setPurpose('')
        setText('')
        onClose()
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }

  return (
    <ResponsiveDialog
      open={mode !== null}
      onOpenChange={(o) => !o && onClose()}
      title={mode === 'deposit' ? 'Reserve manuell aufstocken' : 'Aus der Reserve entnehmen'}
      description={
        mode === 'deposit' ? (
          'Zum Beispiel vorhandenes Bargeld, das du als Puffer einplanen möchtest.'
        ) : (
          <>Verfügbar: <Money cents={balance} />. Die Entnahme wird mit Grund protokolliert.</>
        )
      }
      footer={
        <Button type="submit" form="reserve-form" disabled={save.isPending}>
          {mode === 'deposit' ? 'Zuführen' : 'Entnehmen'}
        </Button>
      }
    >
      <form id="reserve-form" onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="res-amount">Betrag</Label>
          <MoneyInput id="res-amount" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
        </div>
        {mode === 'withdraw' && (
          <div className="space-y-1.5">
            <Label htmlFor="res-purpose">Verwendungszweck</Label>
            <Select value={purpose} onValueChange={setPurpose}>
              <SelectTrigger id="res-purpose" className="w-full">
                <SelectValue placeholder="Zweck wählen" />
              </SelectTrigger>
              <SelectContent>
                {purposes.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="res-text">{mode === 'deposit' ? 'Notiz' : 'Grund'}</Label>
          <Input id="res-text" value={text} onChange={(e) => setText(e.target.value)} required maxLength={255} placeholder={mode === 'deposit' ? 'z. B. Bargeldbestand' : 'z. B. Fahrradreparatur'} />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function SetupDialog({
  open,
  firstTime,
  currentTarget,
  balance,
  monthlySpending,
  onClose,
}: {
  open: boolean
  firstTime: boolean
  currentTarget: number
  balance: number
  monthlySpending: number | null
  onClose: () => void
}) {
  // Fresh state per dialog session: the page remounts this component with a new key on each open.
  const [target, setTarget] = useState(currentTarget > 0 ? centsToInput(currentTarget) : '')
  const [starting, setStarting] = useState('')
  const [key] = useState(newIdempotencyKey)
  const suggestions = monthlySpending ? [3, 6].map((months) => ({ months, cents: monthlySpending * months })) : []

  const save = useFinanceMutation(() => {
    const targetCents = parseEuroInput(target)
    if (!targetCents) throw new Error('Bitte einen Zielbetrag eingeben')
    const startingCents = starting.trim() === '' ? 0 : parseEuroInput(starting)
    if (startingCents === null) throw new Error('Bitte einen gültigen Startbetrag eingeben')
    return api.post('/reserve/setup', { target_cents: targetCents, starting_cents: startingCents }, key)
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate(undefined, {
      onSuccess: () => {
        toast.success(firstTime ? 'Notfallreserve eingerichtet' : 'Ziel gespeichert')
        onClose()
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={firstTime ? 'Notfallreserve einrichten' : 'Ziel der Notfallreserve'}
      description="Üblich sind drei bis sechs Monate deiner Ausgaben. Damit überstehst du eine Reparatur, eine hohe Rechnung oder eine Lücke beim Einkommen."
      footer={
        <Button type="submit" form="setup-form" disabled={save.isPending}>
          {firstTime ? 'Einrichten' : 'Speichern'}
        </Button>
      }
    >
      <form id="setup-form" onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="setup-target">Zielbetrag</Label>
          <MoneyInput id="setup-target" value={target} onChange={(e) => setTarget(e.target.value)} autoFocus />
          {suggestions.length > 0 && (
            <>
              <div className="flex flex-wrap gap-2 pt-1">
                {suggestions.map((sug) => (
                  <Button key={sug.months} type="button" size="sm" variant="outline" onClick={() => setTarget(centsToInput(sug.cents))}>
                    {sug.months} Monate · {formatEur(sug.cents)}
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">Vorschläge aus Fixkosten- und Freizeitbudget deiner letzten Periode.</p>
            </>
          )}
        </div>
        {firstTime && (
          <div className="space-y-1.5">
            <Label htmlFor="setup-starting">Schon vorhanden (optional)</Label>
            <MoneyInput id="setup-starting" value={starting} onChange={(e) => setStarting(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              Geld, das du bereits als Notgroschen zur Seite gelegt hast
              {balance > 0 ? `, zusätzlich zu den aktuellen ${formatEur(balance)}` : ''}.
            </p>
          </div>
        )}
        <div className="rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">
          <p className="mb-1 font-medium text-foreground">So wächst die Reserve</p>
          <ul className="list-disc space-y-0.5 pl-4">
            <li>automatisch mit nicht verbrauchtem Budget beim nächsten Gehalt</li>
            <li>mit „Zuführen“, wenn du zusätzlich etwas zurücklegst</li>
            <li>mit „Umbuchen“ aus deinen Ersparnissen</li>
          </ul>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
