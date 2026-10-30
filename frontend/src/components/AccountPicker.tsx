import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { accountColor } from '@/lib/accounts'
import { formatEur } from '@/lib/format'
import { useWealth } from '@/lib/queries'

export const NO_ACCOUNT = 'none'

/** Optional choice of where savings money comes from or goes to. Hidden without accounts. */
export function AccountPicker({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
}) {
  const wealth = useWealth()
  const accounts = (wealth.data?.accounts ?? []).filter((a) => !a.archived)
  if (accounts.length === 0) return null
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_ACCOUNT}>Ohne Anlageort · {formatEur(wealth.data?.unassigned_cents ?? 0)}</SelectItem>
          {accounts.map((a) => (
            <SelectItem key={a.id} value={String(a.id)}>
              <span className="size-2 rounded-full" style={{ background: accountColor(a) }} /> {a.name} · {formatEur(a.booked_cents)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function accountIdOrNull(value: string): number | null {
  return value === NO_ACCOUNT ? null : Number(value)
}
