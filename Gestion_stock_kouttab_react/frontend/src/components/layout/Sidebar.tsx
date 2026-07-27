import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  ReceiptText,
  FileText,
  Shield,
  Database,
  CheckSquare,
  User,
  Beer,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { fr } from '@/lib/i18n/fr';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  visible: boolean;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { can } = useAuth();

  const items: NavItem[] = [
    { to: '/dashboard', label: fr.nav.dashboard, icon: LayoutDashboard, visible: can(ACTIONS.DASHBOARD_VIEW) },
    { to: '/stock', label: fr.nav.stock, icon: Package, visible: can(ACTIONS.STOCK_VIEW) },
    { to: '/buvette', label: fr.nav.buvette, icon: Beer, visible: can(ACTIONS.BUVETTE_VIEW) },
    {
      to: '/expenses',
      label: fr.nav.expenses,
      icon: ReceiptText,
      visible: can(ACTIONS.EXPENSES_SUBMIT),
    },
    {
      to: '/expenses/validate',
      label: 'Valider notes de frais',
      icon: CheckSquare,
      visible: can(ACTIONS.EXPENSES_VALIDATE),
    },
    {
      to: '/invoices/upload',
      label: 'Déposer une facture',
      icon: FileText,
      visible: can(ACTIONS.INVOICES_SUBMIT),
    },
    {
      to: '/invoices',
      label: fr.nav.invoices,
      icon: FileText,
      visible: can(ACTIONS.INVOICES_SUBMIT),
    },
    {
      to: '/admin',
      label: fr.nav.admin,
      icon: Shield,
      visible: can(ACTIONS.ADMIN_HUB),
    },
    {
      to: '/admin/database',
      label: fr.nav.database,
      icon: Database,
      visible: can(ACTIONS.ADMIN_DATABASE),
    },
    { to: '/profile', label: fr.nav.profile, icon: User, visible: true },
  ];

  return (
    <>
      {/* Backdrop mobile */}
      {open && (
        <button
          aria-label="Fermer le menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-forest-700 bg-forest text-cream-100 transition-transform lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between border-b border-forest-700 px-5 py-4">
          <div className="flex items-center gap-2">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-md bg-terracotta font-serif text-lg font-bold text-cream-50 shadow-sm"
              aria-hidden
            >
              K
            </span>
            <div>
              <p className="font-serif text-base font-bold leading-tight text-cream-50">
                Le Kouttâb
              </p>
              <p className="text-xs text-cream-200/80">Gestion de stock</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-cream-100 hover:bg-forest-700 hover:text-cream-50 lg:hidden"
            aria-label="Fermer"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
          <ul className="space-y-1">
            {items
              .filter((item) => item.visible)
              .map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/dashboard'}
                      onClick={onClose}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                          isActive
                            ? 'bg-terracotta text-cream-50 shadow-sm'
                            : 'text-cream-100/90 hover:bg-forest-700 hover:text-cream-50',
                        )
                      }
                    >
                      <Icon className="h-4 w-4 flex-shrink-0" />
                      <span>{item.label}</span>
                    </NavLink>
                  </li>
                );
              })}
          </ul>
        </nav>

        <div className="border-t border-forest-700 px-5 py-3 text-xs text-cream-200/70">
          <p>Version 1.0.0</p>
        </div>
      </aside>
    </>
  );
}
