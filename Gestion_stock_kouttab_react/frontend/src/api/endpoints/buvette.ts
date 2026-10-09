import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type {
  BuvetteProduct,
  BuvetteReglages,
  BuvetteStats,
  CaisseEtatResponse,
  Cloture,
  ClotureAttendu,
  ClotureCreate,
  Inventaire,
  InventaireEspeces,
  InventaireResume,
  InventaireTerminer,
  MoyenPaiement,
  PaiementsResponse,
  CaisseAppVersion,
  BuvetteProductCreate,
  BuvetteProductUpdate,
  BuvetteSale,
  SyncResult,
  WebhookConfigureRequest,
  WebhookStatus,
} from '@/types/api';
import { nomFichierDepuisEntete } from '@/lib/buvette';

export const buvetteQueryKeys = {
  all: ['buvette'] as const,
  products: () => [...buvetteQueryKeys.all, 'products'] as const,
  sales: (filters?: Record<string, unknown>) =>
    [...buvetteQueryKeys.all, 'sales', filters ?? {}] as const,
  webhook: () => [...buvetteQueryKeys.all, 'webhook'] as const,
  paiements: (filters: Record<string, unknown>) =>
    [...buvetteQueryKeys.all, 'paiements', filters] as const,
  stats: (filters: Record<string, unknown>) => [...buvetteQueryKeys.all, 'stats', filters] as const,
  clotures: () => [...buvetteQueryKeys.all, 'clotures'] as const,
  clotureAttendu: (jour: string) => [...buvetteQueryKeys.clotures(), 'attendu', jour] as const,
  clotureHistorique: (limit: number) =>
    [...buvetteQueryKeys.clotures(), 'historique', limit] as const,
  caisseEtat: () => [...buvetteQueryKeys.all, 'caisse-etat'] as const,
  reglages: () => [...buvetteQueryKeys.all, 'reglages'] as const,
  inventaires: () => [...buvetteQueryKeys.all, 'inventaires'] as const,
  inventaireEnCours: () => [...buvetteQueryKeys.inventaires(), 'en-cours'] as const,
  inventaire: (id: number) => [...buvetteQueryKeys.inventaires(), 'detail', id] as const,
  inventaireEspeces: (id: number, debut: string | null) =>
    [...buvetteQueryKeys.inventaires(), 'especes', id, debut] as const,
  inventairesHistorique: (filtres: Record<string, unknown>) =>
    [...buvetteQueryKeys.inventaires(), 'historique', filtres] as const,
};

/* ---------- Products ---------- */
async function fetchProducts(): Promise<BuvetteProduct[]> {
  const { data } = await api.get<BuvetteProduct[]>('/buvette/products');
  return data;
}

async function createProduct(payload: BuvetteProductCreate): Promise<BuvetteProduct> {
  const { data } = await api.post<BuvetteProduct>('/buvette/products', payload);
  return data;
}

async function updateProduct(params: {
  id: number;
  data: BuvetteProductUpdate;
}): Promise<BuvetteProduct> {
  const { data } = await api.patch<BuvetteProduct>(`/buvette/products/${params.id}`, params.data);
  return data;
}

async function deleteProduct(id: number): Promise<void> {
  await api.delete(`/buvette/products/${id}`);
}

/* ---------- Sales ---------- */
async function fetchSales(limit = 50, offset = 0): Promise<BuvetteSale[]> {
  const { data } = await api.get<BuvetteSale[]>('/buvette/sales', {
    params: { limit, offset },
  });
  return data;
}

/* ---------- Sync ---------- */
async function syncBuvette(): Promise<SyncResult> {
  const { data } = await api.post<SyncResult>('/buvette/sync');
  return data;
}

/* ---------- Webhook ---------- */
async function fetchWebhookStatus(): Promise<WebhookStatus> {
  const { data } = await api.get<WebhookStatus>('/buvette/webhook/status');
  return data;
}

async function configureWebhook(payload?: WebhookConfigureRequest): Promise<WebhookStatus> {
  const { data } = await api.post<WebhookStatus>('/buvette/webhook/configure', payload ?? {});
  return data;
}

