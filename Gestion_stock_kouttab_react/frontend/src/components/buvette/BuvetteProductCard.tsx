import { Barcode, Edit3, Eye, EyeOff, Link2, PackagePlus, Tablet, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatCents, formatDateTime } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import type { BuvetteProduct } from '@/types/api';

interface BuvetteProductCardProps {
  product: BuvetteProduct;
  canEdit: boolean;
  /** Ouvre la fiche (nom, prix, seuil, emoji, photo, onglet) : pas de stock. */
  onModifier: (product: BuvetteProduct) => void;
  onDelete: (product: BuvetteProduct) => void;
  /** Bascule `is_active` : désactivé, le produit disparaît de la tablette de caisse. */
  onToggleActive: (product: BuvetteProduct) => void;
  /** Ouvre la fenêtre de réappro (quantité apportée + prix d'achat). */
  onReappro: (product: BuvetteProduct) => void;
}

function getStockBadge(product: BuvetteProduct) {
  if (product.quantity === 0) {
    return <Badge variant="destructive">{fr.buvette.outOfStock}</Badge>;
  }
  if (product.quantity <= product.seuil_alerte) {
    return <Badge variant="warning">{fr.buvette.lowStock}</Badge>;
  }
  return <Badge variant="success">{fr.buvette.ok}</Badge>;
}

export function BuvetteProductCard({
  product,
  canEdit,
  onModifier,
  onDelete,
  onToggleActive,
  onReappro,
}: BuvetteProductCardProps) {
  const isHelloAsso = product.helloasso_tier_id !== null;
  const masque = !product.is_active;

  return (
    <Card
      className={`flex flex-col overflow-hidden transition-shadow hover:shadow-md ${masque ? 'opacity-60' : ''}`}
    >
      <div className="flex items-center justify-center bg-muted/30 p-6">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="h-28 w-28 rounded-md object-cover"
            loading="lazy"
          />
        ) : (
          <span className="text-7xl" aria-hidden>
            {product.emoji || '📦'}
          </span>
        )}
      </div>

      <CardContent className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="truncate text-base font-semibold" title={product.name}>
              {product.name}
            </h3>
            <p className="text-sm font-bold text-primary">{formatCents(product.price_cents)}</p>
            {/* Pour voir d'un coup d'œil ce qui reste à répertorier au scan. */}
            <p
              className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground"
              data-testid="carte-code-barres"
            >
              <Barcode className="h-3 w-3" aria-hidden />
              {product.barcode ? (
                <span className="font-mono">{product.barcode}</span>
              ) : (
                <span className="italic">{fr.buvette.codeBarres.sansCode}</span>
              )}
            </p>
          </div>
          {getStockBadge(product)}
        </div>

        {(isHelloAsso || product.caisse_category || masque) && (
          <div className="flex flex-wrap gap-1.5">
            {isHelloAsso && (
              <Badge variant="outline" className="w-fit text-[10px]">
                <Link2 className="h-3.5 w-3.5" aria-hidden />
                {fr.buvette.helloassoLink}
              </Badge>
            )}
            {/* Sans ce badge, rien ne distingue un produit vendu par la tablette
                d'un produit qui n'y apparaît pas. */}
            {masque ? (
              <Badge variant="outline" className="w-fit text-[10px]">
                <EyeOff className="h-3.5 w-3.5" aria-hidden />
                {fr.buvette.masqueTablette}
              </Badge>
            ) : (
              product.caisse_category && (
                <Badge variant="outline" className="w-fit text-[10px]">
                  <Tablet className="h-3.5 w-3.5" aria-hidden />
                  {fr.buvette.surLaTablette} : {fr.buvette.onglets[product.caisse_category]}
                </Badge>
              )
            )}
          </div>
        )}

        <div className="flex items-baseline justify-between rounded-md bg-muted/30 px-3 py-2">
          <span className="text-xs text-muted-foreground">{fr.buvette.inStock}</span>
          <span className="text-2xl font-bold">{product.quantity}</span>
        </div>

        <p className="text-[11px] text-muted-foreground">
          {fr.buvette.lastSync} :{' '}
          {product.last_synced_at ? formatDateTime(product.last_synced_at) : fr.buvette.neverSynced}
        </p>

        {canEdit && (
          <div className="mt-auto space-y-2">
            <Button size="sm" fullWidth onClick={() => onReappro(product)}>
              <PackagePlus className="h-3.5 w-3.5" />
              {fr.buvette.reappro.reapprovisionner}
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" fullWidth onClick={() => onModifier(product)}>
                <Edit3 className="h-3.5 w-3.5" />
                {fr.buvette.reappro.modifier}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={masque ? fr.buvette.afficherTablette : fr.buvette.masquerTablette}
                title={masque ? fr.buvette.afficherTablette : fr.buvette.masquerTablette}
                onClick={() => onToggleActive(product)}
              >
                {masque ? (
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Supprimer le produit"
                onClick={() => onDelete(product)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
