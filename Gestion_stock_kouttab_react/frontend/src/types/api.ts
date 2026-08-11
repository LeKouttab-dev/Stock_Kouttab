import type {
  ExpenseStatus,
  InvoiceStatus,
  Role,
  StockModStatus,
  ValidationStatus,
} from '@/lib/constants';

// Re-export : plusieurs modules importent ces types depuis '@/types/api'
// plutot que de connaitre '@/lib/constants'. Sans cette ligne, TypeScript
// remonte TS2459 et le build echoue.
export type { ExpenseStatus, InvoiceStatus, Role, StockModStatus, ValidationStatus };

/* Auth & users */
export interface User {
  id: number;
  username: string;
  role: Role;
  validation_status: ValidationStatus;
  nom: string;
  prenom: string;
  email: string;
  telephone?: string | null;
  rib?: string | null;
  password_must_change?: boolean;
  created_at?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface SignupRequest {
  username: string;
  password: string;
  // Pas de `role` : le serveur crée toujours un compte 'Benevole' et ignore
  // toute valeur envoyée. Un Super Admin promeut ensuite depuis l'administration.
  nom: string;
  prenom: string;
  email: string;
  telephone?: string;
}

export interface AdminSetupRequest {
  token: string;
  email: string;
  username: string;
  password: string;
}

export interface ProfileUpdateRequest {
  nom?: string;
  prenom?: string;
  email?: string;
  telephone?: string;
  rib?: string;
}

/* Stock */
export interface StockItem {
  id: number;
  nom: string;
  categorie: string;
  sous_categorie?: string | null;
  quantite: number;
  seuil_alerte: number;
  emoji?: string | null;
  alert_sent?: boolean;
  // `string | null` quand le backend le renvoie ; absent dans certaines fixtures
  // de test (héritage). Le champ est garanti côté backend.
  barcode?: string | null;
}

export interface StockItemCreate {
  nom: string;
  categorie: string;
  sous_categorie?: string | null;
  quantite: number;
  seuil_alerte: number;
  emoji?: string | null;
  barcode?: string | null;
}

export type StockItemUpdate = Partial<StockItemCreate>;

export interface Category {
  nom: string;
  is_default?: boolean;
}

export interface SubCategory {
  id: number;
  nom_categorie: string;
  nom_sous_categorie: string;
}

export interface StockStatistics {
  total_articles: number;
  total_quantite: number;
  alertes_stock: number;
  stock_epuise: number;
  stats_par_categorie: Array<{ categorie: string; count: number; total: number }>;
  stats_nourriture_sous_categories: Array<{
    sous_categorie: string;
    count: number;
    total: number;
  }>;
  dernieres_modifs: Array<{
    date: string;
    nom: string;
    prenom: string;
    article: string;
    categorie: string;
    status: StockModStatus;
    quantite_demandee: number;
  }>;
}

export interface StockModification {
  id: number;
  id_user: number;
  id_stock: number;
  quantite_actuelle: number;
  quantite_demandee: number;
  status: StockModStatus;
  date_demande: string;
  date_approbation?: string | null;
  approuve_par?: number | null;
  // jointures
  user_nom?: string;
  user_prenom?: string;
  stock_nom?: string;
  categorie?: string;
  sous_categorie?: string | null;
}

/* Expenses */
export interface ExpenseFile {
  id: number;
  id_note_de_frais: number;
  nom_fichier: string;
  chemin?: string;
}

export interface Expense {
  id: number;
  id_user: number;
  user_full_name: string | null;
  user_email?: string | null;
  user_rib?: string | null;
  date_depense: string;
  /** Champ libre historique, remplacé par pôle + événement + date. */
  rattachement?: string | null;
  fournisseur?: string | null;
  nature_charge?: string | null;
  montant: number;
  commentaires?: string | null;
  remboursement_deja_emis: number;
  remise: number;
  status: ExpenseStatus;
  commentaires_compta?: string | null;
  date_soumission?: string;
  // Rattachement comptable, renvoyé par `ExpenseOut` mais absent de ce type
  // jusqu'ici : l'écran de validation ne pouvait donc pas reconstituer le nom
  // du justificatif transmis au comptable. Nullable, les notes antérieures à
  // la mise en place du module ne le portent pas.
  id_pole?: number | null;
  pole?: string | null;
  id_event?: number | null;
  evenement?: string | null;
  date_evenement?: string | null;
  files?: ExpenseFile[];
}

export interface ExpenseCreateRequest {
  date_depense: string;
  fournisseur: string;
  montant: number;
  /* Rattachement comptable : obligatoire, il compose le nom du justificatif
     envoyé au comptable. L'événement accepte un identifiant HelloAsso ou une
     saisie libre — l'un des deux, jamais aucun. Les valeurs nulles ou vides
     sont écartées avant l'envoi du FormData. */
  id_pole: number;
  date_evenement: string;
  id_event?: number | null;
  evenement_libre?: string;
  /** Champ libre historique, plus saisi mais toujours accepté par l'API. */
  rattachement?: string;
  nature_charge?: string;
  commentaires?: string;
  remboursement_deja_emis?: number;
  remise?: number;
}

export interface ExpenseUpdateRequest extends Partial<ExpenseCreateRequest> {}

export interface ExpenseValidateRequest {
  status: ExpenseStatus;
  commentaires_compta?: string;
}

/* Invoices */
export interface InvoiceFile {
  id: number;
  id_facture: number;
  nom_fichier: string;
  chemin?: string;
}

export interface Invoice {
  id: number;
  id_user: number;
  user_full_name: string;
  commentaire?: string | null;
  status: InvoiceStatus;
  date_depot: string;
  files: InvoiceFile[];
  nom?: string;
  prenom?: string;
  /* Rattachement comptable — absent sur les factures antérieures au module. */
  id_pole?: number | null;
  pole?: string | null;
  id_event?: number | null;
  evenement?: string | null;
  date_evenement?: string | null;
  fournisseur?: string | null;
  montant?: string | number | null;
  validated_by?: number | null;
  validated_at?: string | null;
}

/* Référentiels comptables */
export interface Pole {
  id: number;
  nom: string;
  is_default: boolean;
  is_active: boolean;
  ordre: number;
  created_at?: string | null;
}

/**
 * Événement de l'association.
 *
 * ⚠️ Ne PAS nommer ce type `Event` : il entrerait en collision avec le type DOM
 * global du même nom, ce qui produit des erreurs de typage trompeuses.
 */
export interface AppEvent {
  id: number;
  nom: string;
  date_evenement?: string | null;
  date_fin?: string | null;
  url?: string | null;
  source: 'helloasso' | 'manuel';
  is_active: boolean;
  helloasso_state?: string | null;
  last_synced_at?: string | null;
}

export interface EventSyncResult {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export type OutboundEmailStatus = 'pending' | 'sending' | 'sent' | 'failed' | 'abandoned';

export interface OutboundEmail {
  id: number;
  kind: string;
  entity_type: string;
  entity_id: number;
  subject: string;
  status: OutboundEmailStatus;
  attempts: number;
  max_attempts: number;
  last_error?: string | null;
  next_retry_at?: string | null;
  sent_at?: string | null;
  created_at?: string | null;
  recipient_list: string[];
  attachment_names: string[];
}

/* Invitations */
export interface AdminInvitation {
  id: number;
  email: string;
  expires_at: string;
  used: boolean;
  used_at?: string | null;
  attempts: number;
  created_at: string;
}

export interface CreateInvitationRequest {
  email: string;
}

/* Admin / DB */
export interface DatabaseStatus {
  ok: boolean;
  tables: Array<{ name: string; rows: number; size_kb?: number }>;
  total_rows: number;
}

export interface CsvImportRequest {
  file: File;
  skiprows?: number;
}

export interface CsvImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface ApiError {
  detail: string | Record<string, unknown>;
  status?: number;
}

/* Buvette (HelloAsso) */
export interface BuvetteProduct {
  id: number;
  helloasso_tier_id: number | null;
  name: string;
  description: string | null;
  price_cents: number;
  quantity: number;
  seuil_alerte: number;
  emoji: string;
  image_url: string | null;
  is_active: boolean;
  alert_sent: boolean;
  last_synced_at: string | null;
  low_stock: boolean;
  // `string | null` quand le backend le renvoie ; absent dans certaines fixtures
  // de test. Le champ est garanti côté backend.
  barcode?: string | null;
}

export interface BuvetteProductUpdate {
  quantity?: number;
  seuil_alerte?: number;
  emoji?: string;
  is_active?: boolean;
  name?: string;
  description?: string | null;
  price_cents?: number;
  barcode?: string | null;
}

export interface BuvetteProductCreate {
  name: string;
  price_cents: number;
  quantity?: number;
  seuil_alerte?: number;
  emoji?: string;
  helloasso_tier_id?: number | null;
  barcode?: string | null;
}

export interface BuvetteSale {
  id: number;
  product_name_snapshot: string;
  quantity_sold: number;
  amount_cents: number;
  customer_first_name: string | null;
  customer_last_name: string | null;
  sold_at: string | null;
  processed_at: string;
  helloasso_order_id: number | null;
  buvette_product_id: number | null;
}

export interface SyncResult {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface WebhookStatus {
  url: string | null;
  /**
   * `null` quand l'état est indéterminable : HelloAsso ne permet pas de relire
   * l'URL de notification enregistrée. Ne jamais traiter `null` comme `false`,
   * ce serait annoncer « non configuré » pour un webhook qui fonctionne.
   */
  configured: boolean | null;
  /** `false` tant que HelloAsso n'expose pas la lecture de sa configuration. */
  verifiable: boolean;
  /** Dernière vente reçue : preuve directe que le webhook nous appelle. */
  last_sale_at: string | null;
  sales_count: number;
}

export interface WebhookConfigureRequest {
  url?: string;
}

/* Scan de justificatifs */

/** Un coin du document, en pixels de la photo d'origine. */
export interface ScanCorner {
  x: number;
  y: number;
}

export interface ScanDetectResponse {
  detected: boolean;
  corners: ScanCorner[] | null;
}

/* Barcode lookup */
export interface OpenFoodFactsData {
  name: string | null;
  brand: string | null;
  image_url: string | null;
  quantity: string | null;
  categories: string[];
}

export interface BarcodeLookupResponse {
  barcode: string;
  found_in: 'stock' | 'buvette' | null;
  stock_item: StockItem | null;
  buvette_product: BuvetteProduct | null;
  openfoodfacts: OpenFoodFactsData | null;
}