async function deleteWebhook(): Promise<void> {
  await api.delete('/buvette/webhook');
}

/* ---------- Hooks ---------- */
export function useBuvetteProducts() {
  return useQuery({
    queryKey: buvetteQueryKeys.products(),
    queryFn: fetchProducts,
  });
}

export function useBuvetteSales(limit = 50, offset = 0) {
  return useQuery({
    queryKey: buvetteQueryKeys.sales({ limit, offset }),
    queryFn: () => fetchSales(limit, offset),
  });
}

export function useCreateBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useUpdateBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

/**
 * Dépose la photo d'un produit : prise au téléphone, ou choisie sur l'ordinateur.
 *
 * Le serveur la réduit à 600 px et lui donne une adresse NEUVE à chaque dépôt —
 * la tablette met les photos en cache par URL en ignorant les en-têtes, une
 * même adresse y garderait l'ancienne image.
 */
export function useUploadBuvettePhoto() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => {
      const corps = new FormData();
      corps.append('file', file);
      const { data } = await api.post<BuvetteProduct>(`/buvette/products/${id}/photo`, corps);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

/** Retire la photo : la tablette reprend l'emoji, jamais une case vide. */
export function useDeleteBuvettePhoto() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete<BuvetteProduct>(`/buvette/products/${id}/photo`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useDeleteBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useSyncBuvette() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: syncBuvette,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useWebhookStatus() {
  return useQuery({
    queryKey: buvetteQueryKeys.webhook(),
    queryFn: fetchWebhookStatus,
  });
}

export function useConfigureWebhook() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: (payload?: WebhookConfigureRequest) => configureWebhook(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.webhook() }),
  });
}

export function useDeleteWebhook() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.webhook() }),
  });
}

/* ---- Application de la tablette de caisse ------------------------------- */

export const caisseAppQueryKey = ['buvette', 'app-caisse'] as const;

/** La version servie aux tablettes, ou `null` si rien n'a été publié. */
export function useCaisseAppVersion(actif = true) {
  return useQuery({
    queryKey: caisseAppQueryKey,
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<CaisseAppVersion | null>('/buvette/app');
      return data;
    },
  });
}

/**
 * Publie l'APK que les tablettes installeront à leur prochain réveil.
 *
 * Délai généreux : le fichier pèse des dizaines de mégaoctets, là où les
 * autres appels de l'application se comptent en kilo-octets.
 */
export function usePublierCaisseApp() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async ({
      file,
      version_code,
      version_name,
    }: {
      file: File;
      version_code: number;
      version_name: string;
    }) => {
      const corps = new FormData();
      corps.append('file', file);
      corps.append('version_code', String(version_code));
      corps.append('version_name', version_name);
      const { data } = await api.post<CaisseAppVersion>('/buvette/app', corps, {
        timeout: 300_000,
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: caisseAppQueryKey }),
  });
}

/** Retire la version publiée. Les tablettes gardent celle qu'elles exécutent. */
export function useRetirerCaisseApp() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async () => {
      const { data } = await api.delete('/buvette/app');
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: caisseAppQueryKey }),
  });
}

/* ---- Réapprovisionnement ------------------------------------------------- */

/**
 * Ajoute `delta` au stock d'un produit. L'incrément est fait par le serveur
 * (`quantity = quantity + delta`) : deux réappros simultanés s'additionnent,
 * là où un PATCH de la quantité lue écraserait l'un par l'autre.
 */
