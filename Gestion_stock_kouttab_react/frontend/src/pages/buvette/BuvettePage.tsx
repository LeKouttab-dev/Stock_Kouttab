import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Package,
  AlertTriangle,
  ShoppingCart,
  Coins,
  ScanLine,
  Receipt,
  BarChart3,
  Lock,
  Tablet,
  ClipboardList,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { KpiCard } from '@/components/shared/KpiCard';
import { EmptyState } from '@/components/shared/EmptyState';
import { BuvetteProductCard } from '@/components/buvette/BuvetteProductCard';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import { fr } from '@/lib/i18n/fr';
import { extractErrorMessage } from '@/api/client';
import {
  useBuvetteProducts,
  useBuvetteSales,
  useDeleteBuvetteProduct,
  useReapproBuvetteProduct,
  useSyncBuvette,
  useUpdateBuvetteProduct,
} from '@/api/endpoints/buvette';
import { useBarcodeLookup } from '@/api/endpoints/stock';
import { formatCents } from '@/lib/format';
import { AdjustStockModal } from './modals/AdjustStockModal';
import { CreateProductModal } from './modals/CreateProductModal';
import { WebhookConfigModal } from './modals/WebhookConfigModal';
import { AppCaisseModal } from './modals/AppCaisseModal';
import { AddBuvetteFromBarcodeModal } from './modals/AddBuvetteFromBarcodeModal';
import { PaiementsTab } from './tabs/PaiementsTab';
import { StatistiquesTab } from './tabs/StatistiquesTab';
import { ClotureTab } from './tabs/ClotureTab';
import { InventaireTab } from './tabs/InventaireTab';
import { TabletteTab } from './tabs/TabletteTab';
import { BarcodeScanner } from '@/components/scanner/BarcodeScanner';
import type { BarcodeLookupResponse, BuvetteProduct } from '@/types/api';

