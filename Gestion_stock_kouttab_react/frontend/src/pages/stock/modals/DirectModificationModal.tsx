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
import { useUpdateStockItem } from '@/api/endpoints/stock';
import { directModificationSchema, type DirectModificationFormValues } from '@/lib/schemas/stock';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import type { StockItem } from '@/types/api';

interface DirectModificationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: StockItem | null;
}

export function DirectModificationModal({
  open,
  onOpenChange,
  item,
}: DirectModificationModalProps) {
  const update = useUpdateStockItem();
  const toast = useToast();

  const form = useForm<DirectModificationFormValues>({
    resolver: zodResolver(directModificationSchema),
    defaultValues: { quantite: 0 },
  });

  useEffect(() => {
    if (item) form.reset({ quantite: item.quantite });
  }, [item, form]);

  const onSubmit = async (values: DirectModificationFormValues) => {
    if (!item) return;
    if (values.quantite === item.quantite) {
      toast.warning('Aucune modification', 'La quantité est inchangée.');
      return;
    }
    try {
      await update.mutateAsync({ id: item.id, data: { quantite: values.quantite } });
      toast.success('Quantité mise à jour', `${item.quantite} → ${values.quantite}`);
      onOpenChange(false);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  if (!item) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.stock.modifDirecte}</DialogTitle>
          <DialogDescription>
            Modification directe pour <strong>{item.nom}</strong>
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <Alert variant="info">
            <AlertDescription>
              {fr.stock.quantiteActuelle} : <strong>{item.quantite}</strong>
            </AlertDescription>
          </Alert>

          <div className="space-y-1.5">
            <Label htmlFor="quantite" required>
              {fr.stock.nouvelleQuantite}
            </Label>
            <Input
              id="quantite"
              type="number"
              min={0}
              hasError={Boolean(form.formState.errors.quantite)}
              {...form.register('quantite', { valueAsNumber: true })}
            />
            {form.formState.errors.quantite && (
              <p className="text-xs text-destructive">{form.formState.errors.quantite.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {fr.stock.annuler}
            </Button>
            <Button type="submit" loading={update.isPending}>
              {fr.stock.mettreAJour}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
