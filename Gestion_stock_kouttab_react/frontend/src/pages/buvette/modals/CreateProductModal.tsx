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
  createBuvetteProductSchema,
  type CreateBuvetteProductFormValues,
} from '@/lib/schemas/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import { EMOJI_OPTIONS } from '@/lib/constants';

interface CreateProductModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateProductModal({ open, onOpenChange }: CreateProductModalProps) {
  const create = useCreateBuvetteProduct();
  const toast = useToast();

  const form = useForm<CreateBuvetteProductFormValues>({
    resolver: zodResolver(createBuvetteProductSchema),
    defaultValues: {
      name: '',
      price_euros: 0,
      quantity: 0,
      seuil_alerte: 5,
      emoji: '🥤',
      helloasso_tier_id: null,
    },
  });

  useEffect(() => {
    if (!open) form.reset();
  }, [open, form]);

  const onSubmit = (values: CreateBuvetteProductFormValues) => {
    create.mutate(
      {
        name: values.name,
        price_cents: eurosToCents(values.price_euros),
        quantity: values.quantity,
        seuil_alerte: values.seuil_alerte,
        emoji: values.emoji,
        helloasso_tier_id: values.helloasso_tier_id === undefined ? null : values.helloasso_tier_id,
      },
      {
        onSuccess: () => {
          toast.success(fr.buvette.productCreated);
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.buvette.createProduct}</DialogTitle>
          <DialogDescription>Créer manuellement un produit de buvette.</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
              {form.formState.errors.quantity && (
                <p className="text-xs text-destructive">{form.formState.errors.quantity.message}</p>
              )}
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

          <div className="space-y-1.5">
            <Label htmlFor="helloasso_tier_id">{fr.buvette.helloassoTierId}</Label>
            <Input
              id="helloasso_tier_id"
              type="number"
              min={1}
              placeholder="Laisser vide pour un produit local"
              {...form.register('helloasso_tier_id')}
            />
          </div>

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
