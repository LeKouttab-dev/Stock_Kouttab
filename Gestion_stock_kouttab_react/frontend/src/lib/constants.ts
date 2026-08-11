export const ROLES = ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'] as const;
export type Role = (typeof ROLES)[number];

export const VALIDATION_STATUS = ['pending', 'active', 'rejected'] as const;
export type ValidationStatus = (typeof VALIDATION_STATUS)[number];

export const EXPENSE_STATUS = ['En attente', 'Approuvée', 'Refusée', 'Remboursée'] as const;
export type ExpenseStatus = (typeof EXPENSE_STATUS)[number];

export const INVOICE_STATUS = [
  'En attente',
  'En cours de traitement',
  'Validée',
  'Refusée',
] as const;
export type InvoiceStatus = (typeof INVOICE_STATUS)[number];

export const STOCK_MOD_STATUS = ['En attente', 'Approuvée', 'Refusée'] as const;
export type StockModStatus = (typeof STOCK_MOD_STATUS)[number];

/** Icônes par défaut pour les catégories de stock (fallback : 📦). */
export const ICONS: Record<string, string> = {
  Nourriture: '🍔',
  Fournitures: '📝',
  Intendance: '🧼',
  Bibliothèque: '📚',
  Hygiène: '🧻',
  Entretien: '🧹',
  Bureau: '🖊️',
  Informatique: '💻',
  Sécurité: '🔒',
  Transport: '🚗',
  Communication: '📞',
  Événementiel: '🎉',
};

export const EMOJI_OPTIONS = [
  '📦',
  '🍔',
  '🧃',
  '📚',
  '🧻',
  '🧼',
  '📝',
  '🖊️',
  '🍪',
  '💧',
  '🧴',
  '🧹',
  '🪑',
  '🥤',
  '🍎',
  '📒',
  '🥖',
  '🍝',
  '🥛',
  '🥫',
  '🧂',
  '🧊',
  '🧷',
  '🪒',
  '🪥',
  '📋',
  '📁',
  '📎',
  '✂️',
  '📐',
];

export const ROLE_LABELS: Record<Role, string> = {
  'Super Admin': 'Super Admin',
  AdminBenevoles: 'Admin Bénévoles',
  Compta: 'Comptabilité',
  Benevole: 'Bénévole',
};

/**
 * Couleurs des rôles — palette charte "Le Kouttâb" :
 *  Super Admin     → terracotta (autorité, primaire)
 *  AdminBenevoles  → forest (vert profond, gestionnaire)
 *  Compta          → sage (vert clair, "validation")
 *  Benevole        → sand (beige, neutre chaleureux)
 */
export const ROLE_COLORS: Record<Role, string> = {
  'Super Admin': 'bg-terracotta-100 text-terracotta-800 border-terracotta-200',
  AdminBenevoles: 'bg-forest-100 text-forest-800 border-forest-200',
  Compta: 'bg-sage-200 text-forest-800 border-sage-300',
  Benevole: 'bg-sand-100 text-sand-800 border-sand-200',
};

/**
 * Couleurs des statuts — adaptées à la charte :
 *  En attente / pending             → sand (beige neutre = patience)
 *  Approuvée / Validée / active     → sage (vert clair "OK")
 *  Refusée / rejected               → rouge destructive (universel)
 *  Remboursée / Traitée             → forest (vert profond, "fini")
 *  En cours de traitement           → terracotta (action en cours)
 */
export const STATUS_COLORS: Record<string, string> = {
  'En attente': 'bg-sand-100 text-sand-800 border-sand-200',
  Approuvée: 'bg-sage-200 text-forest-800 border-sage-300',
  Refusée: 'bg-red-100 text-red-800 border-red-200',
  Remboursée: 'bg-forest-100 text-forest-800 border-forest-200',
  'En cours de traitement': 'bg-terracotta-100 text-terracotta-800 border-terracotta-200',
  Validée: 'bg-sage-200 text-forest-800 border-sage-300',
  active: 'bg-sage-200 text-forest-800 border-sage-300',
  pending: 'bg-sand-100 text-sand-800 border-sand-200',
  rejected: 'bg-red-100 text-red-800 border-red-200',
};

export const STATUS_EMOJIS: Record<string, string> = {
  'En attente': '🟡',
  Approuvée: '🟢',
  Refusée: '🔴',
  Remboursée: '🔵',
  'En cours de traitement': '🔵',
  Validée: '🟢',
};
