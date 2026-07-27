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
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useUpdateBuvetteProduct } from '@/api/endpoints/buvette';
import {
  adjustBuvetteProductSchema,
  type AdjustBuvetteProductFormValues,
} from '@/lib/schemas/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { EMOJI_OPTIONS } from '@/lib/constants';
import { formatCents } from '@/lib/format';
import type { BuvetteProduct } from '@/types/api';

interface AdjustStockModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: BuvetteProduct | null;
}

export function AdjustStockModal({ open, onOpenChange, product }: AdjustStockModalProps) {
  const update = useUpdateBuvetteProduct();
  const toast = useToast();

  const form = useForm<AdjustBuvetteProductFormValues>({
    resolver: zodResolver(adjustBuvetteProductSchema),
    defaultValues: { quantity: 0, seuil_alerte: 0, emoji: '📦' },
  });

  useEffect(() => {
    if (product) {
      form.reset({
        quantity: product.quantity,
        seuil_alerte: product.seuil_alerte,
        emoji: product.emoji || '📦',
      });
    }
  }, [product, form]);

  const onSubmit = async (values: AdjustBuvetteProductFormValues) => {
    if (!product) return;
    try {
      await update.mutateAsync({ id: product.id, data: values });
      toast.success(fr.buvette.productUpdated);
      onOpenChange(false);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  if (!product) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.buvette.adjustStock}</DialogTitle>
          <DialogDescription>
            <strong>{product.name}</strong> — {formatCents(product.price_cents)}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <Alert variant="info">
            <AlertDescription>
              Quantité actuelle : <strong>{product.quantity}</strong>
            </AlertDescription>
          </Alert>

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

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {fr.common.cancel}
            </Button>
            <Button type="submit" loading={update.isPending}>
              {fr.common.update}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
