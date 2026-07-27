import type {
  ExpenseStatus,
  InvoiceStatus,
  Role,
  StockModStatus,
  ValidationStatus,
} from '@/lib/constants';

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
  role: Role;
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
  rattachement: string;
  fournisseur?: string | null;
  nature_charge?: string | null;
  montant: number;
  commentaires?: string | null;
  remboursement_deja_emis: number;
  remise: number;
  status: ExpenseStatus;
  commentaires_compta?: string | null;
  date_soumission?: string;
  files?: ExpenseFile[];
}

export interface ExpenseCreateRequest {
  date_depense: string;
  rattachement: string;
  fournisseur?: string;
  nature_charge?: string;
  montant: number;
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
  isConfigured: boolean;
}

export interface WebhookConfigureRequest {
  url?: string;
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
