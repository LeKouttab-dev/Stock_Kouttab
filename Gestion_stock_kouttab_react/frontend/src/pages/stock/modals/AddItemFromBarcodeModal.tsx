import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
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
import { useCategories, useCreateStockItem, useSubcategories } from '@/api/endpoints/stock';
import {
  stockItemFromBarcodeSchema,
  type StockItemFromBarcodeFormValues,
} from '@/lib/schemas/stock';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { ScannedBarcodeLine, ScannedProductRow } from '@/components/scanner/ScannedProductPreview';
import { EMOJI_OPTIONS } from '@/lib/constants';
import type { BarcodeLookupResponse } from '@/types/api';

interface AddItemFromBarcodeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lookup: BarcodeLookupResponse | null;
}

function pickFirst(value: string | null | undefined): string {
  return (value ?? '').trim();
}

export function AddItemFromBarcodeModal({
  open,
  onOpenChange,
  lookup,
}: AddItemFromBarcodeModalProps) {
  const create = useCreateStockItem();
  const toast = useToast();
  const { data: categories = [] } = useCategories();

  const form = useForm<StockItemFromBarcodeFormValues>({
    resolver: zodResolver(stockItemFromBarcodeSchema),
    defaultValues: {
      barcode: '',
      nom: '',
      categorie: '',
      sous_categorie: null,
      quantite: 0,
      seuil_alerte: 5,
      emoji: '📦',
    },
  });

  const watchedCategorie = form.watch('categorie');
  const { data: subcategories = [] } = useSubcategories(watchedCategorie || undefined);

  useEffect(() => {
    if (!open || !lookup) return;
    const off = lookup.openfoodfacts;
    const offName = pickFirst(off?.name);
    const offBrand = pickFirst(off?.brand);
    const composedName = offName
      ? offBrand && !offName.toLowerCase().includes(offBrand.toLowerCase())
        ? `${offName} (${offBrand})`
        : offName
      : '';
    const offCategory = off?.categories?.[0] ?? '';
    const offSubcategory = off?.categories?.[1] ?? '';
    form.reset({
      barcode: lookup.barcode,
      nom: composedName,
      categorie: offCategory,
      sous_categorie: offSubcategory || null,
      quantite: 0,
      seuil_alerte: 5,
      emoji: '📦',
    });
  }, [open, lookup, form]);

  const onSubmit = async (values: StockItemFromBarcodeFormValues) => {
    try {
      await create.mutateAsync({
        nom: values.nom,
        categorie: values.categorie,
        sous_categorie: values.sous_categorie ?? null,
        quantite: values.quantite,
        seuil_alerte: values.seuil_alerte,
        emoji: values.emoji,
        barcode: values.barcode,
      });
      toast.success('Article créé', `${values.nom} ajouté au stock.`);
      onOpenChange(false);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  if (!lookup) return null;

  const off = lookup.openfoodfacts;
  const hasOff = Boolean(off && (off.name || off.image_url || off.categories.length));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.scanner.newProductScanned}</DialogTitle>
          <DialogDescription>{fr.scanner.notFound}</DialogDescription>
        </DialogHeader>

        <ScannedBarcodeLine barcode={lookup.barcode} />

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <ScannedProductRow lookup={lookup}>
            <Label htmlFor="nom" required>
              {fr.admin.nomArticle}
            </Label>
            <Input
              id="nom"
              hasError={Boolean(form.formState.errors.nom)}
              {...form.register('nom')}
            />
            {form.formState.errors.nom && (
              <p className="text-xs text-destructive">{form.formState.errors.nom.message}</p>
            )}
          </ScannedProductRow>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="categorie" required>
                {fr.admin.categorie}
              </Label>
              <Input
                id="categorie"
                list="categories-list"
                hasError={Boolean(form.formState.errors.categorie)}
                {...form.register('categorie')}
              />
              <datalist id="categories-list">
                {categories.map((c) => (
                  <option key={c.nom} value={c.nom} />
                ))}
              </datalist>
              {form.formState.errors.categorie && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.categorie.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="sous_categorie">{fr.admin.sousCategorie}</Label>
              <Input
                id="sous_categorie"
                list="subcategories-list"
                {...form.register('sous_categorie')}
              />
              <datalist id="subcategories-list">
                {subcategories.map((s) => (
                  <option key={s.id} value={s.nom_sous_categorie} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="quantite" required>
                {fr.admin.quantiteInitiale}
              </Label>
              <Input
                id="quantite"
                type="number"
                min={0}
                hasError={Boolean(form.formState.errors.quantite)}
                {...form.register('quantite', { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="seuil_alerte" required>
                {fr.stock.seuilAlerte}
              </Label>
              <Input
                id="seuil_alerte"
                type="number"
                min={0}
                hasError={Boolean(form.formState.errors.seuil_alerte)}
                {...form.register('seuil_alerte', { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="emoji" required>
                {fr.admin.emoji}
              </Label>
              <Input
                id="emoji"
                maxLength={4}
                hasError={Boolean(form.formState.errors.emoji)}
                {...form.register('emoji')}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {EMOJI_OPTIONS.slice(0, 18).map((e) => (
              <button
                key={e}
                type="button"
                onClick={() => form.setValue('emoji', e, { shouldDirty: true })}
                className="rounded border border-border px-1.5 py-1 text-base hover:bg-accent"
                aria-label={`Choisir ${e}`}
              >
                {e}
              </button>
            ))}
          </div>

          {hasOff && <p className="text-xs text-muted-foreground">{fr.scanner.enrichedFromOFF}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {fr.common.cancel}
            </Button>
            <Button type="submit" loading={create.isPending}>
              {fr.admin.ajouter}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
