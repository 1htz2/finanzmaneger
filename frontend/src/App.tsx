import { QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { ActionsProvider } from '@/components/Actions'
import { AppShell } from '@/components/AppShell'
import { ErrorState, LoadingState } from '@/components/common'
import { CorrectionProvider } from '@/components/CorrectionProvider'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { unauthorizedListeners } from '@/lib/api'
import { queryClient, useAuthStatus } from '@/lib/queries'
import { AuthPage } from '@/pages/AuthPage'

const BudgetPage = lazy(() => import('@/pages/BudgetPage').then((m) => ({ default: m.BudgetPage })))
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const FixedCostsPage = lazy(() => import('@/pages/FixedCostsPage').then((m) => ({ default: m.FixedCostsPage })))
const ReservePage = lazy(() => import('@/pages/ReservePage').then((m) => ({ default: m.ReservePage })))
const SavingsPage = lazy(() => import('@/pages/SavingsPage').then((m) => ({ default: m.SavingsPage })))
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const StatsPage = lazy(() => import('@/pages/StatsPage').then((m) => ({ default: m.StatsPage })))
const TransactionsPage = lazy(() => import('@/pages/TransactionsPage').then((m) => ({ default: m.TransactionsPage })))

function Gate() {
  const auth = useAuthStatus()

  useEffect(() => {
    const onUnauthorized = () => void queryClient.invalidateQueries({ queryKey: ['auth'] })
    unauthorizedListeners.add(onUnauthorized)
    return () => {
      unauthorizedListeners.delete(onUnauthorized)
    }
  }, [])

  if (auth.isLoading) {
    return (
      <div className="mx-auto max-w-md p-6">
        <LoadingState rows={2} />
      </div>
    )
  }
  if (auth.error || !auth.data) {
    return (
      <div className="mx-auto max-w-md p-6">
        <ErrorState error={auth.error} onRetry={() => auth.refetch()} />
      </div>
    )
  }
  if (auth.data.setup_required) return <AuthPage mode="setup" />
  if (!auth.data.authenticated) return <AuthPage mode="login" />

  return (
    <CorrectionProvider>
      <ActionsProvider>
        <AppShell>
          <Suspense fallback={<LoadingState rows={3} />}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/transaktionen" element={<TransactionsPage />} />
            <Route path="/budget" element={<BudgetPage />} />
            <Route path="/fixkosten" element={<FixedCostsPage />} />
            <Route path="/reserve" element={<ReservePage />} />
            <Route path="/sparziele" element={<SavingsPage />} />
            <Route path="/statistiken" element={<StatsPage />} />
            <Route path="/einstellungen" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
        </AppShell>
      </ActionsProvider>
    </CorrectionProvider>
  )
}

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <BrowserRouter>
            <Gate />
          </BrowserRouter>
          <Toaster position="top-center" richColors closeButton />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