export function useReapproBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async ({ id, delta }: { id: number; delta: number }) => {
      const { data } = await api.post<BuvetteProduct>(`/buvette/products/${id}/reappro`, {
        delta,
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

/* ---- Paiements ----------------------------------------------------------- */

export interface PaiementsFiltres {
  debut: string;
  fin: string;
  moyen?: MoyenPaiement | null;
}

export function useBuvettePaiements(filtres: PaiementsFiltres) {
  const params: Record<string, string> = { debut: filtres.debut, fin: filtres.fin };
  if (filtres.moyen) params.moyen = filtres.moyen;
  return useQuery({
    queryKey: buvetteQueryKeys.paiements(params),
    queryFn: async () => {
      const { data } = await api.get<PaiementsResponse>('/buvette/paiements', { params });
      return data;
    },
  });
}

/* ---- Statistiques -------------------------------------------------------- */

export function useBuvetteStats(debut: string, fin: string) {
  return useQuery({
    queryKey: buvetteQueryKeys.stats({ debut, fin }),
    queryFn: async () => {
      const { data } = await api.get<BuvetteStats>('/buvette/stats', {
        params: { debut, fin },
      });
      return data;
    },
  });
}

/* ---- Clôture de caisse espèces ------------------------------------------- */

export function useClotureAttendu(jour: string) {
  return useQuery({
    queryKey: buvetteQueryKeys.clotureAttendu(jour),
    queryFn: async () => {
      const { data } = await api.get<ClotureAttendu>('/buvette/clotures/attendu', {
        params: { jour },
      });
      return data;
    },
  });
}

export function useClotures(limit = 30) {
  return useQuery({
    queryKey: buvetteQueryKeys.clotureHistorique(limit),
    queryFn: async () => {
      const { data } = await api.get<Cloture[]>('/buvette/clotures', { params: { limit } });
      return data;
    },
  });
}

export function useCreateCloture() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (payload: ClotureCreate) => {
      const { data } = await api.post<Cloture>('/buvette/clotures', payload);
      return data;
    },
    // 409 (déjà clôturé) compris : l'écran relit l'état du jour dans les deux cas.
    onSettled: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.clotures() }),
  });
}

/* ---- Tablette : état et réglages ------------------------------------------ */

/** Dernier signe de vie de la tablette, relu toutes les 30 s. */
export function useCaisseEtat() {
  return useQuery({
    queryKey: buvetteQueryKeys.caisseEtat(),
    queryFn: async () => {
      const { data } = await api.get<CaisseEtatResponse>('/buvette/caisse/etat');
      return data;
    },
    refetchInterval: 30_000,
  });
}

export function useBuvetteReglages(actif = true) {
  return useQuery({
    queryKey: buvetteQueryKeys.reglages(),
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<BuvetteReglages>('/buvette/reglages');
      return data;
    },
  });
}

export function useUpdateBuvetteReglages() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (recap_destinataires: string[]) => {
      const { data } = await api.put<BuvetteReglages>('/buvette/reglages', {
        recap_destinataires,
      });
      return data;
    },
    onSuccess: (data) => qc.setQueryData(buvetteQueryKeys.reglages(), data),
  });
}

/* ---- Inventaire (stock + espèces) ----------------------------------------- */

/** L'inventaire non terminé (en cours ou stock validé), ou `null`. */
export function useInventaireEnCours() {
  return useQuery({
    queryKey: buvetteQueryKeys.inventaireEnCours(),
    queryFn: async () => {
      const { data } = await api.get<{ inventaire: Inventaire | null }>(
        '/buvette/inventaires/en-cours',
      );
      return data.inventaire;
    },
  });
}

export function useInventaire(id: number | null) {
  return useQuery({
    queryKey: buvetteQueryKeys.inventaire(id ?? 0),
    enabled: id !== null,
    queryFn: async () => {
      const { data } = await api.get<Inventaire>(`/buvette/inventaires/${id}`);
      return data;
    },
  });
}

export interface InventairesFiltres {
  debut?: string;
  fin?: string;
}

function paramsPeriode(filtres: InventairesFiltres): Record<string, string> {
  const params: Record<string, string> = {};
  if (filtres.debut) params.debut = filtres.debut;
  if (filtres.fin) params.fin = filtres.fin;
  return params;
}

export function useInventaires(filtres: InventairesFiltres) {
  const params = paramsPeriode(filtres);
  return useQuery({
    queryKey: buvetteQueryKeys.inventairesHistorique(params),
    queryFn: async () => {
      const { data } = await api.get<InventaireResume[]>('/buvette/inventaires', { params });
      return data;
    },
  });
}

