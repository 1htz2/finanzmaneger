import {
  ArrowLeftRight,
  BarChart3,
  Banknote,
  Building2,
  Gem,
  HandCoins,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PiggyBank,
  Plus,
  Settings,
  ShieldCheck,
  Sun,
  SunMoon,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useTheme } from 'next-themes'
import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router'

import { useActions } from '@/components/Actions'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { api } from '@/lib/api'
import { queryClient, useAuthStatus } from '@/lib/queries'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transaktionen', label: 'Transaktionen', icon: ArrowLeftRight },
  { to: '/budget', label: 'Budget', icon: Wallet },
  { to: '/fixkosten', label: 'Fixkosten', icon: Building2 },
  { to: '/reserve', label: 'Reserve', icon: ShieldCheck },
  { to: '/vermoegen', label: 'Vermögen', icon: Gem },
  { to: '/sparziele', label: 'Sparziele', icon: PiggyBank },
  { to: '/schulden', label: 'Schulden', icon: HandCoins },
  { to: '/statistiken', label: 'Statistiken', icon: BarChart3 },
  { to: '/einstellungen', label: 'Einstellungen', icon: Settings },
]

const MOBILE_PRIMARY = ['/', '/transaktionen', '/budget']

async function logout() {
  await api.post('/auth/logout').catch(() => undefined)
  queryClient.clear()
  await queryClient.invalidateQueries({ queryKey: ['auth'] })
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme()
  const { data } = useAuthStatus()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Darstellung und Konto">
          {theme === 'dark' ? <Moon /> : theme === 'light' ? <Sun /> : <SunMoon />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Darstellung</DropdownMenuLabel>
        <DropdownMenuItem onClick={() => setTheme('light')}>
          <Sun /> Hell
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('dark')}>
          <Moon /> Dunkel
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('system')}>
          <SunMoon /> System
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="font-normal text-muted-foreground">
          Angemeldet als {data?.username}
        </DropdownMenuLabel>
        <DropdownMenuItem onClick={logout}>
          <LogOut /> Abmelden
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function SideNav() {
  return (
    <nav className="flex flex-col gap-1" aria-label="Hauptnavigation">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
              isActive && 'bg-muted text-foreground',
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Wallet className="size-4" />
      </span>
      FinanzManager
    </div>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const { addTransaction, recordSalary } = useActions()
  const [moreOpen, setMoreOpen] = useState(false)
  const location = useLocation()
  const inMore = !MOBILE_PRIMARY.includes(location.pathname)

  return (
    <div className="min-h-dvh">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r bg-card px-3 py-5 lg:flex">
        <div className="px-3">
          <Brand />
        </div>
        <div className="mt-6 flex flex-col gap-2 px-1">
          <Button onClick={() => addTransaction()} className="justify-start" size="lg">
            <Plus /> Ausgabe erfassen
          </Button>
          <Button onClick={recordSalary} variant="outline" className="justify-start" size="lg">
            <Banknote /> Gehalt erfassen
          </Button>
        </div>
        <div className="mt-6 flex-1">
          <SideNav />
        </div>
        <p className="px-3 text-xs text-muted-foreground">Lokal gespeichert · keine Cloud</p>
      </aside>

      <div className="lg:pl-60">
      <header className="pt-safe sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-2 px-4 sm:px-6">
          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" onClick={recordSalary} className="lg:hidden">
              <Banknote /> Gehalt
            </Button>
            <ThemeMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-6 pb-28 sm:px-6 lg:pb-12">{children}</main>
      </div>

      <nav
        className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 backdrop-blur lg:hidden"
        aria-label="Mobile Navigation"
      >
        <div className="mx-auto grid h-16 max-w-md grid-cols-5 items-center">
          {NAV.filter((n) => MOBILE_PRIMARY.includes(n.to))
            .slice(0, 2)
            .map((n) => (
              <MobileTab key={n.to} item={n} />
            ))}
          <div className="flex justify-center">
            <Button
              size="icon-lg"
              className="size-12 rounded-full shadow-lg"
              onClick={() => addTransaction()}
              aria-label="Ausgabe erfassen"
            >
              <Plus className="size-6" />
            </Button>
          </div>
          <MobileTab item={NAV[2]!} />
          <button
            type="button"
            onClick={() => setMoreOpen(true)}
            className={cn(
              'flex h-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-muted-foreground',
              inMore && 'text-foreground',
            )}
          >
            <Menu className="size-5" />
            Mehr
          </button>
        </div>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="pb-safe rounded-t-2xl">
          <SheetHeader>
            <SheetTitle>Bereiche</SheetTitle>
          </SheetHeader>
          <div className="grid grid-cols-3 gap-2 px-4 pb-6">
            {NAV.filter((n) => !MOBILE_PRIMARY.includes(n.to)).map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMoreOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col items-center gap-2 rounded-xl border p-4 text-xs font-medium',
                    isActive && 'border-foreground/30 bg-muted',
                  )
                }
              >
                <Icon className="size-5" />
                {label}
              </NavLink>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

function MobileTab({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex h-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-muted-foreground',
          isActive && 'text-foreground',
        )
      }
    >
      <Icon className="size-5" />
      {item.label === 'Transaktionen' ? 'Buchungen' : item.label}
    </NavLink>
  )
}
