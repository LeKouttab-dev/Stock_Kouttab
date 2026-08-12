import { useEffect, useState } from 'react';
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
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCreateReimbursement, useReimbursementOptions } from '@/api/endpoints/reimbursements';
import { useToast } from '@/hooks/useToast';
import { formatCurrency } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

interface ReimbursementModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Bénévole remboursé — toutes les notes lui appartiennent. */
  nomBenevole: string;
  expenseIds: number[];
  /** Montant net des notes sélectionnées, tel qu'affiché dans la liste. */
  total: number;
}

/**
 * Enregistrement d'un versement soldant plusieurs notes.
 *
 * Les valeurs sont pré-remplies avec ce que l'association fait dans l'immense
 * majorité des cas (virement Wise, approuvé par DTC) : le comptable valide sans
 * rien saisir, et ne corrige que l'exception.
 */
export function ReimbursementModal({
  open,
  onOpenChange,
  nomBenevole,
  expenseIds,
  total,
}: ReimbursementModalProps) {
  const { data: options } = useReimbursementOptions();
  const create = useCreateReimbursement();
  const toast = useToast();

  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [moyen, setMoyen] = useState('');
  const [etablissement, setEtablissement] = useState('');
  const [approuvePar, setApprouvePar] = useState('');
  const [commentaire, setCommentaire] = useState('');

  // Les valeurs par défaut viennent du serveur : les recopier ici les ferait
  // diverger de ce que l'API accepte au premier changement.
  useEffect(() => {
    if (!open || !options) return;
    setDate(new Date().toISOString().slice(0, 10));
    setMoyen(options.moyen_defaut);
    setEtablissement(options.etablissement_defaut);
    setApprouvePar(options.approbateur_defaut);
    setCommentaire('');
  }, [open, options]);

  const valider = () => {
    create.mutate(
      {
        expense_ids: expenseIds,
        date_remboursement: date,
        moyen,
        etablissement,
        approuve_par: approuvePar,
        commentaire: commentaire.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success(fr.reimbursements.enregistre, `${nomBenevole} — ${formatCurrency(total)}`);
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.reimbursements.titreModale}</DialogTitle>
          <DialogDescription>
            {nomBenevole} — {expenseIds.length} {fr.reimbursements.notesSoldees} —{' '}
            <strong>{formatCurrency(total)}</strong>
          </DialogDescription>
        </DialogHeader>

        {/* Le remboursement est définitif : les notes passent à « Remboursée »,
            statut terminal du workflow, et le justificatif part à la
            comptabilité. Autant le dire avant, pas après. */}
        <Alert>
          <AlertDescription className="text-xs">{fr.reimbursements.avertissement}</AlertDescription>
        </Alert>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="date_remb" required>
              {fr.reimbursements.emisLe}
            </Label>
            <Input
              id="date_remb"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label required>{fr.reimbursements.moyen}</Label>
            <Select value={moyen} onValueChange={setMoyen}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(options?.moyens ?? []).map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label required>{fr.reimbursements.etablissement}</Label>
            <Select value={etablissement} onValueChange={setEtablissement}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(options?.etablissements ?? []).map((e) => (
                  <SelectItem key={e} value={e}>
                    {e}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="approuve_par" required>
              {fr.reimbursements.approuvePar}
            </Label>
            <Input
              id="approuve_par"
              value={approuvePar}
              onChange={(e) => setApprouvePar(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="commentaire_remb">{fr.reimbursements.commentaire}</Label>
          <Textarea
            id="commentaire_remb"
            rows={2}
            value={commentaire}
            onChange={(e) => setCommentaire(e.target.value)}
            placeholder={fr.reimbursements.commentairePlaceholder}
          />
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.cancel}
          </Button>
          <Button
            type="button"
            onClick={valider}
            loading={create.isPending}
            disabled={!moyen || !etablissement || !approuvePar.trim() || !date}
          >
            {fr.reimbursements.confirmer}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