/** Ventes espèces de la période ; `debut` n'est demandé qu'au premier inventaire. */
export function useInventaireEspeces(id: number, debut: string | null, actif = true) {
  return useQuery({
    queryKey: buvetteQueryKeys.inventaireEspeces(id, debut),
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<InventaireEspeces>(`/buvette/inventaires/${id}/especes`, {
        params: debut ? { debut } : {},
      });
      return data;
    },
  });
}

/** Range l'inventaire renvoyé par le serveur et rafraîchit l'en-cours et l'historique. */
function useApresInventaire() {
  const qc = useQueryClient();
  return (inv: Inventaire) => {
    qc.setQueryData(buvetteQueryKeys.inventaire(inv.id), inv);
    void qc.invalidateQueries({ queryKey: buvetteQueryKeys.inventaireEnCours() });
    void qc.invalidateQueries({ queryKey: [...buvetteQueryKeys.inventaires(), 'historique'] });
  };
}

export function useDemarrerInventaire() {
  const apres = useApresInventaire();
  return useApiMutation({
    mutationFn: async () => {
      const { data } = await api.post<Inventaire>('/buvette/inventaires');
      return data;
    },
    onSuccess: apres,
  });
}

/** Brouillon du comptage : le cache n'est pas réécrit, la saisie en cours reste maîtresse. */
export function useEnregistrerComptage() {
  return useApiMutation({
    mutationFn: async ({
      id,
      lignes,
    }: {
      id: number;
      lignes: { id: number; quantite_comptee: number }[];
    }) => {
      const { data } = await api.put<Inventaire>(`/buvette/inventaires/${id}/lignes`, { lignes });
      return data;
    },
  });
}

export function useValiderStockInventaire() {
  const qc = useQueryClient();
  const apres = useApresInventaire();
  return useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<Inventaire>(`/buvette/inventaires/${id}/valider-stock`);
      return data;
    },
    onSuccess: (inv) => {
      apres(inv);
      // Le stock de chaque produit vient d'être remplacé.
      void qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() });
    },
  });
}

export function useTerminerInventaire() {
  const apres = useApresInventaire();
  return useApiMutation({
    mutationFn: async ({ id, ...corps }: InventaireTerminer & { id: number }) => {
      const { data } = await api.post<Inventaire>(`/buvette/inventaires/${id}/terminer`, corps);
      return data;
    },
    onSuccess: apres,
  });
}

export function useAbandonnerInventaire() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/buvette/inventaires/${id}`);
      return id;
    },
    onSuccess: (id) => {
      qc.removeQueries({ queryKey: buvetteQueryKeys.inventaire(id) });
      void qc.invalidateQueries({ queryKey: buvetteQueryKeys.inventaires() });
    },
  });
}

/* ---- Exports Excel ---------------------------------------------------------- */

export interface TelechargementExcel {
  chemin: string;
  params?: Record<string, string>;
  /** Utilisé si le serveur n'annonce pas de nom (en-tête absent ou non exposé). */
  nomParDefaut: string;
}

async function telechargerExcel({
  chemin,
  params,
  nomParDefaut,
}: TelechargementExcel): Promise<string> {
  const reponse = await api.get(chemin, { params, responseType: 'blob' });
  const entete = reponse.headers['content-disposition'] as string | undefined;
  const nom = nomFichierDepuisEntete(entete) ?? nomParDefaut;
  const url = window.URL.createObjectURL(reponse.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
  return nom;
}

export function useTelechargerExcel() {
  return useApiMutation({ mutationFn: telechargerExcel });
}

export function paramsExportPaiements(filtres: PaiementsFiltres): Record<string, string> {
  const params: Record<string, string> = { debut: filtres.debut, fin: filtres.fin };
  if (filtres.moyen) params.moyen = filtres.moyen;
  return params;
}

export function paramsExportInventaires(filtres: InventairesFiltres): Record<string, string> {
  return paramsPeriode(filtres);
}
