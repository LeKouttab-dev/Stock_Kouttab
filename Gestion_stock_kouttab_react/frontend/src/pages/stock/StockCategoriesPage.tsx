import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, AlertTriangle, Boxes, ScanLine } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useBarcodeLookup, useCategories, useStockItems } from '@/api/endpoints/stock';
import { CategoryIcon } from '@/components/shared/CategoryIcon';
import { fr } from '@/lib/i18n/fr';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import { extractErrorMessage } from '@/api/client';
import { BarcodeScanner } from '@/components/scanner/BarcodeScanner';
import { DirectModificationModal } from './modals/DirectModificationModal';
import { AddItemFromBarcodeModal } from './modals/AddItemFromBarcodeModal';
import type { BarcodeLookupResponse, StockItem } from '@/types/api';

export function StockCategoriesPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const toast = useToast();
  const canScan = can(ACTIONS.STOCK_DIRECT_MOD);

  const lookup = useBarcodeLookup();
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannedItem, setScannedItem] = useState<StockItem | null>(null);
  const [scannedNew, setScannedNew] = useState<BarcodeLookupResponse | null>(null);
  const [directOpen, setDirectOpen] = useState(false);
  const [addNewOpen, setAddNewOpen] = useState(false);

  const handleDetected = async (barcode: string) => {
    setScannerOpen(false);
    try {
      const res = await lookup.mutateAsync(barcode);
      if (res.found_in === 'stock' && res.stock_item) {
        setScannedItem(res.stock_item);
        setDirectOpen(true);
      } else {
        setScannedNew(res);
        setAddNewOpen(true);
      }
    } catch (e) {
      toast.error(fr.scanner.lookupError, extractErrorMessage(e));
    }
  };

  const { data: categories = [], isLoading: catLoading } = useCategories();
  const { data: items = [], isLoading: itemsLoading } = useStockItems();

  const stats = useMemo(() => {
    const map = new Map<string, { count: number; alerts: number }>();
    items.forEach((it) => {
      const cur = map.get(it.categorie) ?? { count: 0, alerts: 0 };
      cur.count += 1;
      if (it.quantite < it.seuil_alerte) cur.alerts += 1;
      map.set(it.categorie, cur);
    });
    return map;
  }, [items]);

  if (catLoading || itemsLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </div>
    );
  }

  if (categories.length === 0) {
    return <EmptyState title={fr.stock.aucunArticle} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 font-serif text-2xl font-bold text-forest">
            <Boxes className="h-6 w-6" aria-hidden />
            {fr.stock.title}
          </h1>
          <p className="text-sm text-muted-foreground">Naviguez par catégorie.</p>
        </div>
        {canScan && (
          <Button variant="outline" onClick={() => setScannerOpen(true)} loading={lookup.isPending}>
            <ScanLine className="h-4 w-4" />
            {fr.scanner.scan}
          </Button>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((cat) => {
          const s = stats.get(cat.nom) ?? { count: 0, alerts: 0 };
          return (
            <Card
              key={cat.nom}
              className="transition-all hover:shadow-md hover:-translate-y-0.5 cursor-pointer"
              onClick={() => navigate(`/stock/${encodeURIComponent(cat.nom)}`)}
            >
              <CardContent className="p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="rounded-lg bg-forest/10 p-2.5 text-forest">
                    <CategoryIcon nom={cat.nom} className="h-7 w-7" />
                  </div>
                  {s.alerts > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-terracotta-100 px-2 py-0.5 text-xs font-semibold text-terracotta-800">
                      <AlertTriangle className="h-3 w-3" />
                      {s.alerts}
                    </span>
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-semibold">{cat.nom}</h2>
                  <p className="text-sm text-muted-foreground">
                    {s.count} {fr.stock.nombreArticles.toLowerCase()}
                  </p>
                </div>
                <Button
                  variant="outline"
                  fullWidth
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/stock/${encodeURIComponent(cat.nom)}`);
                  }}
                >
                  {fr.stock.consulter} {cat.nom}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <BarcodeScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onDetected={handleDetected}
      />
      <DirectModificationModal
        open={directOpen}
        onOpenChange={(o) => {
          setDirectOpen(o);
          if (!o) setScannedItem(null);
        }}
        item={scannedItem}
      />
      <AddItemFromBarcodeModal
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
