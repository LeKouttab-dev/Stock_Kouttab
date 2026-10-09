import { useEffect, useState, type FormEvent } from 'react';
import { RotateCcw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useReapproBuvetteProduct } from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import {
  centsVersSaisie,
  lireEuros,
  lireQuantite,
  PALIERS_REAPPRO,
  REAPPRO_MAX,
} from '@/lib/buvette';
import { formatCents } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import type { BuvetteProduct } from '@/types/api';

interface ReapproModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: BuvetteProduct | null;
}

/**
 * Réapprovisionnement d'un produit : la quantité apportée s'AJOUTE au stock
 * (15 en stock + 60 apportées = 75). Le prix d'achat unitaire est obligatoire,
 * pré-rempli avec le dernier prix saisi pour ce produit.
 */
export function ReapproModal({ open, onOpenChange, product }: ReapproModalProps) {
  const reappro = useReapproBuvetteProduct();
  const toast = useToast();
  const t = fr.buvette.reappro;

  const [quantite, setQuantite] = useState(0);
  const [prix, setPrix] = useState('');
  const [commentaire, setCommentaire] = useState('');
  const [tente, setTente] = useState(false);

  // Chaque ouverture repart d'une saisie vierge, prix pré-rempli.
  useEffect(() => {
    if (open && product) {
      setQuantite(0);
      setPrix(centsVersSaisie(product.dernier_prix_achat_cents));
      setCommentaire('');
      setTente(false);
    }
  }, [open, product]);

  if (!product) return null;

  const prixEuros = lireEuros(prix);
  const prixCents = prixEuros === null ? null : eurosToCents(prixEuros);
  const quantiteValide = quantite >= 1 && quantite <= REAPPRO_MAX;
  const totalCents = prixCents === null ? null : prixCents * quantite;

  const ajouter = (n: number) => setQuantite((q) => Math.min(REAPPRO_MAX, q + n));

  const valider = (e: FormEvent) => {
    e.preventDefault();
    setTente(true);
    if (!quantiteValide || prixCents === null) return;
    const note = commentaire.trim();
    reappro.mutate(
      {
        id: product.id,
        quantite,
        prix_achat_unitaire_cents: prixCents,
        commentaire: note === '' ? null : note,
      },
      {
        onSuccess: ({ produit }) => {
          toast.success(t.succes(produit.name), t.stock(produit.quantity));
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.titre(product.name)}</DialogTitle>
          <DialogDescription>{t.aide}</DialogDescription>
        </DialogHeader>

        <form onSubmit={valider} className="space-y-4" noValidate>
          <div className="flex items-baseline justify-between rounded-md bg-muted/30 px-3 py-2">
            <span className="text-sm text-muted-foreground">{t.stockActuel}</span>
            <span className="text-2xl font-bold" data-testid="reappro-stock-actuel">
              {product.quantity}
            </span>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reappro-quantite" required>
              {t.quantite}
            </Label>
            <div className="flex gap-2">
              <Input
                id="reappro-quantite"
                inputMode="numeric"
                value={quantite === 0 ? '' : String(quantite)}
                placeholder="0"
                hasError={tente && !quantiteValide}
                onChange={(e) => setQuantite(Math.min(REAPPRO_MAX, lireQuantite(e.target.value)))}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t.remiseAZero}
                title={t.remiseAZero}
                onClick={() => setQuantite(0)}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-5 gap-1 pt-1">
              {PALIERS_REAPPRO.map((n) => (
                <Button
                  key={n}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="px-0"
                  aria-label={t.ajouter(n)}
                  title={t.ajouter(n)}
                  onClick={() => ajouter(n)}
                >
                  +{n}
                </Button>
              ))}
            </div>
            {tente && !quantiteValide && (
              <p className="text-xs text-destructive">{t.quantiteInvalide}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reappro-prix" required>
              {t.prix}
            </Label>
            <Input
              id="reappro-prix"
              inputMode="decimal"
              value={prix}
              placeholder="0,00"
              hasError={tente && prixCents === null}
              onChange={(e) => setPrix(e.target.value)}
            />
            {tente && prixCents === null ? (
              <p className="text-xs text-destructive">{t.prixObligatoire}</p>
            ) : (
              product.dernier_prix_achat_cents !== null &&
              product.dernier_prix_achat_cents !== undefined && (
                <p className="text-xs text-muted-foreground">{t.prixAide}</p>
              )
            )}
          </div>

          <div className="space-y-1 rounded-md border border-border px-3 py-2 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t.total}</span>
              <span className="font-semibold" data-testid="reappro-total">
                {totalCents === null ? '…' : formatCents(totalCents)}
              </span>
            </div>
            <p className="font-medium" data-testid="reappro-stock-apres">
              {t.stockApres(product.quantity, quantite)}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reappro-commentaire">{t.commentaire}</Label>
            <Textarea
              id="reappro-commentaire"
              rows={2}
              maxLength={255}
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {fr.common.cancel}
            </Button>
            <Button type="submit" loading={reappro.isPending}>
              {t.valider}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
