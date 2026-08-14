import { useMemo, useRef, useState } from 'react';
import { Download, Pencil, ReceiptText, ScanLine, Upload } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { FileUploader } from '@/components/forms/FileUploader';
import { CategorySelect } from '@/components/forms/CategorySelect';
import { EventSelect } from '@/components/forms/EventSelect';
import { ProfileForm } from '@/components/forms/ProfileForm';
import { AttachmentNamesPreview } from '@/components/forms/AttachmentNamesPreview';
import { DocumentScanner } from '@/components/scanner/DocumentScanner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useExpenseCategories, usePoles } from '@/api/endpoints/referentials';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import {
  useAjouterJustificatif,
  useCreateExpense,
  useMyExpenses,
  useUpdateExpense,
} from '@/api/endpoints/expenses';
import {
  reimbursementDocumentPath,
  useRemboursementParNote,
} from '@/api/endpoints/reimbursements';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
import {
  expenseEditSchema,
  expenseSchema,
  type ExpenseEditFormValues,
  type ExpenseFormValues,
} from '@/lib/schemas/expense';
import { useAuth } from '@/hooks/useAuth';
import { usePendingSummary } from '@/api/endpoints/notifications';
import { ACTIONS } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { ValidateExpensesPage } from './ValidateExpensesPage';
import { ReimbursementsList } from './ReimbursementsList';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { expenseTotal } from '@/lib/money';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Expense } from '@/types/api';

/**
 * Notes de frais : **une seule entrée**, déposer et valider.
 *
 * L'application en proposait deux dans le menu, pour un même sujet. Or la
 * comptabilité fait les deux : elle dépose ses propres notes et valide celles
 * des autres. Naviguer entre deux pages pour cela n'avait pas de sens.
 *
 * L'onglet « Valider » n'apparaît qu'à qui en a le droit ; les autres voient
 * exactement ce qu'ils voyaient avant.
 */
