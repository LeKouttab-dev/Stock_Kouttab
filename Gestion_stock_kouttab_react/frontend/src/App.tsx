import { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Toaster } from '@/components/ui/toast';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';

import { LoginPage } from '@/pages/auth/LoginPage';
import { SignupPage } from '@/pages/auth/SignupPage';
import { AdminSetupPage } from '@/pages/auth/AdminSetupPage';

import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { StockCategoriesPage } from '@/pages/stock/StockCategoriesPage';
import { StockSubCategoriesPage } from '@/pages/stock/StockSubCategoriesPage';
import { StockItemsPage } from '@/pages/stock/StockItemsPage';
import { MyExpensesPage } from '@/pages/expenses/MyExpensesPage';
import { ValidateExpensesPage } from '@/pages/expenses/ValidateExpensesPage';
import { InvoiceUploadPage } from '@/pages/invoices/InvoiceUploadPage';
import { InvoiceListPage } from '@/pages/invoices/InvoiceListPage';
import { BuvettePage } from '@/pages/buvette/BuvettePage';
import { BuvetteSalesPage } from '@/pages/buvette/BuvetteSalesPage';
import { AdminPage } from '@/pages/admin/AdminPage';
import { DatabaseManagementPage } from '@/pages/admin/DatabaseManagementPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
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
              <Route
                path="/stock/:category/:subcategory"
                element={<StockItemsPage />}
              />

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
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
