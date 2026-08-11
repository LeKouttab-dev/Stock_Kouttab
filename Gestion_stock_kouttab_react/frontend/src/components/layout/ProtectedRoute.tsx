import { type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { canAccess, type Action } from '@/lib/auth';
import type { Role } from '@/lib/constants';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredAction?: Action;
  requiredRoles?: Role[];
}

export function ProtectedRoute({ children, requiredAction, requiredRoles }: ProtectedRouteProps) {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (!user) {
    return <LoadingSpinner fullPage />;
  }

  if (requiredAction && !canAccess(user.role, requiredAction)) {
    return <Navigate to="/dashboard" replace />;
  }

  if (requiredRoles && !requiredRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
