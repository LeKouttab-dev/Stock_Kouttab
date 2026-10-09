import { useEffect, useState } from 'react';
import { ScanLine, X } from 'lucide-react';
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
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  useDeleteBuvettePhoto,
  useUpdateBuvetteProduct,
  useUploadBuvettePhoto,
} from '@/api/endpoints/buvette';
import { OngletCaisseSelect } from '@/components/buvette/OngletCaisseSelect';
import { PhotoProduitField } from '@/components/buvette/PhotoProduitField';
import { BarcodeScanner } from '@/components/scanner/BarcodeScanner';
import {
  categorieVersOnglet,
  modifierBuvetteProductSchema,
  ongletVersCategorie,
  type ModifierBuvetteProductFormValues,
} from '@/lib/schemas/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { EMOJI_OPTIONS } from '@/lib/constants';
import { centsToEuros, eurosToCents } from '@/lib/money';
import type { BuvetteProduct, BuvetteProductUpdate } from '@/types/api';

interface ModifierProduitModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: BuvetteProduct | null;
}

/**
 * Fiche d'un produit : nom, prix de vente, seuil, emoji, photo, code-barres,
 * onglet de la tablette. Le stock n'y figure pas : il se change par un
 * réapprovisionnement (tracé, avec son prix d'achat) ou par un inventaire.
 *
 * Seuls les champs modifiés partent au serveur : renvoyer un nom ou un prix
 * inchangé marquerait le produit « modifié à la main », et la synchro HelloAsso
 * cesserait de le mettre à jour. Relier un code-barres ne doit rien écraser.
 */
/** Les champs dont la valeur diffère de la fiche actuelle, et eux seuls. */
function champsModifies(
  product: BuvetteProduct,
  values: ModifierBuvetteProductFormValues,
): BuvetteProductUpdate {
  const data: BuvetteProductUpdate = {};
  const nom = values.name.trim();
  if (nom !== product.name) data.name = nom;
  const prix = eurosToCents(values.price_euros);
  if (prix !== product.price_cents) data.price_cents = prix;
  if (values.seuil_alerte !== product.seuil_alerte) data.seuil_alerte = values.seuil_alerte;
  if (values.emoji !== (product.emoji || '📦')) data.emoji = values.emoji;
  const categorie = ongletVersCategorie(values.onglet_caisse);
  if (categorie !== (product.caisse_category ?? null)) data.caisse_category = categorie;
  // Vide = retirer le code : le serveur attend `null`.
  const code = values.barcode.trim() || null;
  if (code !== (product.barcode ?? null)) data.barcode = code;
  return data;
}

