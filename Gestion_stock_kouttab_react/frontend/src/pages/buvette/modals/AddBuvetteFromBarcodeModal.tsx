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
import { useCreateBuvetteProduct } from '@/api/endpoints/buvette';
import {
  buvetteProductFromBarcodeSchema,
  type BuvetteProductFromBarcodeFormValues,
} from '@/lib/schemas/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import { EMOJI_OPTIONS } from '@/lib/constants';
import type { BarcodeLookupResponse } from '@/types/api';

interface AddBuvetteFromBarcodeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lookup: BarcodeLookupResponse | null;
}

function pickFirst(value: string | null | undefined): string {
  return (value ?? '').trim();
}

export function AddBuvetteFromBarcodeModal({
  open,
  onOpenChange,
  lookup,
}: AddBuvetteFromBarcodeModalProps) {
  const create = useCreateBuvetteProduct();
  const toast = useToast();

  const form = useForm<BuvetteProductFromBarcodeFormValues>({
    resolver: zodResolver(buvetteProductFromBarcodeSchema),
    defaultValues: {
      barcode: '',
      name: '',
      price_euros: 0,
      quantity: 0,
      seuil_alerte: 5,
      emoji: '🥤',
    },
  });

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
    form.reset({
      barcode: lookup.barcode,
      name: composedName,
      price_euros: 0,
      quantity: 0,
      seuil_alerte: 5,
      emoji: '🥤',
    });
  }, [open, lookup, form]);

  const onSubmit = async (values: BuvetteProductFromBarcodeFormValues) => {
    try {
      await create.mutateAsync({
        name: values.name,
        price_cents: eurosToCents(values.price_euros),
        quantity: values.quantity,
        seuil_alerte: values.seuil_alerte,
        emoji: values.emoji,
        helloasso_tier_id: null,
        barcode: values.barcode,
      });
      toast.success(fr.buvette.productCreated);
      onOpenChange(false);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  if (!lookup) return null;

  const off = lookup.openfoodfacts;
  const hasOff = Boolean(off && (off.name || off.image_url));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.scanner.newProductScanned}</DialogTitle>
          <DialogDescription>{fr.scanner.notFound}</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{fr.scanner.barcode} :</span>
          <span className="rounded bg-muted px-2 py-1 font-mono text-sm">{lookup.barcode}</span>
        </div>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="flex gap-3">
            {off?.image_url ? (
              <img
                src={off.image_url}
                alt={off.name ?? 'Produit'}
                className="h-20 w-20 flex-shrink-0 rounded-md border border-border object-cover"
              />
            ) : null}

            <div className="flex-1 space-y-1.5">
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
          </div>

          <div className="grid grid-cols-2 gap-3">
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
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
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
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="emoji" required>
                {fr.buvette.emoji}
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
              {fr.common.submit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
