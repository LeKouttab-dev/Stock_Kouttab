import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Banknote,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Copy,
  Download,
  Trash2,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAllExpenses, useDeleteExpense, useValidateExpense } from '@/api/endpoints/expenses';
import { ReimbursementModal } from './modals/ReimbursementModal';
import { expenseValidateSchema, type ExpenseValidateFormValues } from '@/lib/schemas/expense';
import { EXPENSE_STATUS } from '@/lib/constants';
import type { Expense } from '@/types/api';
import { copyToClipboard } from '@/lib/utils';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
import { useToast } from '@/hooks/useToast';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { expenseTotal } from '@/lib/money';

/**
 * Écran comptable, en trois niveaux : **bénévole → ses notes → le détail**.
 *
 * La comptabilité ne rembourse pas une note, elle rembourse une personne : un
 * virement couvre plusieurs dépenses. Une liste plate de notes obligeait donc à
 * reconstituer de tête, en parcourant l'écran, ce que l'on devait à chacun.
 *
 * Le troisième niveau est l'ancienne vue, reprise telle quelle : elle porte la
 * validation, le RIB et les justificatifs, et n'avait aucune raison de changer.
 */
export function ValidateExpensesPage({ embarquee = false }: { embarquee?: boolean } = {}) {
  const { data: expenses = [], isLoading } = useAllExpenses();
  const [benevoleOuvert, setBenevoleOuvert] = useState<number | null>(null);

  // Regroupement local : `useAllExpenses` rapporte déjà toutes les notes avec
  // le nom du déposant. Un second appel au serveur pour les mêmes données
  // coûterait un aller-retour vers une base distante sans rien apprendre.
  const fiches = useMemo(() => groupeParBenevole(expenses), [expenses]);

  if (isLoading) return <LoadingSpinner fullPage />;

  return (
    <div className="space-y-4">
      {/* Titre masqué quand la page est rendue dans un onglet : la page hôte
          en porte déjà un, et deux titres l'un sous l'autre brouillent la
          lecture. */}
      {!embarquee && (
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ClipboardCheck className="h-6 w-6" aria-hidden />
            {fr.expenses.dashboardCompta}
          </h1>
          <p className="text-sm text-muted-foreground">Validation et remboursement des notes.</p>
        </div>
      )}

      {fiches.length === 0 ? (
        <EmptyState title={fr.expenses.aucuneATraiter} />
      ) : (
        <div className="space-y-3">
          {fiches.map((fiche) => (
            <FicheBenevole
              key={fiche.idUser}
              fiche={fiche}
              ouverte={benevoleOuvert === fiche.idUser}
              onToggle={() =>
                setBenevoleOuvert(benevoleOuvert === fiche.idUser ? null : fiche.idUser)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface FicheBenevoleData {
  idUser: number;
  nom: string;
  notes: Expense[];
  /** Notes « Approuvée » : celles qu'un versement peut solder aujourd'hui. */
  aRembourser: Expense[];
  totalDu: number;
}

function groupeParBenevole(expenses: Expense[]): FicheBenevoleData[] {
  const parUser = new Map<number, Expense[]>();
  for (const note of expenses) {
    const liste = parUser.get(note.id_user) ?? [];
    liste.push(note);
    parUser.set(note.id_user, liste);
  }

  const fiches = [...parUser.entries()].map(([idUser, notes]) => {
    const aRembourser = notes.filter((n) => n.status === 'Approuvée');
    return {
      idUser,
      nom: notes[0]?.user_full_name ?? '—',
      notes,
      aRembourser,
      totalDu: aRembourser.reduce((somme, n) => somme + expenseTotal(n), 0),
    };
  });

  // Ceux qui attendent un versement d'abord : c'est le travail du jour.
  fiches.sort((a, b) => b.aRembourser.length - a.aRembourser.length || a.nom.localeCompare(b.nom));
  return fiches;
}

function FicheBenevole({
  fiche,
  ouverte,
  onToggle,
}: {
  fiche: FicheBenevoleData;
  ouverte: boolean;
  onToggle: () => void;
}) {
  const [noteOuverte, setNoteOuverte] = useState<number | null>(null);
  const [selection, setSelection] = useState<number[]>([]);
  const [modaleOuverte, setModaleOuverte] = useState(false);

  const selectionnables = fiche.aRembourser.map((n) => n.id);
  const totalSelection = fiche.aRembourser
    .filter((n) => selection.includes(n.id))
    .reduce((somme, n) => somme + expenseTotal(n), 0);

  const basculer = (id: number) =>
    setSelection((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <Card>
      <CardContent className="p-0">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
        >
          <div className="flex min-w-0 items-center gap-2">
            {ouverte ? (
              <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            )}
            <span className="truncate font-medium">{fiche.nom}</span>
            <span className="flex-shrink-0 text-xs text-muted-foreground">
              {fiche.notes.length} note(s)
            </span>
          </div>
          {fiche.totalDu > 0 && (
            <span className="flex-shrink-0 rounded-full bg-terracotta/10 px-2.5 py-1 text-xs font-semibold text-terracotta">
              {fr.reimbursements.totalDu} : {formatCurrency(fiche.totalDu)}
            </span>
          )}
        </button>

        {ouverte && (
          <div className="border-t bg-muted/5">
            {selectionnables.length > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selection.length === selectionnables.length}
                    onChange={(e) => setSelection(e.target.checked ? selectionnables : [])}
                    className="h-4 w-4 rounded border-input"
                  />
                  {fr.reimbursements.toutSelectionner}
                </label>
                {/* Le bouton n'apparaît qu'une fois une note choisie : proposer
                    « Rembourser » sans sélection n'aurait aucun sens. */}
                {selection.length > 0 && (
                  <Button size="sm" onClick={() => setModaleOuverte(true)}>
                    <Banknote className="h-4 w-4" />
                    {fr.reimbursements.rembourser} — {selection.length}{' '}
                    {fr.reimbursements.selection} ({formatCurrency(totalSelection)})
                  </Button>
                )}
              </div>
            )}

            <ul className="divide-y">
              {fiche.notes.map((note) => {
                const total = expenseTotal(note);
                const ouvert = noteOuverte === note.id;
                const remboursable = note.status === 'Approuvée';
                return (
                  <li key={note.id}>
                    <div className="flex items-center gap-2 px-4 py-2 hover:bg-muted/20">
                      {/* Case décochée et inerte pour ce qui n'est pas encore
                          approuvé : l'API refuserait, autant le montrer. */}
                      <input
                        type="checkbox"
                        checked={selection.includes(note.id)}
                        onChange={() => basculer(note.id)}
                        disabled={!remboursable}
                        aria-label={`Sélectionner la note du ${formatDate(note.date_depense)}`}
                        className="h-4 w-4 flex-shrink-0 rounded border-input disabled:opacity-30"
                      />
                      <button
                        onClick={() => setNoteOuverte(ouvert ? null : note.id)}
                        className="flex min-w-0 flex-1 items-center justify-between gap-3 text-left"
                      >
                        <span className="truncate text-sm">
                          {formatDate(note.date_depense)} — {formatCurrency(total)}
                          {note.fournisseur ? ` — ${note.fournisseur}` : ''}
                        </span>
                        <StatusBadge status={note.status} />
                      </button>
                    </div>
                    {ouvert && <ValidateExpenseDetail expense={note} total={total} />}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardContent>

      <ReimbursementModal
        open={modaleOuverte}
        onOpenChange={(o) => {
          setModaleOuverte(o);
          if (!o) setSelection([]);
        }}
        nomBenevole={fiche.nom}
        expenseIds={selection}
        total={totalSelection}
      />
    </Card>
  );
}

interface DetailProps {
  expense: Expense;
  total: number;
}

function ValidateExpenseDetail({ expense, total }: DetailProps) {
  const validate = useValidateExpense();
  const remove = useDeleteExpense();
  const toast = useToast();
  const { download, downloadingId } = useDownloadAttachment();

  // Mêmes noms que ceux envoyés au comptable : pôle, événement, date, puis
  // suffixe `-2`, `-3` quand un dépôt porte plusieurs pièces.
  const comptaNames = useMemo(() => {
    const files = expense.files ?? [];
    if (files.length === 0) return [];
    return deduplicateFilenames(
      files.map((f) =>
        buildAttachmentFilename(
          [expense.pole, expense.evenement],
          expense.date_evenement || expense.date_depense || null,
          f.nom_fichier.split('.').pop() || 'pdf',
        ),
      ),
    );
  }, [expense]);

  const form = useForm<ExpenseValidateFormValues>({
    resolver: zodResolver(expenseValidateSchema),
    defaultValues: {
      status: expense.status,
      commentaires_compta: expense.commentaires_compta ?? '',
    },
  });

  const onValidate = (values: ExpenseValidateFormValues) => {
    validate.mutate(
      {
        id: expense.id,
        payload: { status: values.status, commentaires_compta: values.commentaires_compta },
      },
      { onSuccess: () => toast.success(fr.expenses.noteUpdated) },
    );
  };

  const onCopyRib = async () => {
    if (!expense.user_rib) return;
    await copyToClipboard(expense.user_rib);
    toast.success(fr.expenses.ribCopie);
  };

  const onDelete = () => {
    if (!confirm(fr.expenses.suppressionWarning)) return;
    remove.mutate(expense.id, { onSuccess: () => toast.success(fr.expenses.noteSupprimee) });
  };

  return (
    <div className="border-t bg-muted/10 px-4 py-4 space-y-4 text-sm">
      <div className="grid gap-2 md:grid-cols-2">
        <p>
          <strong>Rattachement :</strong> {expense.rattachement}
        </p>
        <p>
          <strong>Fournisseur :</strong> {expense.fournisseur ?? '—'}
        </p>
        <p>
          <strong>Nature :</strong> {expense.nature_charge ?? '—'}
        </p>
        <p>
          <strong>{fr.expenses.commentaireUtilisateur} :</strong> {expense.commentaires ?? '—'}
        </p>
      </div>

      <div className="rounded-md border bg-background px-3 py-2 space-y-1">
        <p>
          {fr.expenses.montantBrut} : <strong>{formatCurrency(expense.montant)}</strong>
        </p>
        <p>
          Remboursement déjà émis :{' '}
          <strong>-{formatCurrency(expense.remboursement_deja_emis)}</strong>
        </p>
        <p>
          Remise : <strong>-{formatCurrency(expense.remise)}</strong>
        </p>
        <p className="text-base">
          {fr.expenses.totalARembourser} : <strong>{formatCurrency(total)}</strong>
        </p>
      </div>

      {expense.user_rib ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <Label>{fr.expenses.ribUtilisateur}</Label>
            <Input value={expense.user_rib} disabled />
          </div>
          <Button variant="outline" onClick={onCopyRib}>
            <Copy className="h-4 w-4" />
            {fr.expenses.copierRib}
          </Button>
        </div>
      ) : (
        <Alert variant="warning">
          <AlertDescription>{fr.expenses.ribAbsent}</AlertDescription>
        </Alert>
      )}

      {expense.files && expense.files.length > 0 ? (
        <div className="space-y-1">
          <p className="font-medium">Justificatifs :</p>
          <ul className="space-y-1">
            {expense.files.map((f, index) => {
              // Le comptable reçoit la pièce sous sa nomenclature ; l'afficher
              // ici sous le nom brut du téléphone (`_p9.png`) l'obligerait à
              // faire le rapprochement de tête. L'extension reste celle du
              // fichier réellement servi : annoncer `.pdf` pour télécharger un
              // PNG tromperait sur le contenu.
              const nomComptable = comptaNames[index] ?? f.nom_fichier;
              return (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() =>
                      download(`/expenses/${expense.id}/files/${f.id}`, nomComptable, f.id)
                    }
                    disabled={downloadingId === f.id}
                    className="inline-flex items-center gap-1 text-primary hover:underline disabled:opacity-60"
                  >
                    <Download className="h-3.5 w-3.5" />
                    {nomComptable}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <Alert variant="warning">
          <AlertDescription>{fr.expenses.aucunTicket}</AlertDescription>
        </Alert>
      )}

      <form
        onSubmit={form.handleSubmit(onValidate)}
        className="space-y-3 rounded-md border bg-background p-3"
      >
        <div>
          <Label>{fr.expenses.commentaireCompta}</Label>
          <Textarea rows={2} {...form.register('commentaires_compta')} />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <Label>{fr.expenses.changerStatut}</Label>
            <Select
              value={form.watch('status')}
              onValueChange={(v) => form.setValue('status', v as (typeof EXPENSE_STATUS)[number])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXPENSE_STATUS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" loading={validate.isPending}>
            {fr.common.update}
          </Button>
        </div>
      </form>

      {expense.status === 'Remboursée' && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 space-y-2">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Trash2 className="h-4 w-4" aria-hidden />
            {fr.expenses.zoneSuppression}
          </p>
          <p className="text-xs text-muted-foreground">{fr.expenses.suppressionWarning}</p>
          <Button variant="destructive" size="sm" onClick={onDelete} loading={remove.isPending}>
            <Trash2 className="h-4 w-4" />
            {fr.expenses.supprimer}
          </Button>
        </div>
      )}
    </div>
  );
}
