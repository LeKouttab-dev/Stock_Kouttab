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
  Archive,
  Undo2,
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
import {
  useAllExpenses,
  useArchiveExpense,
  useRestoreExpense,
  useValidateExpense,
} from '@/api/endpoints/expenses';
import { ReimbursementModal } from './modals/ReimbursementModal';
import {
  reimbursementDocumentPath,
  useRemboursementParNote,
} from '@/api/endpoints/reimbursements';
import { expenseValidateSchema, type ExpenseValidateFormValues } from '@/lib/schemas/expense';
import { EXPENSE_STATUS, normaliserStatut } from '@/lib/constants';
import type { Expense, Reimbursement } from '@/types/api';
import { cn, copyToClipboard } from '@/lib/utils';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
import { useToast } from '@/hooks/useToast';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { expenseTotal } from '@/lib/money';

/**
 * Les vues de l'écran comptable.
 *
 * Sans elles, l'onglet empilait tout — en attente, approuvé, déjà remboursé —
 * dans la fiche de chaque bénévole. Le travail du jour se noyait dans les mois
 * précédents, et rien ne permettait de consulter l'historique en tant que tel.
 */
const VUES = {
  // « À traiter » = ce qui demande une action de la comptabilité : valider, ou
  // payer. Cette vue ne montrait que les notes « En attente », si bien que le
  // bouton « Rembourser » — qui n'apparaît qu'en présence de notes approuvées —
  // était invisible sur l'écran d'accueil. Il fallait deviner qu'il fallait
  // changer de filtre pour pouvoir payer.
  traiter: {
    libelle: fr.expenses.filtreATraiter,
    garde: (n: Expense) => n.status === 'En attente' || n.status === 'Approuvée',
  },
  approuvees: {
    libelle: fr.expenses.filtreApprouvees,
    garde: (n: Expense) => n.status === 'Approuvée',
  },
  remboursees: {
    libelle: fr.expenses.filtreRemboursees,
    garde: (n: Expense) => n.status === 'Remboursée',
  },
  archivees: { libelle: fr.expenses.filtreArchivees, garde: (n: Expense) => Boolean(n.archived_at) },
  toutes: { libelle: fr.expenses.filtreToutes, garde: () => true },
} as const;

type Vue = keyof typeof VUES;

