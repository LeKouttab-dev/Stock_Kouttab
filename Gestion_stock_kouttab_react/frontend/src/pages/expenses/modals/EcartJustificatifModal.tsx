import { useEffect, useState } from 'react';
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
import { useEcarterJustificatif } from '@/api/endpoints/expenses';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Motif d'un écart de justificatif.
 *
 * Le motif est **montré au déposant** : c'est lui qui doit savoir quoi
 * redéposer. Sans explication, il renvoie la même pièce et le va-et-vient
 * recommence — d'où le champ obligatoire plutôt qu'une simple confirmation.
 *
 * Pas d'avertissement alarmant : le geste se défait, contrairement à la
 * suppression d'une note.
 */
export function EcartJustificatifModal({
  expenseId,
  fileId,
  onClose,
}: {
  expenseId: number;
  /** `null` quand aucune pièce n'est visée : la fenêtre reste fermée. */
  fileId: number | null;
  onClose: () => void;
}) {
  const ecarter = useEcarterJustificatif();
  const toast = useToast();
  const [motif, setMotif] = useState('');

  // Repartir d'un champ vide : un motif hérité de la pièce précédente serait
  // faux, et il est lu par quelqu'un.
  useEffect(() => {
    if (fileId !== null) setMotif('');
  }, [fileId]);

  const onConfirmer = () => {
    if (fileId === null) return;
    ecarter.mutate(
      { expenseId, fileId, motif: motif.trim() },
      {
        onSuccess: () => {
          toast.success(fr.expenses.justificatifEcarte);
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={fileId !== null} onOpenChange={(ouvert) => !ouvert && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.expenses.ecarterTitre}</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <p className="text-muted-foreground">{fr.expenses.ecarterAide}</p>

          <div>
            <Label required htmlFor="motif-ecart">
              {fr.expenses.ecarterMotif}
            </Label>
            <Input
              id="motif-ecart"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              placeholder={fr.expenses.ecarterMotifPlaceholder}
            />
            <p className="mt-1 text-xs text-muted-foreground">{fr.expenses.ecarterMotifAide}</p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {fr.common.cancel}
          </Button>
          <Button onClick={onConfirmer} disabled={!motif.trim()} loading={ecarter.isPending}>
            {fr.expenses.ecarter}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
