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
import { SsoExchangePage } from '@/pages/auth/SsoExchangePage';

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
const ContactPage = lazyNamed(() => import('@/pages/contact/ContactPage'), 'ContactPage');
const NotFoundPage = lazyNamed(() => import('@/pages/NotFoundPage'), 'NotFoundPage');

import { ACTIONS , pageParDefaut } from '@/lib/auth';
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
  const { user, isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? pageParDefaut(user?.role) : '/login'} replace />;
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
              {/* Passage signé depuis gestion.lekouttab.fr (jeton en fragment #). */}
              <Route path="/sso" element={<SsoExchangePage />} />

              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={
                  <ProtectedRoute requiredAction={ACTIONS.DASHBOARD_VIEW}><DashboardPage /></ProtectedRoute>
                } />

                <Route path="/stock" element={
                  <ProtectedRoute requiredAction={ACTIONS.STOCK_VIEW}><StockCategoriesPage /></ProtectedRoute>
                } />
                <Route path="/stock/:category" element={
                  <ProtectedRoute requiredAction={ACTIONS.STOCK_VIEW}><StockSubCategoriesPage /></ProtectedRoute>
                } />
                <Route path="/stock/:category/:subcategory" element={
                  <ProtectedRoute requiredAction={ACTIONS.STOCK_VIEW}><StockItemsPage /></ProtectedRoute>
                } />

                <Route path="/expenses" element={
                  <ProtectedRoute requiredAction={ACTIONS.EXPENSES_SUBMIT}><MyExpensesPage /></ProtectedRoute>
                } />
                {/* La validation a rejoint « Notes de frais » sous forme
                    d'onglet. L'ancienne adresse reste valide : des signets et
                    des liens de courriels la visent encore. */}
                <Route
                  path="/expenses/validate"
                  element={<Navigate to="/expenses#valider" replace />}
                />

                <Route path="/invoices/upload" element={
                  <ProtectedRoute requiredAction={ACTIONS.INVOICES_SUBMIT}><InvoiceUploadPage /></ProtectedRoute>
                } />
                <Route path="/invoices" element={
                  <ProtectedRoute requiredAction={ACTIONS.INVOICES_SUBMIT}><InvoiceListPage /></ProtectedRoute>
                } />

                <Route path="/buvette" element={
                  <ProtectedRoute requiredAction={ACTIONS.BUVETTE_VIEW}><BuvettePage /></ProtectedRoute>
                } />
                <Route path="/buvette/sales" element={
                  <ProtectedRoute requiredAction={ACTIONS.BUVETTE_VIEW}><BuvetteSalesPage /></ProtectedRoute>
                } />

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

                <Route path="/profile" element={
                  <ProtectedRoute requiredAction={ACTIONS.PROFILE_VIEW}><ProfilePage /></ProtectedRoute>
                } />
                <Route path="/contact" element={
                  <ProtectedRoute requiredAction={ACTIONS.CONTACT_VIEW}><ContactPage /></ProtectedRoute>
                } />
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
