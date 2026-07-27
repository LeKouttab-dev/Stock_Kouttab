import type { Role } from './constants';

/**
 * Matrice de permissions de l'application.
 * Synchronisée avec CLAUDE.md §5.
 */
export const ACTIONS = {
  DASHBOARD_VIEW: 'dashboard:view',
  STOCK_VIEW: 'stock:view',
  STOCK_REQUEST_MOD: 'stock:request_mod',
  STOCK_DIRECT_MOD: 'stock:direct_mod',
  STOCK_APPROVE_MODS: 'stock:approve_mods',
  STOCK_CRUD: 'stock:crud',
  EXPENSES_SUBMIT: 'expenses:submit',
  EXPENSES_VALIDATE: 'expenses:validate',
  EXPENSES_VIEW_RIB: 'expenses:view_rib',
  INVOICES_SUBMIT: 'invoices:submit',
  INVOICES_CHANGE_STATUS: 'invoices:change_status',
  ADMIN_VALIDATE_USERS: 'admin:validate_users',
  ADMIN_MANAGE_USERS: 'admin:manage_users',
  ADMIN_INVITATIONS: 'admin:invitations',
  ADMIN_DATABASE: 'admin:database',
  ADMIN_IMPORT_CSV: 'admin:import_csv',
  ADMIN_HUB: 'admin:hub',
  BUVETTE_VIEW: 'buvette:view',
  BUVETTE_SYNC: 'buvette:sync',
  BUVETTE_CRUD: 'buvette:crud',
  BUVETTE_WEBHOOK: 'buvette:webhook',
  POLES_MANAGE: 'poles:manage',
  EVENTS_MANAGE: 'events:manage',
  COMPTA_RESEND_EMAIL: 'compta:resend_email',
} as const;

export type Action = (typeof ACTIONS)[keyof typeof ACTIONS];

const PERMISSIONS: Record<Action, Role[]> = {
  [ACTIONS.DASHBOARD_VIEW]: ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'],
  [ACTIONS.STOCK_VIEW]: ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'],
  [ACTIONS.STOCK_REQUEST_MOD]: ['Benevole'],
  [ACTIONS.STOCK_DIRECT_MOD]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.STOCK_APPROVE_MODS]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.STOCK_CRUD]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.EXPENSES_SUBMIT]: ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'],
  [ACTIONS.EXPENSES_VALIDATE]: ['Super Admin', 'Compta'],
  [ACTIONS.EXPENSES_VIEW_RIB]: ['Super Admin', 'Compta'],
  [ACTIONS.INVOICES_SUBMIT]: ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'],
  [ACTIONS.INVOICES_CHANGE_STATUS]: ['Super Admin', 'Compta'],
  [ACTIONS.ADMIN_VALIDATE_USERS]: ['Super Admin'],
  [ACTIONS.ADMIN_MANAGE_USERS]: ['Super Admin'],
  [ACTIONS.ADMIN_INVITATIONS]: ['Super Admin'],
  [ACTIONS.ADMIN_DATABASE]: ['Super Admin'],
  [ACTIONS.ADMIN_IMPORT_CSV]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.ADMIN_HUB]: ['Super Admin', 'AdminBenevoles', 'Compta'],
  [ACTIONS.BUVETTE_VIEW]: ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'],
  [ACTIONS.BUVETTE_SYNC]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.BUVETTE_CRUD]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.BUVETTE_WEBHOOK]: ['Super Admin'],
  // Doivent refléter exactement les dépendances de rôle côté serveur :
  // _POLE_ADMIN_ROLES et _EVENT_ADMIN_ROLES dans les endpoints correspondants.
  [ACTIONS.POLES_MANAGE]: ['Super Admin'],
  [ACTIONS.EVENTS_MANAGE]: ['Super Admin', 'AdminBenevoles'],
  [ACTIONS.COMPTA_RESEND_EMAIL]: ['Super Admin', 'Compta'],
};

export function canAccess(role: Role | null | undefined, action: Action): boolean {
  if (!role) return false;
  return PERMISSIONS[action]?.includes(role) ?? false;
}

export function hasAnyRole(role: Role | null | undefined, allowed: Role[]): boolean {
  if (!role) return false;
  return allowed.includes(role);
}
