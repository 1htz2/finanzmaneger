import { Lock, Wallet } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { errorMessage } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { queryClient } from '@/lib/queries'

export function AuthPage({ mode }: { mode: 'setup' | 'login' }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const setup = mode === 'setup'

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (setup && password !== repeat) {
      setError('Die Passwörter stimmen nicht überein.')
      return
    }
    setBusy(true)
    try {
      await api.post(setup ? '/auth/setup' : '/auth/login', { username, password })
      await queryClient.invalidateQueries({ queryKey: ['auth'] })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <Wallet className="size-6" />
          </div>
          <CardTitle className="text-xl">{setup ? 'Willkommen' : 'Anmelden'}</CardTitle>
          <CardDescription>
            {setup
              ? 'Lege dein Konto an. Deine Daten bleiben ausschließlich auf diesem Rechner.'
              : 'Dein persönlicher Finanzmanager.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Benutzername</Label>
              <Input
                id="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={setup ? 3 : 1}
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Passwort</Label>
              <Input
                id="password"
                type="password"
                autoComplete={setup ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={setup ? 10 : 1}
              />
              {setup && <p className="text-xs text-muted-foreground">Mindestens 10 Zeichen.</p>}
            </div>
            {setup && (
              <div className="space-y-1.5">
                <Label htmlFor="repeat">Passwort wiederholen</Label>
                <Input
                  id="repeat"
                  type="password"
                  autoComplete="new-password"
                  value={repeat}
                  onChange={(e) => setRepeat(e.target.value)}
                  required
                />
              </div>
            )}
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              <Lock /> {busy ? 'Bitte warten …' : setup ? 'Konto anlegen' : 'Anmelden'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
