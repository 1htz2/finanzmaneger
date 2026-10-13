import { ArrowRight, CheckCircle2, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { Money, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, newIdempotencyKey } from '@/lib/api'
import { BUCKETS, bucketOf } from '@/lib/domain'
import { localInputToApi, nowLocalInput, parseEuroInput, periodRange } from '@/lib/format'
import { useFinanceMutation } from '@/lib/queries'
import type { SalaryPreview, SalaryResult } from '@/lib/types'

type Step = 'input' | 'preview' | 'done'

export function SalaryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [step, setStep] = useState<Step>('input')
  const [amount, setAmount] = useState('')
  const [when, setWhen] = useState(nowLocalInput())
  const [description, setDescription] = useState('')
  const [payday, setPayday] = useState('')
  const [cover, setCover] = useState(false)
  const [preview, setPreview] = useState<SalaryPreview | null>(null)
  const [result, setResult] = useState<SalaryResult | null>(null)
  const [busy, setBusy] = useState(false)
  // One key per dialog session (remounted on open): a double tap or a retry cannot open two periods.
  const [key] = useState(newIdempotencyKey)

  const cents = parseEuroInput(amount)

  async function loadPreview(e: FormEvent) {
    e.preventDefault()
    if (!cents) {
      toast.error('Bitte das erhaltene Nettogehalt eingeben, z. B. 1.300,00')
      return
    }
    setBusy(true)
    try {
      setPreview(
        await api.post<SalaryPreview>('/salary/preview', {
          amount_cents: cents,
          received_at: localInputToApi(when),
        }),
      )
      setStep('preview')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const record = useFinanceMutation(() =>
    api.post<SalaryResult>(
      '/salary',
      {
        amount_cents: cents,
        received_at: localInputToApi(when),
        description: description || null,
        cover_deficit_from_reserve: cover,
        expected_next_payday: payday || null,
      },
      key,
    ),
  )

  function confirm() {
    record.mutate(undefined, {
      onSuccess: (r) => {
        setResult(r)
        setStep('done')
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }

  const closing = preview?.closing

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      wide={step !== 'input'}
      title={step === 'done' ? 'Neue Budgetperiode gestartet' : 'Gehalt erfassen'}
      description={
        step === 'input'
          ? 'Das tatsächlich erhaltene Nettogehalt. Es startet eine neue Budgetperiode.'
          : step === 'preview'
            ? 'Bitte prüfe, was sich durch diesen Gehaltseingang ändert.'
            : undefined
      }
      footer={
        step === 'input' ? (
          <Button type="submit" form="salary-form" size="lg" disabled={busy} className="w-full sm:w-auto">
            {busy ? 'Berechne …' : 'Weiter zur Vorschau'} <ArrowRight />
          </Button>
        ) : step === 'preview' ? (
          <div className="flex w-full flex-col-reverse gap-2 sm:w-auto sm:flex-row">
            <Button variant="outline" size="lg" onClick={() => setStep('input')} disabled={record.isPending}>
              Zurück
            </Button>
            <Button size="lg" onClick={confirm} disabled={record.isPending}>
              {record.isPending ? 'Bucht …' : closing ? 'Periode abschließen & starten' : 'Budget starten'}
            </Button>
          </div>
        ) : (
          <Button size="lg" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
            Fertig
          </Button>
        )
      }
    >
      {step === 'input' && (
        <form id="salary-form" onSubmit={loadPreview} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="salary-amount">Nettogehalt</Label>
            <MoneyInput
              id="salary-amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              autoFocus
              className="h-12 text-lg font-semibold"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="salary-when">Geldeingang</Label>
            <Input id="salary-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="salary-desc">Beschreibung (optional)</Label>
            <Input
              id="salary-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="z. B. Gehalt November"
              maxLength={255}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="salary-payday">Erwarteter nächster Zahltag (optional)</Label>
            <Input id="salary-payday" type="date" value={payday} onChange={(e) => setPayday(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              Damit berechnet die App dein Tages- und Wochenbudget. Ohne Datum gibt es keine zeitbasierte Prognose.
            </p>
          </div>
        </form>
      )}

      {step === 'preview' && preview && (
        <div className="space-y-5">
          {closing ? (
            <section className="rounded-xl border p-4">
              <h3 className="text-sm font-semibold">
                Abschluss der aktuellen Periode <span className="font-normal text-muted-foreground">({periodRange(closing.period.started_at, new Date(localInputToApi(when)).toISOString())})</span>
              </h3>
              <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-sm">
                {(['fixed', 'leisure'] as const).map((b) => {
                  const s = bucketOf(closing.period, b)
                  return (
                    <div key={b} className="contents">
                      <dt className="text-muted-foreground">
                        {BUCKETS[b].label}: <Money cents={s.spent_cents} /> von <Money cents={s.budget_cents} />
                      </dt>
                      <dd className="text-right">
                        <Money cents={s.available_cents} signed />
                      </dd>
                    </div>
                  )
                })}
                <dt className="border-t pt-1.5 font-medium">Ergebnis</dt>
                <dd className="border-t pt-1.5 text-right font-medium">
                  <Money cents={closing.leftover_cents} signed />
                </dd>
              </dl>
              {closing.deficit_cents > 0 ? (
                <div className="mt-3 space-y-3 rounded-lg bg-critical/10 p-3 text-sm">
                  <p className="flex gap-2">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-critical" />
                    <span>
                      Defizit von <Money cents={closing.deficit_cents} />. Es gibt keine Reserve-Zuführung.
                    </span>
                  </p>
                  {closing.coverable_from_reserve_cents > 0 && (
                    <label className="flex items-center gap-2">
                      <Checkbox checked={cover} onCheckedChange={(v) => setCover(v === true)} />
                      <span>
                        <Money cents={closing.coverable_from_reserve_cents} /> bewusst aus der Reserve decken
                      </span>
                    </label>
                  )}
                </div>
              ) : (
                <p className="mt-3 flex gap-2 rounded-lg bg-good/10 p-3 text-sm">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" />
                  <span>
                    <Money cents={closing.reserve_transfer_cents} className="font-semibold" /> wandern in deine Reserve.
                  </span>
                </p>
              )}
              {closing.transactions_moving_to_new_period > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {closing.transactions_moving_to_new_period} Buchung(en) nach dem Geldeingang werden der neuen
                  Periode zugeordnet.
                </p>
              )}
            </section>
          ) : (
            <p className="text-sm text-muted-foreground">Das ist dein erster Gehaltseingang. Es wird nichts abgeschlossen.</p>
          )}

          <section className="rounded-xl border p-4">
            <h3 className="text-sm font-semibold">Neues Budget · {preview.budget_model_label}</h3>
            <ul className="mt-3 grid gap-2 sm:grid-cols-3">
              {preview.new_split.map((s) => {
                const meta = BUCKETS[s.bucket]
                return (
                  <li key={s.bucket} className="rounded-lg bg-muted/60 p-3">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="size-2.5 rounded-full" style={{ background: meta.color }} />
                      {meta.label} · {s.percent} %
                    </div>
                    <Money cents={s.amount_cents} className="mt-1 block text-lg font-semibold" />
                  </li>
                )
              })}
            </ul>
          </section>

          <section className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg border p-3">
              <div className="text-xs text-muted-foreground">Reserve</div>
              <Money cents={preview.reserve_balance_before_cents} /> →{' '}
              <Money
                cents={preview.reserve_balance_after_cents - (cover ? (closing?.coverable_from_reserve_cents ?? 0) : 0)}
                className="font-semibold"
              />
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs text-muted-foreground">Ersparnisse</div>
              <Money cents={preview.savings_balance_before_cents} /> →{' '}
              <Money cents={preview.savings_balance_after_cents} className="font-semibold" />
            </div>
          </section>
        </div>
      )}

      {step === 'done' && result && (
        <div className="space-y-4 text-sm">
          <p className="flex items-center gap-2 text-base">
            <CheckCircle2 className="size-5 text-good" /> Gehalt von{' '}
            <Money cents={result.new_period.net_salary_cents} className="font-semibold" /> gebucht.
          </p>
          <ul className="space-y-1.5">
            {result.closed_period && (
              <li>
                Vorherige Periode abgeschlossen:{' '}
                {result.reserve_transfer_cents > 0 ? (
                  <>
                    <Money cents={result.reserve_transfer_cents} /> zur Reserve.
                  </>
                ) : (
                  <>
                    Defizit <Money cents={result.deficit_cents + result.deficit_covered_cents} />
                    {result.deficit_covered_cents > 0 && (
                      <>
                        , davon <Money cents={result.deficit_covered_cents} /> aus der Reserve gedeckt
                      </>
                    )}
                    .
                  </>
                )}
              </li>
            )}
            <li>
              Neue Reserve: <Money cents={result.reserve_balance_cents} className="font-medium" />
            </li>
            <li>
              Ersparnisse gesamt: <Money cents={result.savings_balance_cents} className="font-medium" />
            </li>
            <li>
              Freizeitbudget: <Money cents={bucketOf(result.new_period, 'leisure').budget_cents} className="font-medium" />
              , Fixkosten: <Money cents={bucketOf(result.new_period, 'fixed').budget_cents} className="font-medium" />
            </li>
          </ul>
        </div>
      )}
    </ResponsiveDialog>
  )
}
