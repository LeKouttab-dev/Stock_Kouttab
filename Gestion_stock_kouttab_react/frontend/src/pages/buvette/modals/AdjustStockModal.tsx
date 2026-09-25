import { useEffect, useState } from 'react';
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
import {
  adjustBuvetteProductSchema,
  categorieVersOnglet,
  ongletVersCategorie,
  type AdjustBuvetteProductFormValues,
} from '@/lib/schemas/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { EMOJI_OPTIONS } from '@/lib/constants';
import { centsToEuros, eurosToCents } from '@/lib/money';
import type { BuvetteProduct } from '@/types/api';

interface AdjustStockModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: BuvetteProduct | null;
}

export function AdjustStockModal({ open, onOpenChange, product }: AdjustStockModalProps) {
  const update = useUpdateBuvetteProduct();
  const deposerPhoto = useUploadBuvettePhoto();
  const retirerPhoto = useDeleteBuvettePhoto();
  const [photo, setPhoto] = useState<File | null>(null);
  const toast = useToast();

  const form = useForm<AdjustBuvetteProductFormValues>({
    resolver: zodResolver(adjustBuvetteProductSchema),
    defaultValues: {
      name: '',
      price_euros: 0,
      quantity: 0,
      seuil_alerte: 0,
      emoji: '📦',
      onglet_caisse: 'aucun',
    },
  });

  useEffect(() => {
    if (product) {
      setPhoto(null);
      form.reset({
        name: product.name,
        price_euros: centsToEuros(product.price_cents),
        quantity: product.quantity,
        seuil_alerte: product.seuil_alerte,
        emoji: product.emoji || '📦',
        onglet_caisse: categorieVersOnglet(product.caisse_category),
      });
    }
  }, [product, form]);

  const onSubmit = ({ onglet_caisse, price_euros, ...values }: AdjustBuvetteProductFormValues) => {
    if (!product) return;
    update.mutate(
      {
        id: product.id,
        data: {
          ...values,
          price_cents: eurosToCents(price_euros),
          caisse_category: ongletVersCategorie(onglet_caisse),
        },
      },
      {
        onSuccess: () => {
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
        },
      },
    );
  };

  if (!product) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.buvette.adjustStock}</DialogTitle>
          <DialogDescription>
            Nom, prix, stock, photo et onglet de la caisse.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <Alert variant="info">
            <AlertDescription>
              Quantité actuelle : <strong>{product.quantity}</strong>
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
              <p className="text-xs text-destructive">{form.formState.errors.price_euros.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="quantity" required>
              {fr.buvette.quantity}
            </Label>
            <Input
              id="quantity"
              type="number"
              min={0}
              hasError={Boolean(form.formState.errors.quantity)}
              {...form.register('quantity', { valueAsNumber: true })}
            />
            {form.formState.errors.quantity && (
              <p className="text-xs text-destructive">{form.formState.errors.quantity.message}</p>
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
  );
}
