import { ArrowDownToLine, ArrowLeftRight, ArrowUpFromLine, Info, ShieldCheck } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { useActions } from '@/components/Actions'
import { BalanceChart } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, newIdempotencyKey } from '@/lib/api'
import { RESERVE_KIND_LABELS } from '@/lib/domain'
import { formatDateTime, parseEuroInput } from '@/lib/format'
import { useFinanceMutation, useReserve } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function ReservePage() {
  const { data, isLoading, error, refetch } = useReserve()
  const { addTransaction } = useActions()
  const [dialog, setDialog] = useState<'deposit' | 'withdraw' | null>(null)

  if (isLoading) return <LoadingState rows={3} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />
  const low = data.minimum_cents > 0 && data.balance_cents < data.minimum_cents

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reserve"
        description="Dein Puffer aus nicht verbrauchtem Budget. Getrennt von deinen langfristigen Ersparnissen."
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
        <Card className="lg:col-span-1">
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="size-4" /> Aktuelle Reserve
            </div>
            <Money cents={data.balance_cents} className={cn('block text-4xl font-semibold tracking-tight', data.balance_cents < 0 && 'text-critical')} />
            {data.minimum_cents > 0 && (
              <p className={cn('text-sm', low ? 'text-critical' : 'text-muted-foreground')}>
                Mindesthöhe <Money cents={data.minimum_cents} /> {low ? 'unterschritten' : 'erreicht'}
              </p>
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
