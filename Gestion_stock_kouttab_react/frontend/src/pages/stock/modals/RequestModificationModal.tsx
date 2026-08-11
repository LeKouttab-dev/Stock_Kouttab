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
import { useCreateStockModification } from '@/api/endpoints/stock';
import { requestModificationSchema, type RequestModificationFormValues } from '@/lib/schemas/stock';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import type { StockItem } from '@/types/api';

interface RequestModificationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: StockItem | null;
}

export function RequestModificationModal({
  open,
  onOpenChange,
  item,
}: RequestModificationModalProps) {
  const create = useCreateStockModification();
  const toast = useToast();

  const form = useForm<RequestModificationFormValues>({
    resolver: zodResolver(requestModificationSchema),
    defaultValues: { quantite_demandee: 0 },
  });

  useEffect(() => {
    if (item) form.reset({ quantite_demandee: item.quantite });
  }, [item, form]);

  const onSubmit = (values: RequestModificationFormValues) => {
    if (!item) return;
    create.mutate(
      { id_stock: item.id, quantite_demandee: values.quantite_demandee },
      {
        onSuccess: () => {
          toast.success(fr.stock.demandeEnvoyee);
          onOpenChange(false);
        },
      },
    );
  };

  if (!item) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.stock.demandeModif}</DialogTitle>
          <DialogDescription>
            Modification pour <strong>{item.nom}</strong>
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <Alert variant="info">
            <AlertDescription>
              {fr.stock.quantiteActuelle} : <strong>{item.quantite}</strong>
            </AlertDescription>
          </Alert>

          <div className="space-y-1.5">
            <Label htmlFor="quantite_demandee" required>
              {fr.stock.nouvelleQuantiteSouhaitee}
            </Label>
            <Input
              id="quantite_demandee"
              type="number"
              min={0}
              hasError={Boolean(form.formState.errors.quantite_demandee)}
              {...form.register('quantite_demandee', { valueAsNumber: true })}
            />
            {form.formState.errors.quantite_demandee && (
              <p className="text-xs text-destructive">
                {form.formState.errors.quantite_demandee.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {fr.stock.annuler}
            </Button>
            <Button type="submit" loading={create.isPending}>
              {fr.stock.envoyerDemande}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
