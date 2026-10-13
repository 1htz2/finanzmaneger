import { Archive, ArchiveRestore, Database, Download, FileJson, FileSpreadsheet, KeyRound, Plus, Shield, Tags, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ErrorState, LoadingState, PageHeader, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api'
import { CATEGORY_KIND_LABELS } from '@/lib/domain'
import { centsToInput, parseEuroInput } from '@/lib/format'
import { useCategories, useFinanceMutation, useSettings } from '@/lib/queries'
import type { AppSettings, Category, CategoryKind } from '@/lib/types'

export function SettingsPage() {
  const settings = useSettings()
  return (
    <div className="space-y-6">
      <PageHeader title="Einstellungen" />
      {settings.isLoading ? (
        <LoadingState rows={2} />
      ) : settings.error || !settings.data ? (
        <ErrorState error={settings.error} onRetry={() => settings.refetch()} />
      ) : (
        <BudgetSettings key={settings.data.reserve_purposes.join('|')} settings={settings.data} />
      )}
      <Categories />
      <DataExport />
      <PasswordChange />
    </div>
  )
}

function BudgetSettings({ settings }: { settings: AppSettings }) {
  const [minimum, setMinimum] = useState(centsToInput(settings.reserve_minimum_cents))
  const [large, setLarge] = useState(centsToInput(settings.large_expense_threshold_cents))
  const [purposes, setPurposes] = useState(settings.reserve_purposes)
  const [newPurpose, setNewPurpose] = useState('')

  const save = useFinanceMutation((body: Partial<AppSettings>) => api.put<AppSettings>('/settings', body))

  function submit(e: FormEvent) {
    e.preventDefault()
    const min = parseEuroInput(minimum)
    const lg = parseEuroInput(large)
    if (min === null || !lg) return toast.error('Bitte gültige Beträge eingeben')
    save.mutate(
      { reserve_minimum_cents: min, large_expense_threshold_cents: lg, reserve_purposes: purposes },
      { onSuccess: () => toast.success('Einstellungen gespeichert'), onError: (err) => toast.error(errorMessage(err)) },
    )
  }

  const model = settings.budget_models.find((m) => m.key === settings.budget_model_key)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Budget und Warnungen</CardTitle>
        <CardDescription>
          Budgetmodell: {model?.label}. Währung EUR, Zeitzone Europe/Berlin.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="s-min">Mindesthöhe der Reserve</Label>
              <MoneyInput id="s-min" value={minimum} onChange={(e) => setMinimum(e.target.value)} />
              <p className="text-xs text-muted-foreground">0 schaltet die Warnung aus.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-large">Große Ausgabe ab</Label>
              <MoneyInput id="s-large" value={large} onChange={(e) => setLarge(e.target.value)} />
              <p className="text-xs text-muted-foreground">Einzelne Ausgaben ab diesem Betrag erscheinen als Hinweis.</p>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Wofür die Reserve verwendet werden darf</Label>
            <div className="flex flex-wrap gap-2">
              {purposes.map((p) => (
                <Badge key={p} variant="secondary" className="gap-1 pr-1">
                  {p}
                  <button type="button" aria-label={`${p} entfernen`} className="rounded-full p-0.5 hover:bg-muted" onClick={() => setPurposes(purposes.filter((x) => x !== p))}>
                    <X className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input value={newPurpose} onChange={(e) => setNewPurpose(e.target.value)} placeholder="Neuer Zweck" maxLength={64} />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const v = newPurpose.trim()
                  if (v && !purposes.includes(v)) setPurposes([...purposes, v])
                  setNewPurpose('')
                }}
              >
                <Plus /> Hinzufügen
              </Button>
            </div>
          </div>
          <Button type="submit" disabled={save.isPending}>
            Speichern
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function Categories() {
  const { data, isLoading } = useCategories()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<CategoryKind>('leisure')
  const [color, setColor] = useState('#64748b')
  const create = useFinanceMutation(() => api.post('/categories', { name, kind, color }))
  const update = useFinanceMutation(({ id, body }: { id: number; body: Partial<Category> }) => api.patch(`/categories/${id}`, body))
  const remove = useFinanceMutation((id: number) => api.delete(`/categories/${id}`))

  const groups: CategoryKind[] = ['leisure', 'fixed', 'income']
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Tags className="size-4" /> Kategorien
        </CardTitle>
        <CardDescription>Eigene Kategorien anlegen. Verwendete Kategorien werden archiviert statt gelöscht.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <form
          className="grid gap-2 sm:grid-cols-[1fr_10rem_4rem_auto]"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(undefined, {
              onSuccess: () => {
                toast.success('Kategorie angelegt')
                setName('')
              },
              onError: (err) => toast.error(errorMessage(err)),
            })
          }}
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name der Kategorie" required maxLength={64} aria-label="Name" />
          <Select value={kind} onValueChange={(v) => setKind(v as CategoryKind)}>
            <SelectTrigger className="w-full" aria-label="Art">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {groups.map((g) => (
                <SelectItem key={g} value={g}>
                  {CATEGORY_KIND_LABELS[g]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="h-9 p-1" aria-label="Farbe" />
          <Button type="submit" disabled={create.isPending}>
            <Plus /> Anlegen
          </Button>
        </form>
        {isLoading ? (
          <LoadingState rows={1} />
        ) : (
          <div className="grid gap-6 md:grid-cols-3">
            {groups.map((g) => (
              <div key={g}>
                <h3 className="mb-2 text-sm font-medium">{CATEGORY_KIND_LABELS[g]}</h3>
                <ul className="divide-y rounded-lg border text-sm">
                  {(data ?? [])
                    .filter((c) => c.kind === g)
                    .map((c) => (
                      <li key={c.id} className="flex items-center gap-2 px-3 py-1.5">
                        <span className="size-2.5 rounded-full" style={{ background: c.color ?? 'var(--muted-foreground)' }} />
                        <span className={c.archived ? 'flex-1 text-muted-foreground line-through' : 'flex-1'}>{c.name}</span>
                        {c.usage_count > 0 ? (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={c.archived ? 'Reaktivieren' : 'Archivieren'}
                            disabled={c.name === 'Gehalt'}
                            onClick={() => update.mutate({ id: c.id, body: { archived: !c.archived } })}
                          >
                            {c.archived ? <ArchiveRestore /> : <Archive />}
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Löschen"
                            disabled={c.name === 'Gehalt' || c.name === 'Sonstige Einnahmen'}
                            onClick={() => remove.mutate(c.id, { onError: (err) => toast.error(errorMessage(err)) })}
                          >
                            <Trash2 />
                          </Button>
                        )}
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

async function download(path: string, method: 'GET' | 'POST', fallbackName: string) {
  const csrf = document.cookie.split('; ').find((c) => c.startsWith('fm_csrf='))?.slice(8)
  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    headers: method === 'POST' && csrf ? { 'X-CSRF-Token': csrf } : {},
  })
  if (!res.ok) throw new Error('Download fehlgeschlagen')
  const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? fallbackName
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function DataExport() {
  const [busy, setBusy] = useState<string | null>(null)
  async function run(id: string, path: string, method: 'GET' | 'POST', name: string) {
    setBusy(id)
    try {
      await download(path, method, name)
      toast.success('Download gestartet')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="size-4" /> Daten und Backup
        </CardTitle>
        <CardDescription>Alles bleibt lokal. Exporte werden nur auf dein Gerät heruntergeladen.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-3">
        <Button variant="outline" disabled={busy !== null} onClick={() => run('backup', '/export/backup', 'POST', 'finanzmanager.db')}>
          <Download /> Datenbank-Backup
        </Button>
        <Button variant="outline" disabled={busy !== null} onClick={() => run('json', '/export/json', 'GET', 'finanzmanager.json')}>
          <FileJson /> Export als JSON
        </Button>
        <Button variant="outline" disabled={busy !== null} onClick={() => run('csv', '/export/transactions.csv', 'GET', 'buchungen.csv')}>
          <FileSpreadsheet /> Buchungen als CSV
        </Button>
        <p className="text-xs text-muted-foreground sm:col-span-3">
          Ein Backup wird zusätzlich im Datenordner des Servers unter <code>backups/</code> abgelegt. Wiederherstellung: siehe README.
        </p>
      </CardContent>
    </Card>
  )
}

function PasswordChange() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const change = useFinanceMutation(() => api.post('/auth/password', { current_password: current, new_password: next }))
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4" /> Passwort ändern
        </CardTitle>
        <CardDescription className="flex items-center gap-1">
          <Shield className="size-3" /> Andere angemeldete Geräte werden dabei abgemeldet.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault()
            change.mutate(undefined, {
              onSuccess: () => {
                toast.success('Passwort geändert')
                setCurrent('')
                setNext('')
              },
              onError: (err) => toast.error(errorMessage(err)),
            })
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="pw-current">Aktuelles Passwort</Label>
            <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pw-new">Neues Passwort</Label>
            <Input id="pw-new" type="password" autoComplete="new-password" minLength={10} value={next} onChange={(e) => setNext(e.target.value)} required />
          </div>
          <Button type="submit" disabled={change.isPending}>
            Ändern
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
