import { Suspense, lazy, type ComponentType } from 'react';
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
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';

/**
 * Charge un écran à la demande.
 *
 * `lazy` attend un export `default` ; nos pages sont exportées nommément.
 * L'adaptateur est écrit une fois ici plutôt que recopié à chaque route.
 */
function lazyNamed<K extends string>(loader: () => Promise<{ [P in K]: ComponentType }>, name: K) {
  return lazy(() => loader().then((m) => ({ default: m[name] })));
}

// Le reste est chargé à la demande. Le `<Suspense>` ci-dessous existait déjà
// mais ne servait à rien, tous les imports étant statiques : l'application
// livrait un unique bundle de ~1,5 Mo, dont le scanner de codes-barres et les
// graphiques, que la plupart des utilisateurs n'ouvrent jamais.
const DashboardPage = lazyNamed(() => import('@/pages/dashboard/DashboardPage'), 'DashboardPage');
const StockCategoriesPage = lazyNamed(
  () => import('@/pages/stock/StockCategoriesPage'),
  'StockCategoriesPage',
);
const StockSubCategoriesPage = lazyNamed(
  () => import('@/pages/stock/StockSubCategoriesPage'),
  'StockSubCategoriesPage',
);
const StockItemsPage = lazyNamed(() => import('@/pages/stock/StockItemsPage'), 'StockItemsPage');
const MyExpensesPage = lazyNamed(() => import('@/pages/expenses/MyExpensesPage'), 'MyExpensesPage');
const InvoiceUploadPage = lazyNamed(
  () => import('@/pages/invoices/InvoiceUploadPage'),
  'InvoiceUploadPage',
);
const InvoiceListPage = lazyNamed(
  () => import('@/pages/invoices/InvoiceListPage'),
  'InvoiceListPage',
);
const BuvettePage = lazyNamed(() => import('@/pages/buvette/BuvettePage'), 'BuvettePage');
const BuvetteSalesPage = lazyNamed(
  () => import('@/pages/buvette/BuvetteSalesPage'),
  'BuvetteSalesPage',
);
const AdminPage = lazyNamed(() => import('@/pages/admin/AdminPage'), 'AdminPage');
const DatabaseManagementPage = lazyNamed(
  () => import('@/pages/admin/DatabaseManagementPage'),
  'DatabaseManagementPage',
);
const ProfilePage = lazyNamed(() => import('@/pages/ProfilePage'), 'ProfilePage');
const NotFoundPage = lazyNamed(() => import('@/pages/NotFoundPage'), 'NotFoundPage');

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
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

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
                {/* La validation a rejoint « Notes de frais » sous forme
                    d'onglet. L'ancienne adresse reste valide : des signets et
                    des liens de courriels la visent encore. */}
                <Route
                  path="/expenses/validate"
                  element={<Navigate to="/expenses#valider" replace />}
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
