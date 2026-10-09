import { useEffect, useMemo, useState } from 'react';
import { Link2, PackagePlus, Search } from 'lucide-react';
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
import { ScannedBarcodeLine } from '@/components/scanner/ScannedProductPreview';
import { useUpdateBuvetteProduct } from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import type { BuvetteProduct } from '@/types/api';

interface CodeBarresInconnuModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  barcode: string | null;
  products: BuvetteProduct[];
  /** Le code est relié : la page ouvre ensuite le réappro de ce produit. */
  onAssocie: (product: BuvetteProduct) => void;
  /** Ouvre la création d'un nouveau produit à partir du code scanné. */
  onCreer: () => void;
}

/** Minuscules, sans accents : « cafe » retrouve « Café ». */
function normaliser(texte: string): string {
  return texte.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/**
 * Un code scanné n'est relié à aucun produit de la buvette.
 *
 * Les produits viennent de HelloAsso et n'ont jamais été scannés : le plus
 * souvent, le code appartient à un produit qui existe déjà. L'associer passe
 * en premier, et n'envoie que `{ barcode }` : la photo HelloAsso, le nom et le
 * prix restent intacts. Créer un nouveau produit reste possible, en second.
 */
export function CodeBarresInconnuModal({
  open,
  onOpenChange,
  barcode,
  products,
  onAssocie,
  onCreer,
}: CodeBarresInconnuModalProps) {
  const update = useUpdateBuvetteProduct();
  const toast = useToast();
  const [recherche, setRecherche] = useState('');

  useEffect(() => {
    if (open) setRecherche('');
  }, [open, barcode]);

  const sansCode = useMemo(() => products.filter((p) => !p.barcode), [products]);
  const filtres = useMemo(() => {
    const cle = normaliser(recherche);
    if (!cle) return sansCode;
    return sansCode.filter((p) => normaliser(p.name).includes(cle));
  }, [sansCode, recherche]);

  if (!barcode) return null;

  const associer = (p: BuvetteProduct) => {
    // Le code seul : rien d'autre ne doit être réécrit sur la fiche.
    update.mutate(
      { id: p.id, data: { barcode } },
      {
        onSuccess: (maj) => {
          toast.success(fr.buvette.codeBarres.associe(maj.name));
          onAssocie(maj);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.buvette.codeBarres.inconnuTitre}</DialogTitle>
          <DialogDescription>{fr.buvette.codeBarres.inconnuAide}</DialogDescription>
        </DialogHeader>

        <ScannedBarcodeLine barcode={barcode} />

        <section className="space-y-2" aria-labelledby="associer-titre">
          <h3 id="associer-titre" className="flex items-center gap-1.5 text-sm font-semibold">
            <Link2 className="h-4 w-4" aria-hidden />
            {fr.buvette.codeBarres.associerTitre}
          </h3>
          <p className="text-xs text-muted-foreground">{fr.buvette.codeBarres.associerAide}</p>

          {sansCode.length === 0 ? (
            <p className="text-sm text-muted-foreground">{fr.buvette.codeBarres.aucunSansCode}</p>
          ) : (
            <>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  type="search"
                  aria-label={fr.buvette.codeBarres.rechercher}
                  placeholder={fr.buvette.codeBarres.rechercher}
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                  className="pl-8"
                />
              </div>
              {filtres.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {fr.buvette.codeBarres.aucunResultat}
                </p>
              ) : (
                <ul className="max-h-72 space-y-1 overflow-y-auto rounded-md border border-border p-1">
                  {filtres.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => associer(p)}
                        disabled={update.isPending}
                        aria-label={fr.buvette.codeBarres.associerA(p.name)}
                        className="flex w-full items-center gap-3 rounded px-2 py-1.5 text-left hover:bg-accent disabled:opacity-50"
                      >
                        {p.image_url ? (
                          <img
                            src={p.image_url}
                            alt=""
                            className="h-10 w-10 flex-shrink-0 rounded object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <span
                            className="flex h-10 w-10 flex-shrink-0 items-center justify-center text-2xl"
                            aria-hidden
                          >
                            {p.emoji || '📦'}
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{p.name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {fr.buvette.onglets[p.caisse_category ?? 'aucun']}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>

        <section className="space-y-2 border-t border-border pt-4">
          <p className="text-xs text-muted-foreground">{fr.buvette.codeBarres.creerAide}</p>
          <Button type="button" variant="outline" onClick={onCreer} disabled={update.isPending}>
            <PackagePlus className="h-4 w-4" />
            {fr.buvette.codeBarres.creerTitre}
          </Button>
        </section>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            {fr.common.cancel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
