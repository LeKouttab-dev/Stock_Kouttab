import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Toaster } from '@/components/ui/toast';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';

// Les écrans d'authentification restent en import direct : ce sont les
// premiers affichés, les charger en différé ajouterait un aller-retour réseau
// avant même l'écran de connexion.
import { LoginPage } from '@/pages/auth/LoginPage';
import { SignupPage } from '@/pages/auth/SignupPage';
import { AdminSetupPage } from '@/pages/auth/AdminSetupPage';

// Le reste est chargé à la demande. Le `<Suspense>` ci-dessous existait déjà
// mais ne servait à rien, tous les imports étant statiques : l'application
// livrait un unique bundle de ~1,5 Mo, dont le scanner de codes-barres et les
// graphiques, que la plupart des utilisateurs n'ouvrent jamais.
const DashboardPage = lazy(() =>
  import('@/pages/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const StockCategoriesPage = lazy(() =>
  import('@/pages/stock/StockCategoriesPage').then((m) => ({
    default: m.StockCategoriesPage,
  })),
);
const StockSubCategoriesPage = lazy(() =>
  import('@/pages/stock/StockSubCategoriesPage').then((m) => ({
    default: m.StockSubCategoriesPage,
  })),
);
const StockItemsPage = lazy(() =>
  import('@/pages/stock/StockItemsPage').then((m) => ({ default: m.StockItemsPage })),
);
const MyExpensesPage = lazy(() =>
  import('@/pages/expenses/MyExpensesPage').then((m) => ({ default: m.MyExpensesPage })),
);
const ValidateExpensesPage = lazy(() =>
  import('@/pages/expenses/ValidateExpensesPage').then((m) => ({
    default: m.ValidateExpensesPage,
  })),
);
const InvoiceUploadPage = lazy(() =>
  import('@/pages/invoices/InvoiceUploadPage').then((m) => ({
    default: m.InvoiceUploadPage,
  })),
);
const InvoiceListPage = lazy(() =>
  import('@/pages/invoices/InvoiceListPage').then((m) => ({ default: m.InvoiceListPage })),
);
const BuvettePage = lazy(() =>
  import('@/pages/buvette/BuvettePage').then((m) => ({ default: m.BuvettePage })),
);
const BuvetteSalesPage = lazy(() =>
  import('@/pages/buvette/BuvetteSalesPage').then((m) => ({ default: m.BuvetteSalesPage })),
);
const AdminPage = lazy(() =>
  import('@/pages/admin/AdminPage').then((m) => ({ default: m.AdminPage })),
);
const DatabaseManagementPage = lazy(() =>
  import('@/pages/admin/DatabaseManagementPage').then((m) => ({
    default: m.DatabaseManagementPage,
  })),
);
const ProfilePage = lazy(() =>
  import('@/pages/ProfilePage').then((m) => ({ default: m.ProfilePage })),
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
);

import { ACTIONS } from '@/lib/auth';
import { useAuth } from '@/hooks/useAuth';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 60_000,
    },
    mutations: {
      retry: 0,
    },
  },
});

function RootRedirect() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <Suspense fallback={<LoadingSpinner fullPage />}>
            <Routes>
              <Route path="/" element={<RootRedirect />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/admin-setup" element={<AdminSetupPage />} />

              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<DashboardPage />} />

                <Route path="/stock" element={<StockCategoriesPage />} />
                <Route path="/stock/:category" element={<StockSubCategoriesPage />} />
                <Route path="/stock/:category/:subcategory" element={<StockItemsPage />} />

                <Route path="/expenses" element={<MyExpensesPage />} />
                <Route
                  path="/expenses/validate"
                  element={
                    <ProtectedRoute requiredAction={ACTIONS.EXPENSES_VALIDATE}>
                      <ValidateExpensesPage />
                    </ProtectedRoute>
                  }
                />

                <Route path="/invoices/upload" element={<InvoiceUploadPage />} />
                <Route path="/invoices" element={<InvoiceListPage />} />

                <Route path="/buvette" element={<BuvettePage />} />
                <Route path="/buvette/sales" element={<BuvetteSalesPage />} />

                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute requiredAction={ACTIONS.ADMIN_HUB}>
                      <AdminPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/database"
                  element={
                    <ProtectedRoute requiredAction={ACTIONS.ADMIN_DATABASE}>
                      <DatabaseManagementPage />
                    </ProtectedRoute>
                  }
                />

                <Route path="/profile" element={<ProfilePage />} />
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
