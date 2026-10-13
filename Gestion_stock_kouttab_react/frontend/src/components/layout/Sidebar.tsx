import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  ReceiptText,
  FileText,
  Shield,
  Database,
  User,
  Beer,
  CalendarDays,
  LifeBuoy,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { usePendingSummary } from '@/api/endpoints/notifications';
import { ACTIONS } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { fr } from '@/lib/i18n/fr';
import { Logo } from '@/components/shared/Logo';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  /**
   * Repliée en rail d'icônes (desktop seulement).
   *
   * Un rail, et non une disparition : masquer complètement la navigation
   * obligerait à un bouton flottant, donc un geste de plus pour changer de
   * page. Le tiroir mobile (`open`) n'est pas concerné.
   */
  repliee?: boolean;
}

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  visible: boolean;
  /** Dossiers en attente sur cette page. 0 ou absent : aucune pastille. */
  badge?: number;
}

export function Sidebar({ open, onClose, repliee = false }: SidebarProps) {
  const { can } = useAuth();
  // Compteurs déjà filtrés par les droits côté serveur : inutile de les
  // recouper ici, un rôle sans droit reçoit des zéros.
  const { data: aTraiter } = usePendingSummary();

  const items: NavItem[] = [
    {
      to: '/dashboard',
      label: fr.nav.dashboard,
      icon: LayoutDashboard,
      visible: can(ACTIONS.DASHBOARD_VIEW),
    },
    { to: '/stock', label: fr.nav.stock, icon: Package, visible: can(ACTIONS.STOCK_VIEW) },
    { to: '/buvette', label: fr.nav.buvette, icon: Beer, visible: can(ACTIONS.BUVETTE_VIEW) },
    {
      to: '/calendar',
      label: fr.nav.calendar,
      icon: CalendarDays,
      visible: can(ACTIONS.CALENDAR_VIEW),
    },
    {
      to: '/expenses',
      label: fr.nav.expenses,
      icon: ReceiptText,
      visible: can(ACTIONS.EXPENSES_SUBMIT),
      // Deux publics, une pastille : ce que la comptabilité doit traiter, et
      // ce sur quoi elle s'est prononcée pour moi. L'un des deux vaut
      // toujours 0 selon le rôle, sauf pour la comptabilité elle-même — qui
      // dépose aussi ses propres notes.
      badge: (aTraiter?.notes_a_valider ?? 0) + (aTraiter?.notes_suivies ?? 0),
    },
    {
      to: '/invoices/upload',
      label: 'Déposer une facture',
      icon: FileText,
      visible: can(ACTIONS.INVOICES_SUBMIT),
      // Ce que la comptabilité me réclame : la pastille est sur la page qui
      // sert justement à le lui donner.
      badge: aTraiter?.justificatifs_demandes,
    },
    {
      to: '/invoices',
      label: fr.nav.invoices,
      icon: FileText,
      visible: can(ACTIONS.INVOICES_SUBMIT),
      badge:
        (aTraiter?.factures_a_traiter ?? 0) +
        (aTraiter?.tickets_ouverts ?? 0) +
        (aTraiter?.factures_suivies ?? 0),
    },
    {
      to: '/admin',
      label: fr.nav.admin,
      icon: Shield,
      visible: can(ACTIONS.ADMIN_HUB),
      badge: (aTraiter?.comptes_a_valider ?? 0) + (aTraiter?.modifications_stock ?? 0),
    },
    {
      to: '/admin/database',
      label: fr.nav.database,
      icon: Database,
      visible: can(ACTIONS.ADMIN_DATABASE),
    },
    // Le BenevoleFrais gère son profil dans l'onglet dédié de /expenses.
    { to: '/profile', label: fr.nav.profile, icon: User, visible: can(ACTIONS.PROFILE_VIEW) },
    // Visible de tous : c'est justement la personne sans droits qui a le
    // plus besoin de savoir a qui s'adresser.
    {
      to: '/contact',
      label: fr.nav.contact,
      icon: LifeBuoy,
      visible: can(ACTIONS.CONTACT_VIEW),
      // Les deux côtés du fil sur une seule pastille : ce que l'équipe doit
      // traiter, et les réponses que je n'ai pas encore lues. L'un des deux
      // vaut toujours 0 pour un bénévole.
      badge: (aTraiter?.conversations_a_traiter ?? 0) + (aTraiter?.conversations_non_lues ?? 0),
    },
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
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-forest-700 bg-forest text-cream-100 transition-transform lg:static lg:translate-x-0 lg:transition-[width] motion-reduce:transition-none',
          open ? 'translate-x-0' : '-translate-x-full',
          repliee && 'lg:w-16',
        )}
      >
        <div
          className={cn(
            'flex items-center justify-between border-b border-forest-700 py-4',
            repliee ? 'px-3 lg:justify-center' : 'px-5',
          )}
        >
          <div className="flex items-center gap-2">
            <Logo className="h-9 w-9 flex-shrink-0 rounded-md shadow-sm" />
            <div className={cn(repliee && 'lg:hidden')}>
              <p className="font-serif text-base font-bold leading-tight text-cream-50">
                Le Kouttâb
              </p>
              <p className="text-xs text-cream-200/80">Gestion</p>
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
                      // Le libellé disparaît du rail : `title` donne l'indice
                      // au survol, `aria-label` garde le nom accessible.
                      title={item.label}
                      aria-label={item.label}
                      className={({ isActive }) =>
                        cn(
                          'relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                          repliee && 'lg:justify-center lg:gap-0 lg:px-2',
                          isActive
                            ? 'bg-terracotta text-cream-50 shadow-sm'
                            : 'text-cream-100/90 hover:bg-forest-700 hover:text-cream-50',
                        )
                      }
                    >
                      <Icon className="h-4 w-4 flex-shrink-0" />
                      <span className={cn('flex-1', repliee && 'lg:hidden')}>{item.label}</span>
                      {/* Pastille de comptage : elle dit combien de dossiers
                          attendent, sans avoir à ouvrir la page. Masquée à 0
                          plutôt qu'affichée vide, pour que sa seule présence
                          signifie « il y a quelque chose à faire ». */}
                      {Boolean(item.badge) && (
                        <>
                          <span
                            aria-label={`${item.badge} ${fr.notifications.aTraiter}`}
                            className={cn(
                              'ml-auto min-w-[1.25rem] rounded-full bg-terracotta px-1.5 py-0.5 text-center text-[11px] font-semibold leading-none text-cream-50 shadow-sm',
                              repliee && 'lg:hidden',
                            )}
                          >
                            {item.badge}
                          </span>
                          {/* En rail, un point suffit à l'œil — mais le compte
                              doit rester lisible par un lecteur d'écran. */}
                          {repliee && (
                            <span
                              aria-hidden
                              className="absolute right-1.5 top-1.5 hidden h-2 w-2 rounded-full bg-terracotta lg:block"
                            />
                          )}
                        </>
                      )}
                    </NavLink>
                  </li>
                );
              })}
          </ul>
        </nav>

        <div
          className={cn(
            'border-t border-forest-700 py-3 text-xs text-cream-200/70',
            repliee ? 'px-2 text-center lg:text-[10px]' : 'px-5',
          )}
        >
          <p>{repliee ? 'v1.0' : 'Version 1.0.0'}</p>
        </div>
      </aside>
    </>
  );
}
