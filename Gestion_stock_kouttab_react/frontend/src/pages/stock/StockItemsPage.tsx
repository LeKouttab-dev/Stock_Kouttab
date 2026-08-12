import { useMemo, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Edit3, Send, ScanLine, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useBarcodeLookup, useDeleteStockItem, useStockItems } from '@/api/endpoints/stock';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { ACTIONS } from '@/lib/auth';
import { fr } from '@/lib/i18n/fr';
import type { BarcodeLookupResponse, StockItem } from '@/types/api';
import { RequestModificationModal } from './modals/RequestModificationModal';
import { DirectModificationModal } from './modals/DirectModificationModal';
import { AddItemFromBarcodeModal } from './modals/AddItemFromBarcodeModal';
import { BarcodeScanner } from '@/components/scanner/BarcodeScanner';

interface StockItemsListProps {
  items: StockItem[];
}

export function StockItemsList({ items }: StockItemsListProps) {
  const { can } = useAuth();
  const canDirect = can(ACTIONS.STOCK_DIRECT_MOD);
  const canRequest = can(ACTIONS.STOCK_REQUEST_MOD);
  const canDelete = canDirect; // même permission que la modif directe (AdminBenevoles+)

  const toast = useToast();
  const deleteMut = useDeleteStockItem();

  const [requestOpen, setRequestOpen] = useState(false);
  const [directOpen, setDirectOpen] = useState(false);
  const [selected, setSelected] = useState<StockItem | null>(null);

  const sorted = useMemo(() => [...items].sort((a, b) => a.nom.localeCompare(b.nom)), [items]);

  const handleDelete = (item: StockItem) => {
    if (!confirm(`Supprimer définitivement « ${item.nom} » ? Cette action est irréversible.`))
      return;
    deleteMut.mutate(item.id, { onSuccess: () => toast.success(`« ${item.nom} » supprimé`) });
  };

  if (sorted.length === 0) return <EmptyState title={fr.stock.aucunSousCat} />;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((item) => {
          const isAlert = item.quantite < item.seuil_alerte;
          return (
            <Card key={item.id} className="transition-shadow hover:shadow-md">
              <CardContent className="p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-semibold">
                      <span className="mr-1.5 text-xl" aria-hidden>
                        {item.emoji ?? '📦'}
                      </span>
                      {item.nom}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2">
                  <span className="text-xs text-muted-foreground">{fr.stock.quantiteEnStock}</span>
                  <span className="text-2xl font-bold">{item.quantite}</span>
                </div>

                {isAlert ? (
                  <p className="flex items-center gap-1 text-xs text-terracotta-700">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {fr.stock.seuilBas} ({item.seuil_alerte})
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {fr.stock.seuilAlerte} : {item.seuil_alerte}
                  </p>
                )}

                {canDirect && (
                  <div className="flex gap-2">
                    <Button
                      className="flex-1"
                      onClick={() => {
                        setSelected(item);
                        setDirectOpen(true);
                      }}
                    >
                      <Edit3 className="h-4 w-4" />
                      {fr.stock.modifier}
                    </Button>
                    {canDelete && (
                      <Button
                        variant="outline"
                        size="icon"
                        title="Supprimer cet article"
                        onClick={() => handleDelete(item)}
                        loading={deleteMut.isPending && deleteMut.variables === item.id}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </div>
                )}
                {!canDirect && canRequest && (
                  <Button
                    fullWidth
                    variant="outline"
                    onClick={() => {
                      setSelected(item);
                      setRequestOpen(true);
                    }}
                  >
                    <Send className="h-4 w-4" />
                    {fr.stock.demanderModification}
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <RequestModificationModal open={requestOpen} onOpenChange={setRequestOpen} item={selected} />
      <DirectModificationModal open={directOpen} onOpenChange={setDirectOpen} item={selected} />
    </>
  );
}

export function StockItemsPage() {
  const { category: rawCategory, subcategory: rawSubcategory } = useParams<{
    category: string;
    subcategory: string;
  }>();
  const category = rawCategory ? decodeURIComponent(rawCategory) : '';
  const subcategory = rawSubcategory ? decodeURIComponent(rawSubcategory) : '';
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

  const { data: items = [], isLoading } = useStockItems({ category, subcategory });

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

  if (!category || !subcategory) return <Navigate to="/stock" replace />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/stock/${encodeURIComponent(category)}`)}
        >
          <ArrowLeft className="h-4 w-4" />
          {fr.stock.retourA} {category}
        </Button>
        <span className="text-xs text-muted-foreground">
          {category} / {subcategory}
        </span>
        {canScan && (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => setScannerOpen(true)}
            loading={lookup.isPending}
          >
            <ScanLine className="h-4 w-4" />
            {fr.scanner.scan}
          </Button>
        )}
      </div>

      <h1 className="text-2xl font-bold">
        {fr.stock.articlesPour} : {subcategory}
      </h1>

      {isLoading ? <Skeleton className="h-64" /> : <StockItemsList items={items} />}

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
        defaultCategory={category}
        defaultSubcategory={subcategory}
      />
    </div>
  );
}