export function MyExpensesPage() {
  const { can } = useAuth();
  const peutValider = can(ACTIONS.EXPENSES_VALIDATE);
  const { data: aTraiter } = usePendingSummary();
  const [onglet, setOnglet] = useState(() =>
    window.location.hash === '#valider' ? 'valider' : 'submit',
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <ReceiptText className="h-6 w-6" aria-hidden />
          {fr.expenses.title}
        </h1>
        <p className="text-sm text-muted-foreground">
          Soumettez vos notes de frais et suivez leur traitement.
        </p>
      </div>

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList
          className={cn(
            'grid w-full grid-cols-1',
            peutValider ? 'sm:grid-cols-5' : 'sm:grid-cols-4',
          )}
        >
          <TabsTrigger value="submit">{fr.expenses.submitTab}</TabsTrigger>
          <TabsTrigger value="mine">{fr.expenses.myDemandsTab}</TabsTrigger>
          <TabsTrigger value="remboursements">{fr.expenses.remboursementsTab}</TabsTrigger>
          {peutValider && (
            <TabsTrigger value="valider" className="gap-1.5">
              {fr.expenses.validateTab}
              {/* Le nombre à traiter suit l'onglet : la pastille du menu portait
                  cette information, et l'entrée correspondante a disparu. */}
              {Boolean(aTraiter?.notes_a_valider) && (
                <span className="rounded-full bg-terracotta px-1.5 py-0.5 text-[11px] font-semibold leading-none text-cream-50">
                  {aTraiter?.notes_a_valider}
                </span>
              )}
            </TabsTrigger>
          )}
          <TabsTrigger value="profile">{fr.expenses.profileTab}</TabsTrigger>
        </TabsList>

        <TabsContent value="submit">
          <SubmitExpenseTab />
        </TabsContent>
        <TabsContent value="mine">
          <MyExpensesList />
        </TabsContent>
        <TabsContent value="remboursements">
          <ReimbursementsList />
        </TabsContent>
        {peutValider && (
          <TabsContent value="valider">
            <ValidateExpensesPage embarquee />
          </TabsContent>
        )}
        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SubmitExpenseTab() {
  const create = useCreateExpense();
  const toast = useToast();
  const { data: poles } = usePoles();
  const [files, setFiles] = useState<File[]>([]);
  const [scanOpen, setScanOpen] = useState(false);

  const form = useForm<ExpenseFormValues>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      date_depense: new Date().toISOString().slice(0, 10),
      fournisseur: '',
      nature_charge: '',
      montant: 0,
      commentaires: '',
      remboursement_deja_emis: 0,
      remise: 0,
      // `undefined` et non `null` : le pôle est désormais requis, et un `null`
      // explicite ferait échouer la validation sur le type plutôt que d'afficher
      // « Pôle de rattachement obligatoire ».
      id_pole: undefined,
      requiert_evenement: false,
      id_event: null,
      evenement_libre: '',
      date_evenement: '',
      id_categorie: null,
    },
  });

  const poleId = form.watch('id_pole');
  const eventId = form.watch('id_event');
  const eventLibre = form.watch('evenement_libre');
  const dateEvenement = form.watch('date_evenement');
  const dateDepense = form.watch('date_depense');
  const categorieId = form.watch('id_categorie');

  const selectedPole = poles?.find((p) => p.id === poleId) ?? null;
  const requiertEvenement = Boolean(selectedPole?.requiert_evenement);
  const { data: categories } = useExpenseCategories();
  const selectedCategorie = categories?.find((c) => c.id === categorieId) ?? null;

  /**
   * Changement de pôle : on repart des champs de l'événement.
   *
   * Sans ce nettoyage, un événement saisi puis un basculement vers « Local »
   * laissait l'événement dans le formulaire — invisible, mais envoyé, et refusé
   * par l'API avec un message que rien à l'écran n'expliquait.
   *
   * La catégorie, elle, **survit au changement** : elle est demandée sous tous
   * les pôles, et l'effacer ferait resaisir la nature de la dépense à chaque
   * hésitation sur le pôle.
   */
  const changerPole = (id: number) => {
    const pole = poles?.find((p) => p.id === id) ?? null;
    form.setValue('id_pole', id, { shouldValidate: true });
    form.setValue('requiert_evenement', Boolean(pole?.requiert_evenement));
    form.setValue('id_event', null);
    form.setValue('evenement_libre', '');
    form.setValue('date_evenement', '');
  };

  /**
   * Aperçu du nom transmis à la comptabilité.
   *
   * Deuxième composant : l'événement sous un pôle événementiel, la catégorie
   * sous les autres — exactement ce que le backend compose. La date de dépense
   * sert de repli tant que le formulaire est incomplet, pour que l'aperçu reste
   * lisible pendant la saisie.
   */
  const previewNames = useMemo(() => {
    if (files.length === 0) return [];
    const rattachement = requiertEvenement
      ? eventLibre?.trim() ||
        (eventId !== null && eventId !== undefined ? fr.events.selected : null)
      : (selectedCategorie?.nom ?? null);
    const base = files.map(() =>
      buildAttachmentFilename(
        [selectedPole?.nom, rattachement],
        (requiertEvenement ? dateEvenement : '') || dateDepense || null,
      ),
    );
    return deduplicateFilenames(base);
  }, [
    files,
    selectedPole,
    requiertEvenement,
    selectedCategorie,
    eventLibre,
    eventId,
    dateEvenement,
    dateDepense,
  ]);

  const onSubmit = (values: ExpenseFormValues) => {
    create.mutate(
      { payload: values, files },
      {
        onSuccess: () => {
          toast.success(fr.expenses.soumissionOK);
          form.reset();
          setFiles([]);
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{fr.expenses.nouvelleNote}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="date_depense" required>
                {fr.expenses.date}
              </Label>
              <Input
                id="date_depense"
                type="date"
                hasError={Boolean(form.formState.errors.date_depense)}
                {...form.register('date_depense')}
              />
              {form.formState.errors.date_depense && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.date_depense.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fournisseur" required>
                {fr.expenses.fournisseur}
              </Label>
              <Input
                id="fournisseur"
                hasError={Boolean(form.formState.errors.fournisseur)}
                {...form.register('fournisseur')}
              />
              {form.formState.errors.fournisseur && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.fournisseur.message}
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="montant" required>
                {fr.expenses.montant}
              </Label>
              <Input
                id="montant"
                type="number"
                step="0.01"
                min="0"
                hasError={Boolean(form.formState.errors.montant)}
                {...form.register('montant', { valueAsNumber: true })}
              />
              {form.formState.errors.montant && (
                <p className="text-xs text-destructive">{form.formState.errors.montant.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="remboursement_deja_emis">{fr.expenses.rembEmis}</Label>
              <Input
                id="remboursement_deja_emis"
                type="number"
                step="0.01"
                min="0"
                {...form.register('remboursement_deja_emis', { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="remise">{fr.expenses.remise}</Label>
              <Input
                id="remise"
                type="number"
                step="0.01"
                min="0"
                {...form.register('remise', { valueAsNumber: true })}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="nature_charge">{fr.expenses.natureCharge}</Label>
            <Input id="nature_charge" {...form.register('nature_charge')} />
          </div>

          {/* Le rattachement compose le nom du ticket envoyé au comptable : il
              est obligatoire, comme sur les factures, et remplace l'ancien champ
              « Rattachement » qui faisait double emploi.

              Ce qu'il demande dépend du pôle, et le pôle seul en décide :
              événement et date sous le pôle événementiel, catégorie et
              description partout ailleurs. Une dépense du local n'a pas
              d'événement — en exiger un obligeait à en inventer. */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label required>{fr.invoices.pole}</Label>
              <Select
                value={poleId ? String(poleId) : ''}
                onValueChange={(v) => changerPole(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={fr.invoices.polePlaceholder} />
                </SelectTrigger>
                <SelectContent>
                  {(poles ?? []).map((pole) => (
                    <SelectItem key={pole.id} value={String(pole.id)}>
                      {pole.nom}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.formState.errors.id_pole && (
                <p className="text-xs text-destructive">{form.formState.errors.id_pole.message}</p>
              )}
            </div>

            {/* La nature de la dépense est demandée sous tous les pôles : elle
                dit ce qui a été acheté, là où l'événement dit à quelle occasion.
                Le comptable a besoin des deux pour imputer, et il ne la
                recevait que sur les pièces des pôles sans événement. */}
            <div className="space-y-1.5 md:col-span-2">
              <Label required>{fr.categories.label}</Label>
              <CategorySelect
                categoryId={categorieId ?? null}
                onChange={(id) => form.setValue('id_categorie', id, { shouldValidate: true })}
              />
              {form.formState.errors.id_categorie && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.id_categorie.message}
                </p>
              )}
            </div>

            {requiertEvenement && (
              <>
                <div className="space-y-1.5">
                  <Label required>{fr.invoices.evenement}</Label>
                  <EventSelect
                    eventId={eventId ?? null}
                    freeText={eventLibre ?? ''}
                    onEventIdChange={(id) =>
                      form.setValue('id_event', id, { shouldValidate: true })
                    }
                    onFreeTextChange={(v) =>
                      form.setValue('evenement_libre', v, { shouldValidate: true })
                    }
                    typeEvenement={selectedPole?.type_evenement}
                    onEventDate={(d) => {
                      if (d && !form.getValues('date_evenement')) {
                        form.setValue('date_evenement', d, { shouldValidate: true });
                      }
                    }}
                  />
                  {form.formState.errors.id_event && (
                    <p className="text-xs text-destructive">
                      {form.formState.errors.id_event.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="date_evenement" required>
                    {fr.invoices.dateEvenement}
                  </Label>
                  <Input id="date_evenement" type="date" {...form.register('date_evenement')} />
                  {form.formState.errors.date_evenement && (
                    <p className="text-xs text-destructive">
                      {form.formState.errors.date_evenement.message}
                    </p>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Sous un pôle sans événement, la description prend la place que
              l'événement occupait : c'est elle qui dit ce qui a été acheté. */}
          <div className="space-y-1.5">
            <Label htmlFor="commentaires" required={!requiertEvenement}>
              {requiertEvenement ? fr.expenses.commentaires : fr.categories.description}
            </Label>
            <Textarea
              id="commentaires"
              rows={3}
              placeholder={requiertEvenement ? undefined : fr.categories.descriptionPlaceholder}
              {...form.register('commentaires')}
            />
            {form.formState.errors.commentaires && (
              <p className="text-xs text-destructive">
                {form.formState.errors.commentaires.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label>{fr.expenses.tickets}</Label>
              <Button type="button" variant="outline" size="sm" onClick={() => setScanOpen(true)}>
                <ScanLine className="h-4 w-4" />
                {fr.scanner.documentTitle}
              </Button>
            </div>
            <FileUploader
              accept=".png,.jpg,.jpeg,.pdf,.heic,.heif,.webp,image/*,application/pdf"
              files={files}
              onChange={setFiles}
              helperText={fr.expenses.formatsAcceptes}
            />
          </div>

          <DocumentScanner
            open={scanOpen}
            onClose={() => setScanOpen(false)}
            onScanned={(scanned) => setFiles((prev) => [...prev, scanned])}
          />

          <AttachmentNamesPreview names={previewNames} />

          <Button type="submit" loading={create.isPending}>
            {fr.expenses.soumettre}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function MyExpensesList() {
  const { data: expenses = [], isLoading } = useMyExpenses();
  const update = useUpdateExpense();
  const toast = useToast();
  const [editing, setEditing] = useState<number | null>(null);
  // Une note « Remboursée » n'affichait qu'une pastille verte : ni date de
  // versement, ni montant, ni preuve. Le justificatif existait pourtant.
  const remboursementParNote = useRemboursementParNote();
  const { download, downloadingId } = useDownloadAttachment();

  const editForm = useForm<ExpenseEditFormValues>({
    resolver: zodResolver(expenseEditSchema),
  });

  if (isLoading) return <LoadingSpinner fullPage />;

  if (expenses.length === 0) {
    return <EmptyState title={fr.expenses.aucuneDemande} />;
  }

  const startEdit = (exp: Expense) => {
    setEditing(exp.id);
    editForm.reset({
      date_depense: exp.date_depense.slice(0, 10),
      fournisseur: exp.fournisseur ?? '',
      nature_charge: exp.nature_charge ?? '',
      montant: exp.montant,
      commentaires: exp.commentaires ?? '',
      remboursement_deja_emis: exp.remboursement_deja_emis,
      remise: exp.remise,
    });
  };

  const onSubmitEdit = (id: number) => {
    update.mutate(
      { id, data: editForm.getValues() },
      {
        onSuccess: () => {
          toast.success(fr.expenses.noteUpdated);
          setEditing(null);
        },
      },
    );
  };

  return (
    <div className="space-y-3">
      {expenses.map((exp) => {
        const total = expenseTotal(exp);
        const isEditing = editing === exp.id;

        return (
          <Card key={exp.id}>
            <CardContent className="p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="flex items-center gap-2 font-semibold">
                    {/* Un point, et non un compteur : ce qui compte est qu'il y
                        ait du nouveau sur cette note, pas combien de fois. Il
                        s'éteint dès que la liste a été ouverte. */}
                    {exp.non_lu_demandeur && (
                      <span
                        className="h-2 w-2 flex-shrink-0 rounded-full bg-terracotta"
                        aria-label={fr.expenses.duNouveau}
                      />
                    )}
                    {/* Les notes déposées avant la refonte n'ont ni événement ni
                        fournisseur : on retombe sur leur rattachement libre
                        plutôt que d'afficher une ligne amputée. */}
                    <span>
                      {formatDate(exp.date_depense)} —{' '}
                      {exp.evenement || exp.fournisseur || exp.rattachement}
                    </span>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Montant : {formatCurrency(exp.montant)} · Total demandé :{' '}
                    <strong>{formatCurrency(total)}</strong>
                  </p>
                </div>
                <StatusBadge status={exp.status} />
              </div>

              {exp.commentaires_compta && (
                <Alert variant={exp.non_lu_demandeur ? 'warning' : 'info'}>
                  <AlertDescription>
                    {fr.expenses.motDeLaCompta} : {exp.commentaires_compta}
                  </AlertDescription>
                </Alert>
              )}

              {/* Le versement qui a soldé cette note : date, montant, et le
                  justificatif à télécharger. Sans lui, le bénévole ne pouvait
                  ni dater ni prouver son remboursement depuis l'application. */}
              {(() => {
                const versement = remboursementParNote.get(exp.id);
                if (!versement) return null;
                return (
                  <div className="rounded-md border bg-background px-3 py-2 text-sm">
                    <p className="text-muted-foreground">
                      {fr.reimbursements.emisLe} {formatDate(versement.date_remboursement)} ·{' '}
                      {formatCurrency(Number(versement.montant_total))} {fr.reimbursements.verse} ·{' '}
                      {versement.moyen}
                    </p>
                    {versement.a_pdf && (
                      <button
                        type="button"
                        disabled={downloadingId === versement.id}
                        onClick={() =>
                          download(
                            reimbursementDocumentPath(versement.id, 'pdf'),
                            `NDF-${versement.id}.pdf`,
                            versement.id,
                          )
                        }
                        className="mt-1 inline-flex items-center gap-1 text-primary hover:underline disabled:opacity-60"
                      >
                        <Download className="h-3.5 w-3.5" />
                        {fr.expenses.voirJustificatif}
                      </button>
                    )}
                  </div>
                );
              })()}

              {/* Une pièce écartée est une demande d'action : on dit laquelle,
                  pourquoi, et on donne de quoi y répondre. Sans ce bloc, la
                  comptabilité retirait une pièce et le déposant ne pouvait rien
                  faire — l'écran conseillait même de recréer la note. */}
              <PiecesEcartees expense={exp} />

              {exp.status === 'En attente' && !isEditing && (
                <Button size="sm" variant="outline" onClick={() => startEdit(exp)}>
                  <Pencil className="h-4 w-4" aria-hidden />
                  {fr.expenses.editer}
                </Button>
              )}

              {isEditing && (
                <form
                  onSubmit={editForm.handleSubmit(() => onSubmitEdit(exp.id))}
                  className="space-y-3 border-t pt-3"
                >
                  <p className="text-xs text-muted-foreground">{fr.expenses.pourModifierTickets}</p>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <Label required>{fr.expenses.date}</Label>
                      <Input type="date" {...editForm.register('date_depense')} />
                    </div>
                    <div>
                      <Label required>{fr.expenses.fournisseur}</Label>
                      <Input {...editForm.register('fournisseur')} />
                    </div>
                    <div>
                      <Label required>{fr.expenses.montant}</Label>
                      <Input
                        type="number"
                        step="0.01"
                        {...editForm.register('montant', { valueAsNumber: true })}
                      />
                    </div>
                    <div>
                      <Label>{fr.expenses.fournisseur}</Label>
                      <Input {...editForm.register('fournisseur')} />
                    </div>
                    <div>
                      <Label>{fr.expenses.natureCharge}</Label>
                      <Input {...editForm.register('nature_charge')} />
                    </div>
                    <div>
                      <Label>{fr.expenses.rembEmis}</Label>
                      <Input
                        type="number"
                        step="0.01"
                        {...editForm.register('remboursement_deja_emis', { valueAsNumber: true })}
                      />
                    </div>
                    <div>
                      <Label>{fr.expenses.remise}</Label>
                      <Input
                        type="number"
                        step="0.01"
                        {...editForm.register('remise', { valueAsNumber: true })}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>{fr.expenses.commentaires}</Label>
                    <Textarea rows={2} {...editForm.register('commentaires')} />
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" loading={update.isPending}>
                      {fr.common.save}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setEditing(null)}
                    >
                      {fr.common.cancel}
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}


/**
 * Les pièces écartées d'une note, et de quoi en redéposer une.
 *
 * La comptabilité peut retirer un justificatif illisible ou mal rattaché. Sans
 * ce bloc, le déposant voyait sa pièce disparaître de l'examen sans savoir
 * pourquoi, et n'avait aucun moyen d'en fournir une autre — l'écran conseillait
 * de supprimer la note et de la recréer.
 */
function PiecesEcartees({ expense }: { expense: Expense }) {
  const ajouter = useAjouterJustificatif();
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);

  const ecartees = (expense.files ?? []).filter((f) => f.ecarte_at);
  // Une note soldée ne se complète plus : le versement est parti.
  const peutAjouter = expense.status !== 'Remboursée';
  if (ecartees.length === 0) return null;

  const onChoisir = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fichiers = Array.from(e.target.files ?? []);
    e.target.value = '';
    if (fichiers.length === 0) return;
    ajouter.mutate(
      { expenseId: expense.id, files: fichiers },
      { onSuccess: () => toast.success(fr.expenses.justificatifAjoute) },
    );
  };

  return (
    <Alert variant="warning">
      <AlertDescription className="space-y-2">
        <p>{fr.expenses.pieceEcarteeAide}</p>
        <ul className="text-xs">
          {ecartees.map((f) => (
            <li key={f.id}>
              <span className="line-through">{f.nom_fichier}</span> — {f.motif_ecart}
            </li>
          ))}
        </ul>
        {peutAjouter && (
          <>
            <input
              ref={champ}
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.pdf,.heic,.heif,.webp,image/*,application/pdf"
              className="hidden"
              onChange={onChoisir}
              data-testid={`ajout-justificatif-${expense.id}`}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => champ.current?.click()}
              loading={ajouter.isPending}
            >
              <Upload className="mr-1 h-3.5 w-3.5" />
              {fr.expenses.ajouterJustificatif}
            </Button>
          </>
        )}
      </AlertDescription>
    </Alert>
  );
}

// L'onglet « Profil » et la page /profile affichaient deux copies du meme
// formulaire : un champ ajoute d'un cote manquait de l'autre.
function ProfileTab() {
  return <ProfileForm />;
}