export function ModifierProduitModal({ open, onOpenChange, product }: ModifierProduitModalProps) {
  const update = useUpdateBuvetteProduct();
  const deposerPhoto = useUploadBuvettePhoto();
  const retirerPhoto = useDeleteBuvettePhoto();
  const [photo, setPhoto] = useState<File | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const toast = useToast();

  const form = useForm<ModifierBuvetteProductFormValues>({
    resolver: zodResolver(modifierBuvetteProductSchema),
    defaultValues: {
      name: '',
      price_euros: 0,
      seuil_alerte: 0,
      emoji: '📦',
      onglet_caisse: 'aucun',
      barcode: '',
    },
  });

  useEffect(() => {
    if (product) {
      setPhoto(null);
      form.reset({
        name: product.name,
        price_euros: centsToEuros(product.price_cents),
        seuil_alerte: product.seuil_alerte,
        emoji: product.emoji || '📦',
        onglet_caisse: categorieVersOnglet(product.caisse_category),
        barcode: product.barcode ?? '',
      });
    }
  }, [product, form]);

  const onSubmit = (values: ModifierBuvetteProductFormValues) => {
    if (!product) return;
    const data = champsModifies(product, values);

    const terminer = () => {
      // La photo part APRÈS la fiche : elle est facultative, et un échec de
      // son envoi ne doit pas faire perdre un prix corrigé.
      if (photo) {
        deposerPhoto.mutate(
          { id: product.id, file: photo },
          {
            onSuccess: () => {
              toast.success(fr.buvette.productUpdated);
              onOpenChange(false);
            },
          },
        );
        return;
      }
      toast.success(fr.buvette.productUpdated);
      onOpenChange(false);
    };

    if (Object.keys(data).length === 0) {
      terminer();
      return;
    }
    update.mutate({ id: product.id, data }, { onSuccess: terminer });
  };

  if (!product) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{fr.buvette.modifierProduit}</DialogTitle>
            <DialogDescription>{fr.buvette.modifierProduitAide}</DialogDescription>
          </DialogHeader>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <Alert variant="info">
              <AlertDescription>
                {fr.buvette.reappro.stockActuel} : <strong>{product.quantity}</strong>
              </AlertDescription>
            </Alert>

            <div className="space-y-1.5">
              <Label htmlFor="name" required>
                {fr.buvette.name}
              </Label>
              <Input
                id="name"
                hasError={Boolean(form.formState.errors.name)}
                {...form.register('name')}
              />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="price_euros" required>
                {fr.buvette.price}
              </Label>
              <Input
                id="price_euros"
                type="number"
                step="0.01"
                min={0}
                hasError={Boolean(form.formState.errors.price_euros)}
                {...form.register('price_euros', { valueAsNumber: true })}
              />
              {form.formState.errors.price_euros && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.price_euros.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="seuil_alerte" required>
                {fr.buvette.seuilAlerte}
              </Label>
              <Input
                id="seuil_alerte"
                type="number"
                min={0}
                hasError={Boolean(form.formState.errors.seuil_alerte)}
                {...form.register('seuil_alerte', { valueAsNumber: true })}
              />
              {form.formState.errors.seuil_alerte && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.seuil_alerte.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="emoji" required>
                {fr.buvette.emoji}
              </Label>
              <Input
                id="emoji"
                type="text"
                maxLength={4}
                hasError={Boolean(form.formState.errors.emoji)}
                {...form.register('emoji')}
              />
              <div className="flex flex-wrap gap-1.5 pt-1">
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
              {form.formState.errors.emoji && (
                <p className="text-xs text-destructive">{form.formState.errors.emoji.message}</p>
              )}
            </div>

            <PhotoProduitField
              photoActuelle={product.a_une_photo ? product.image_url : null}
              emoji={form.watch('emoji')}
              onFichier={setPhoto}
              onRetirer={() => retirerPhoto.mutate(product.id)}
              occupe={deposerPhoto.isPending || retirerPhoto.isPending}
            />

            <div className="space-y-1.5">
              <Label htmlFor="barcode">{fr.buvette.codeBarres.champ}</Label>
              <div className="flex gap-2">
                <Input
                  id="barcode"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder={fr.buvette.codeBarres.placeholder}
                  className="font-mono"
                  hasError={Boolean(form.formState.errors.barcode)}
                  {...form.register('barcode')}
                />
                <Button type="button" variant="outline" onClick={() => setScannerOpen(true)}>
                  <ScanLine className="h-4 w-4" />
                  {fr.buvette.codeBarres.scanner}
                </Button>
                {form.watch('barcode') && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() =>
                      form.setValue('barcode', '', { shouldDirty: true, shouldValidate: true })
                    }
                  >
                    <X className="h-4 w-4" />
                    {fr.buvette.codeBarres.retirer}
                  </Button>
                )}
              </div>
              {form.formState.errors.barcode && (
                <p className="text-xs text-destructive">{form.formState.errors.barcode.message}</p>
              )}
            </div>

            <OngletCaisseSelect
              value={form.watch('onglet_caisse')}
              onChange={(onglet) => form.setValue('onglet_caisse', onglet, { shouldDirty: true })}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {fr.common.cancel}
              </Button>
              <Button type="submit" loading={update.isPending || deposerPhoto.isPending}>
                {fr.common.update}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Le lecteur s'ouvre par-dessus la fiche ; le code lu remplit le champ. */}
      <BarcodeScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onDetected={(code) => {
          setScannerOpen(false);
          form.setValue('barcode', code, { shouldDirty: true, shouldValidate: true });
        }}
      />
    </>
  );
}
