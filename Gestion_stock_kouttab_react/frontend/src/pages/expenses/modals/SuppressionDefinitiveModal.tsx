import { useEffect, useState } from 'react';
import { Trash2, TriangleAlert } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useSupprimerDefinitivement } from '@/api/endpoints/expenses';
import { useToast } from '@/hooks/useToast';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import type { Expense } from '@/types/api';

/**
 * Confirmation d'une suppression irréversible.
 *
 * Une fenêtre plutôt qu'un `confirm()` du navigateur : il faut de la place pour
 * dire ce que le geste emporte, rappeler qu'il ne concerne pas les notes
 * réelles, et exiger un motif — la seule trace qui restera de la note.
 *
 * Le bouton reste inerte tant que le motif est vide. Ce n'est pas une formalité
 * : quelqu'un qui doit écrire pourquoi il supprime relit ce qu'il supprime.
 */
export function SuppressionDefinitiveModal({
  expense,
  open,
  onOpenChange,
}: {
  expense: Expense;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const supprimer = useSupprimerDefinitivement();
  const toast = useToast();
  const [motif, setMotif] = useState('');

  // Repartir d'un champ vide à chaque ouverture : un motif hérité de la note
  // précédente serait faux, et il finit dans le journal.
  useEffect(() => {
    if (open) setMotif('');
  }, [open]);

  const onConfirmer = () => {
    supprimer.mutate(
      { id: expense.id, motif: motif.trim() },
      {
        onSuccess: () => {
          toast.success(fr.expenses.noteSupprimee);
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TriangleAlert className="h-5 w-5 text-destructive" aria-hidden />
            {fr.expenses.suppressionTitre}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <p className="rounded-md border bg-muted/30 px-3 py-2">
            {formatDate(expense.date_depense)} — {formatCurrency(expense.montant)}
            {expense.fournisseur ? ` — ${expense.fournisseur}` : ''}
            {expense.user_full_name ? ` — ${expense.user_full_name}` : ''}
          </p>

          <Alert variant="destructive">
            <AlertDescription>{fr.expenses.suppressionAvertissement}</AlertDescription>
          </Alert>

          <Alert variant="warning">
            <AlertDescription>{fr.expenses.suppressionUsage}</AlertDescription>
          </Alert>

          <div>
            <Label required htmlFor="motif-suppression">
              {fr.expenses.suppressionMotif}
            </Label>
            <Input
              id="motif-suppression"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              placeholder={fr.expenses.suppressionMotifPlaceholder}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {fr.expenses.suppressionMotifAide}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.cancel}
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirmer}
            disabled={!motif.trim()}
            loading={supprimer.isPending}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            {fr.expenses.suppressionConfirmer}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