/** Les archives ne remontent que dans leur propre vue, et dans « Toutes ». */
function visible(note: Expense, vue: Vue): boolean {
  if (note.archived_at && vue !== 'archivees' && vue !== 'toutes') return false;
  return VUES[vue].garde(note);
}

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
  // Ouverture sur le travail du jour : c'est la raison d'être de l'onglet.
  const [vue, setVue] = useState<Vue>('traiter');

  const comptes = useMemo(
    () =>
      Object.fromEntries(
        (Object.keys(VUES) as Vue[]).map((v) => [v, expenses.filter((n) => visible(n, v)).length]),
      ) as Record<Vue, number>,
    [expenses],
  );

  // Regroupement local : `useAllExpenses` rapporte déjà toutes les notes avec
  // le nom du déposant. Un second appel au serveur pour les mêmes données
  // coûterait un aller-retour vers une base distante sans rien apprendre.
  const fiches = useMemo(() => groupeParBenevole(expenses, vue), [expenses, vue]);

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

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filtrer les notes">
        {(Object.keys(VUES) as Vue[]).map((v) => (
          <button
            key={v}
            type="button"
            role="tab"
            aria-selected={vue === v}
            onClick={() => setVue(v)}
            className={cn(
              'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
              vue === v
                ? 'border-terracotta bg-terracotta text-cream-50'
                : 'border-input bg-background hover:bg-muted/40',
            )}
          >
            {VUES[v].libelle}
            {/* Le compte figure sur chaque filtre : c'est ce qui dit d'un coup
                d'œil s'il reste du travail, sans avoir à y entrer. */}
            <span className="ml-1.5 opacity-70">{comptes[v]}</span>
          </button>
        ))}
      </div>

      {fiches.length === 0 ? (
        <EmptyState
          title={vue === 'traiter' ? fr.expenses.aucuneATraiter : fr.expenses.aucuneDansFiltre}
        />
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

/**
 * Regroupe par bénévole, en séparant deux choses qu'on avait confondues.
 *
 * Ce qui est **affiché** dépend du filtre choisi ; ce qui est **dû** n'en dépend
 * pas. Calculer le total sur les seules notes visibles faisait tomber « Reste à
 * rembourser » à zéro dès qu'on regardait un autre onglet, et retirait les cases
 * à cocher avec lui — la somme due à quelqu'un ne change pas selon l'écran qu'on
 * consulte.
 */
function groupeParBenevole(toutes: Expense[], vue: Vue): FicheBenevoleData[] {
  const parUser = new Map<number, Expense[]>();
  for (const note of toutes) {
    const liste = parUser.get(note.id_user) ?? [];
    liste.push(note);
    parUser.set(note.id_user, liste);
  }

  const fiches = [...parUser.entries()]
    .map(([idUser, notesDuBenevole]) => {
      // Une note archivée est sortie du circuit : la proposer au paiement
      // ferait payer deux fois ce que la comptabilité avait rangé.
      const aRembourser = notesDuBenevole.filter(
        (n) => n.status === 'Approuvée' && !n.archived_at,
      );
      return {
        idUser,
        nom: notesDuBenevole[0]?.user_full_name ?? '—',
        notes: notesDuBenevole.filter((n) => visible(n, vue)),
        aRembourser,
        totalDu: aRembourser.reduce((somme, n) => somme + expenseTotal(n), 0),
      };
    })
    // Un bénévole dont aucune note n'entre dans le filtre n'a rien à y faire.
    .filter((fiche) => fiche.notes.length > 0);

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

  // On ne coche que ce qui est à l'écran : `aRembourser` porte tout ce qui est
  // dû — c'est ce que la pastille annonce — mais sélectionner une note que le
  // filtre courant masque reviendrait à payer à l'aveugle.
  const payables = fiche.notes.filter((n) => n.status === 'Approuvée' && !n.archived_at);
  const selectionnables = payables.map((n) => n.id);
  const totalSelection = payables
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
  const archiver = useArchiveExpense();
  const restaurer = useRestoreExpense();
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

  const versement = useRemboursementParNote().get(expense.id);
  const statutCanonique = normaliserStatut(expense.status, EXPENSE_STATUS) ?? 'En attente';
  const statutInitial =
    statutCanonique === 'Remboursée' && !versement ? 'Approuvée' : statutCanonique;
  // Une note soldée par un versement est verrouillée : son justificatif porte
  // le montant et la date, y revenir le contredirait. Seul le commentaire reste
  // modifiable.
  const verrouillee = statutCanonique === 'Remboursée' && Boolean(versement);

  const form = useForm<ExpenseValidateFormValues>({
    resolver: zodResolver(expenseValidateSchema),
    defaultValues: {
      // Pour une note marquée « Remboursée » sans versement, le formulaire
      // s'ouvre sur « Approuvée » — la valeur qu'il va réellement envoyer.
      //
      // L'écran affichait auparavant « Approuvée » tout en gardant « Remboursée »
      // dans le formulaire : cliquer sur « Mettre à jour » sans toucher à la
      // liste renvoyait le statut inchangé, le serveur l'acceptait comme un
      // non-changement, et le message « Statut mis à jour » s'affichait alors
      // que rien n'avait bougé. Un affichage ne doit jamais contredire ce qui
      // sera soumis.
      //
      // `normaliserStatut` couvre les notes héritées de la version Streamlit,
      // dont le statut s'écrit sans accents : le schéma du formulaire les
      // rejetait, et « Mettre à jour » ne partait jamais, en silence.
      status: statutInitial,
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

  const onArchiver = () => {
    archiver.mutate(expense.id, { onSuccess: () => toast.success(fr.expenses.noteArchivee) });
  };

  const onRestaurer = () => {
    restaurer.mutate(expense.id, { onSuccess: () => toast.success(fr.expenses.noteRestauree) });
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
          {/* Le document de la banque, quand le bénévole l'a déposé : l'IBAN
              ci-contre suffit au virement, celui-ci sert de preuve au dossier. */}
          {expense.user_rib_document_nom && (
            <Button
              variant="outline"
              onClick={() =>
                download(
                  `/users/${expense.id_user}/rib-document`,
                  expense.user_rib_document_nom as string,
                )
              }
            >
              <Download className="h-4 w-4" />
              {fr.expenses.ribDocumentTelecharger}
            </Button>
          )}
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

      {/* Une note soldée ne se pilote plus par la liste des statuts : elle
          porte son versement, ou signale qu'il manque. */}
      {statutCanonique === 'Remboursée' && <BlocVersement versement={versement} />}

      <form
        onSubmit={form.handleSubmit(onValidate)}
        className="space-y-3 rounded-md border bg-background p-3"
      >
        <div>
          <Label>{fr.expenses.commentaireCompta}</Label>
          <Textarea rows={2} {...form.register('commentaires_compta')} />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className={cn('flex-1 min-w-[200px]', verrouillee && 'hidden')}>
            <Label>{fr.expenses.changerStatut}</Label>
            <Select
              value={form.watch('status')}
              onValueChange={(v) => form.setValue('status', v as (typeof EXPENSE_STATUS)[number])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {/* « Remboursée » ne figure pas dans la liste : elle se constate,
                    elle ne se déclare pas. La proposer ici laissait marquer une
                    note payée sans enregistrer le versement — donc sans
                    justificatif, sans rien dans l'onglet « Remboursements », et
                    dans un état terminal impossible à corriger. Le bouton
                    « Rembourser », lui, fait les deux. */}
                {EXPENSE_STATUS.filter((s) => s !== 'Remboursée').map((s) => (
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

      {/* Rangement, et non destruction : plus aucune confirmation alarmante,
          puisque le geste se défait. */}
      {expense.archived_at ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-background p-3">
          <p className="text-xs text-muted-foreground">
            {fr.expenses.archiveePar
              .replace('{date}', formatDate(expense.archived_at))
              .replace('{qui}', expense.archived_by_name ?? '—')}
          </p>
          <Button variant="outline" size="sm" onClick={onRestaurer} loading={restaurer.isPending}>
            <Undo2 className="h-4 w-4" />
            {fr.expenses.restaurer}
          </Button>
        </div>
      ) : (
        expense.status === 'Remboursée' && (
          <div className="rounded-md border bg-background p-3 space-y-2">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Archive className="h-4 w-4" aria-hidden />
              {fr.expenses.zoneArchivage}
            </p>
            <p className="text-xs text-muted-foreground">{fr.expenses.archivageAide}</p>
            <Button variant="outline" size="sm" onClick={onArchiver} loading={archiver.isPending}>
              <Archive className="h-4 w-4" />
              {fr.expenses.archiver}
            </Button>
          </div>
        )
      )}
    </div>
  );
}

/**
 * Le versement qui a soldé une note, ou son absence.
 *
 * Une note peut avoir été marquée « Remboursée » par l'ancienne liste
 * déroulante, sans qu'aucun versement n'ait été enregistré : ni justificatif,
 * ni ligne dans l'onglet « Remboursements ». Le dire est plus utile que de
 * laisser chercher un PDF qui n'a jamais existé.
 */
function BlocVersement({ versement }: { versement?: Reimbursement }) {
  const { download, downloadingId } = useDownloadAttachment();

  if (!versement) {
    return (
      <Alert variant="warning">
        <AlertDescription>{fr.expenses.remboursementSansVersement}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="rounded-md border bg-background p-3 text-sm">
      <p className="text-muted-foreground">
        {fr.reimbursements.emisLe} {formatDate(versement.date_remboursement)} ·{' '}
        {formatCurrency(Number(versement.montant_total))} {fr.reimbursements.verse} ·{' '}
        {versement.moyen} ({versement.etablissement})
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {versement.a_pdf && (
          <Button
            variant="outline"
            size="sm"
            disabled={downloadingId === versement.id}
            onClick={() =>
              download(
                reimbursementDocumentPath(versement.id, 'pdf'),
                `NDF-${versement.id}.pdf`,
                versement.id,
              )
            }
          >
            <Download className="h-4 w-4" />
            {fr.reimbursements.justificatifPdf}
          </Button>
        )}
        {versement.a_xlsx && (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              download(
                reimbursementDocumentPath(versement.id, 'xlsx'),
                `NDF-${versement.id}.xlsx`,
              )
            }
          >
            <Download className="h-4 w-4" />
            {fr.reimbursements.justificatifXlsx}
          </Button>
        )}
      </div>
    </div>
  );
}