function startOfTodayIso(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

const ONGLETS = [
  'produits',
  'paiements',
  'statistiques',
  'cloture',
  'inventaire',
  'tablette',
] as const;
type Onglet = (typeof ONGLETS)[number];

function estOnglet(v: string | null): v is Onglet {
  return v !== null && (ONGLETS as readonly string[]).includes(v);
}

export function BuvettePage() {
  // L'onglet vit dans l'adresse (?onglet=paiements) : on peut y renvoyer par
  // un lien, et le rechargement de la page ne ramène pas aux produits.
  const [searchParams, setSearchParams] = useSearchParams();
  const ongletParam = searchParams.get('onglet');
  const onglet: Onglet = estOnglet(ongletParam) ? ongletParam : 'produits';
  const changerOnglet = (v: string) => {
    const suivant = new URLSearchParams(searchParams);
    if (v === 'produits') suivant.delete('onglet');
    else suivant.set('onglet', v);
    setSearchParams(suivant, { replace: true });
  };

  const { can } = useAuth();
  const toast = useToast();

  const canSync = can(ACTIONS.BUVETTE_SYNC);
  const canCrud = can(ACTIONS.BUVETTE_CRUD);
  const canWebhook = can(ACTIONS.BUVETTE_WEBHOOK);

  const products = useBuvetteProducts();
  const sales = useBuvetteSales(200, 0);
  const sync = useSyncBuvette();
  const remove = useDeleteBuvetteProduct();
  const update = useUpdateBuvetteProduct();
  const reappro = useReapproBuvetteProduct();
  const reapproId = reappro.isPending ? reappro.variables?.id : undefined;

  const [adjustOpen, setAdjustOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [webhookOpen, setWebhookOpen] = useState(false);
  const [appCaisseOpen, setAppCaisseOpen] = useState(false);
  const [selected, setSelected] = useState<BuvetteProduct | null>(null);

  // Scanner flow state
  const lookup = useBarcodeLookup();
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannedNew, setScannedNew] = useState<BarcodeLookupResponse | null>(null);
  const [addNewOpen, setAddNewOpen] = useState(false);

  const handleDetected = async (barcode: string) => {
    setScannerOpen(false);
    try {
      const res = await lookup.mutateAsync(barcode);
      if (res.found_in === 'buvette' && res.buvette_product) {
        setSelected(res.buvette_product);
        setAdjustOpen(true);
      } else {
        setScannedNew(res);
        setAddNewOpen(true);
      }
    } catch (e) {
      toast.error(fr.scanner.lookupError, extractErrorMessage(e));
    }
  };

  const list = products.data ?? [];

  const kpis = useMemo(() => {
    const totalProducts = list.length;
    const totalStock = list.reduce((acc, p) => acc + p.quantity, 0);
    const productsAlert = list.filter((p) => p.quantity <= p.seuil_alerte).length;
    const today = startOfTodayIso();
    const salesToday = (sales.data ?? []).filter((s) => (s.sold_at ?? s.processed_at) >= today);
    const salesTodayCents = salesToday.reduce((acc, s) => acc + s.amount_cents, 0);
    return {
      totalProducts,
      totalStock,
      productsAlert,
      salesTodayCents,
      salesTodayCount: salesToday.length,
    };
  }, [list, sales.data]);

  // Pas de `catch` ici : `useSyncBuvette` signale déjà l'échec par un toast,
  // en ajouter un second en affichait deux à l'écran.
  const handleSync = () => {
    sync.mutate(undefined, {
      onSuccess: (r) => {
        const msg = fr.buvette.syncSuccess(r);
        if (r.errors.length > 0) {
          toast.warning(msg, `${r.errors.length} erreur(s) : voir les logs.`);
        } else {
          toast.success('Synchronisation terminée', msg);
        }
      },
    });
  };

  // Masqué = absent du catalogue de la tablette (le serveur filtre is_active), onglet conservé.
  const handleToggleActive = (p: BuvetteProduct) => {
    update.mutate(
      { id: p.id, data: { is_active: !p.is_active } },
      {
        onSuccess: () =>
          toast.success(p.is_active ? fr.buvette.produitMasque : fr.buvette.produitAffiche),
        onError: (e) => toast.error(extractErrorMessage(e)),
      },
    );
  };

  // L'échec est déjà signalé par `useApiMutation` : pas de second toast ici.
  const handleReappro = (p: BuvetteProduct, delta: number) => {
    reappro.mutate(
      { id: p.id, delta },
      {
        onSuccess: (maj) =>
          toast.success(
            fr.buvette.reappro.succes(maj.name),
            fr.buvette.reappro.stock(maj.quantity),
          ),
      },
    );
  };

  const handleDelete = (p: BuvetteProduct) => {
    if (!window.confirm(fr.buvette.deleteConfirm)) return;
    remove.mutate(p.id, { onSuccess: () => toast.success(fr.buvette.productDeleted) });
  };

  const handleAdjust = (p: BuvetteProduct) => {
    setSelected(p);
    setAdjustOpen(true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-2xl font-bold text-forest">{fr.buvette.title}</h1>
        <p className="text-sm text-muted-foreground">{fr.buvette.subtitle}</p>
      </div>

      <Tabs value={onglet} onValueChange={changerOnglet}>
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 sm:w-auto">
          <TabsTrigger value="produits" className="gap-1.5">
            <Package className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.produits}
          </TabsTrigger>
          <TabsTrigger value="paiements" className="gap-1.5">
            <Receipt className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.paiements}
          </TabsTrigger>
          <TabsTrigger value="statistiques" className="gap-1.5">
            <BarChart3 className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.statistiques}
          </TabsTrigger>
          <TabsTrigger value="cloture" className="gap-1.5">
            <Lock className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.cloture}
          </TabsTrigger>
          <TabsTrigger value="inventaire" className="gap-1.5">
            <ClipboardList className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.inventaire}
          </TabsTrigger>
          <TabsTrigger value="tablette" className="gap-1.5">
            <Tablet className="h-4 w-4" aria-hidden />
            {fr.buvette.tabs.tablette}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="produits" className="space-y-6">
          {(canSync || canCrud || canWebhook) && (
            <div className="flex flex-wrap gap-2">
              {canSync && (
                <Button onClick={handleSync} loading={sync.isPending}>
                  {sync.isPending ? fr.buvette.syncing : fr.buvette.sync}
                </Button>
              )}
              {canCrud && (
                <Button variant="outline" onClick={() => setCreateOpen(true)}>
                  {fr.buvette.addProduct}
                </Button>
              )}
              {canCrud && (
                <Button
                  variant="outline"
                  onClick={() => setScannerOpen(true)}
                  loading={lookup.isPending}
                >
                  <ScanLine className="h-4 w-4" />
                  {fr.scanner.scan}
                </Button>
              )}
              {canWebhook && (
                <Button variant="ghost" onClick={() => setWebhookOpen(true)}>
                  {fr.buvette.webhook}
                </Button>
              )}
              {/* Même cercle que le webhook : publier cet APK, c'est distribuer de
              quoi encaisser — il porte la clé SumUp et la clé de caisse. */}
              {canWebhook && (
                <Button variant="ghost" onClick={() => setAppCaisseOpen(true)}>
                  Application tablette
                </Button>
              )}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label={fr.buvette.totalProducts}
              value={kpis.totalProducts}
              icon={<Package className="h-6 w-6" />}
            />
            <KpiCard
              label={fr.buvette.totalStock}
              value={kpis.totalStock}
              icon={<ShoppingCart className="h-6 w-6" />}
              variant="info"
            />
            <KpiCard
              label={fr.buvette.productsAlert}
              value={kpis.productsAlert}
              icon={<AlertTriangle className="h-6 w-6" />}
              variant={kpis.productsAlert > 0 ? 'danger' : 'success'}
            />
            <KpiCard
              label={fr.buvette.salesToday}
              value={formatCents(kpis.salesTodayCents)}
              hint={`${kpis.salesTodayCount} vente(s)`}
              icon={<Coins className="h-6 w-6" />}
              variant="success"
            />
          </div>

          {products.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-72" />
              ))}
            </div>
          ) : list.length === 0 ? (
            <EmptyState
              title={fr.buvette.noProducts}
              action={
                canSync ? (
                  <Button onClick={handleSync} loading={sync.isPending}>
                    {fr.buvette.sync}
                  </Button>
                ) : null
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {list.map((p) => (
                <BuvetteProductCard
                  key={p.id}
                  product={p}
                  canEdit={canCrud}
                  onAdjust={handleAdjust}
                  onDelete={handleDelete}
                  onToggleActive={handleToggleActive}
                  onReappro={handleReappro}
                  reapproEnCours={reapproId === p.id}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="paiements">
          <PaiementsTab />
        </TabsContent>
        <TabsContent value="statistiques">
          <StatistiquesTab />
        </TabsContent>
        <TabsContent value="cloture">
          <ClotureTab />
        </TabsContent>
        <TabsContent value="inventaire">
          <InventaireTab />
        </TabsContent>
        <TabsContent value="tablette">
          <TabletteTab />
        </TabsContent>
      </Tabs>

      <AdjustStockModal open={adjustOpen} onOpenChange={setAdjustOpen} product={selected} />
      <CreateProductModal open={createOpen} onOpenChange={setCreateOpen} />
      <WebhookConfigModal open={webhookOpen} onOpenChange={setWebhookOpen} />
      <AppCaisseModal open={appCaisseOpen} onOpenChange={setAppCaisseOpen} />

      <BarcodeScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onDetected={handleDetected}
      />
      <AddBuvetteFromBarcodeModal
        open={addNewOpen}
        onOpenChange={(o) => {
          setAddNewOpen(o);
          if (!o) setScannedNew(null);
        }}
        lookup={scannedNew}
      />
    </div>
  );
}
