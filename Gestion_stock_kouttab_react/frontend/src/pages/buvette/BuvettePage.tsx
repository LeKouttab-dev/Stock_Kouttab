import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, AlertTriangle, ShoppingCart, Coins, ScanLine } from 'lucide-react';
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
  useSyncBuvette,
} from '@/api/endpoints/buvette';
import { useBarcodeLookup } from '@/api/endpoints/stock';
import { formatCents } from '@/lib/format';
import { AdjustStockModal } from './modals/AdjustStockModal';
import { CreateProductModal } from './modals/CreateProductModal';
import { WebhookConfigModal } from './modals/WebhookConfigModal';
import { AddBuvetteFromBarcodeModal } from './modals/AddBuvetteFromBarcodeModal';
import { BarcodeScanner } from '@/components/scanner/BarcodeScanner';
import type { BarcodeLookupResponse, BuvetteProduct } from '@/types/api';

function startOfTodayIso(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

export function BuvettePage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const toast = useToast();

  const canSync = can(ACTIONS.BUVETTE_SYNC);
  const canCrud = can(ACTIONS.BUVETTE_CRUD);
  const canWebhook = can(ACTIONS.BUVETTE_WEBHOOK);

  const products = useBuvetteProducts();
  const sales = useBuvetteSales(200, 0);
  const sync = useSyncBuvette();
  const remove = useDeleteBuvetteProduct();

  const [adjustOpen, setAdjustOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [webhookOpen, setWebhookOpen] = useState(false);
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

  const handleSync = async () => {
    try {
      const r = await sync.mutateAsync();
      const msg = fr.buvette.syncSuccess(r);
      if (r.errors.length > 0) {
        toast.warning(msg, `${r.errors.length} erreur(s) — voir les logs.`);
      } else {
        toast.success('Synchronisation terminée', msg);
      }
    } catch (e) {
      toast.error('Erreur de synchronisation', extractErrorMessage(e));
    }
  };

  const handleDelete = async (p: BuvetteProduct) => {
    if (!window.confirm(fr.buvette.deleteConfirm)) return;
    try {
      await remove.mutateAsync(p.id);
      toast.success(fr.buvette.productDeleted);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
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
          <Button variant="outline" onClick={() => navigate('/buvette/sales')}>
            {fr.buvette.viewSales}
          </Button>
          {canWebhook && (
            <Button variant="ghost" onClick={() => setWebhookOpen(true)}>
              {fr.buvette.webhook}
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
            />
          ))}
        </div>
      )}

      <AdjustStockModal open={adjustOpen} onOpenChange={setAdjustOpen} product={selected} />
      <CreateProductModal open={createOpen} onOpenChange={setCreateOpen} />
      <WebhookConfigModal open={webhookOpen} onOpenChange={setWebhookOpen} />

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
