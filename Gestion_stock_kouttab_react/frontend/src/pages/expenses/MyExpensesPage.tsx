import { useMemo, useState } from 'react';
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
import { EventSelect } from '@/components/forms/EventSelect';
import { ProfileForm } from '@/components/forms/ProfileForm';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { usePoles } from '@/api/endpoints/referentials';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import { useCreateExpense, useMyExpenses, useUpdateExpense } from '@/api/endpoints/expenses';
import { expenseSchema, type ExpenseFormValues } from '@/lib/schemas/expense';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { expenseTotal } from '@/lib/money';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Expense } from '@/types/api';

export function MyExpensesPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">📝 {fr.expenses.title}</h1>
        <p className="text-sm text-muted-foreground">
          Soumettez vos notes de frais et suivez leur traitement.
        </p>
      </div>

      <Tabs defaultValue="submit">
        <TabsList className="grid w-full grid-cols-1 sm:grid-cols-3">
          <TabsTrigger value="submit">{fr.expenses.submitTab}</TabsTrigger>
          <TabsTrigger value="mine">{fr.expenses.myDemandsTab}</TabsTrigger>
          <TabsTrigger value="profile">{fr.expenses.profileTab}</TabsTrigger>
        </TabsList>

        <TabsContent value="submit">
          <SubmitExpenseTab />
        </TabsContent>
        <TabsContent value="mine">
          <MyExpensesList />
        </TabsContent>
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

  const form = useForm<ExpenseFormValues>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      date_depense: new Date().toISOString().slice(0, 10),
      rattachement: '',
      fournisseur: '',
      nature_charge: '',
      montant: 0,
      commentaires: '',
      remboursement_deja_emis: 0,
      remise: 0,
      id_pole: null,
      id_event: null,
      evenement_libre: '',
      date_evenement: '',
    },
  });

  const poleId = form.watch('id_pole');
  const eventId = form.watch('id_event');
  const eventLibre = form.watch('evenement_libre');
  const dateEvenement = form.watch('date_evenement');
  const dateDepense = form.watch('date_depense');
  const rattachement = form.watch('rattachement');

  const selectedPole = poles?.find((p) => p.id === poleId) ?? null;

  /**
   * Aperçu du nom transmis à la comptabilité.
   *
   * Même règle de repli que le serveur : à défaut d'événement, on retombe sur
   * le rattachement, et à défaut de date d'événement sur la date de dépense.
   */
  const previewNames = useMemo(() => {
    if (files.length === 0) return [];
    const eventLabel =
      eventLibre?.trim() ||
      (eventId !== null && eventId !== undefined ? fr.events.selected : null) ||
      rattachement;
    const base = files.map(() =>
      buildAttachmentFilename(
        [selectedPole?.nom, eventLabel],
        dateEvenement || dateDepense || null,
      ),
    );
    return deduplicateFilenames(base);
  }, [files, selectedPole, eventLibre, eventId, rattachement, dateEvenement, dateDepense]);

  const onSubmit = async (values: ExpenseFormValues) => {
    try {
      await create.mutateAsync({ payload: values, files });
      toast.success(fr.expenses.soumissionOK);
      form.reset();
      setFiles([]);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
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
              <Label htmlFor="rattachement" required>
                {fr.expenses.rattachement}
              </Label>
              <Input
                id="rattachement"
                hasError={Boolean(form.formState.errors.rattachement)}
                {...form.register('rattachement')}
              />
              {form.formState.errors.rattachement && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.rattachement.message}
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

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="fournisseur">{fr.expenses.fournisseur}</Label>
              <Input id="fournisseur" {...form.register('fournisseur')} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nature_charge">{fr.expenses.natureCharge}</Label>
              <Input id="nature_charge" {...form.register('nature_charge')} />
            </div>
          </div>

          {/* Rattachement comptable : facultatif ici, contrairement aux
              factures. Une dépense courante n'a pas toujours d'événement, et
              le nom du ticket retombe alors sur le rattachement. */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label>{fr.invoices.pole}</Label>
              <Select
                value={poleId ? String(poleId) : ''}
                onValueChange={(v) => form.setValue('id_pole', Number(v))}
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
            </div>
            <div className="space-y-1.5">
              <Label>{fr.invoices.evenement}</Label>
              <EventSelect
                eventId={eventId ?? null}
                freeText={eventLibre ?? ''}
                onEventIdChange={(id) => form.setValue('id_event', id)}
                onFreeTextChange={(v) => form.setValue('evenement_libre', v)}
                onEventDate={(d) => {
                  if (d && !form.getValues('date_evenement')) {
                    form.setValue('date_evenement', d);
                  }
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date_evenement">{fr.invoices.dateEvenement}</Label>
              <Input id="date_evenement" type="date" {...form.register('date_evenement')} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="commentaires">{fr.expenses.commentaires}</Label>
            <Textarea id="commentaires" rows={3} {...form.register('commentaires')} />
          </div>

          <div className="space-y-1.5">
            <Label>{fr.expenses.tickets}</Label>
            <FileUploader
              accept=".png,.jpg,.jpeg"
              files={files}
              onChange={setFiles}
              helperText="PNG, JPG. 10 Mo max par fichier, 5 fichiers max."
            />
          </div>

          {previewNames.length > 0 && (
            <div className="rounded-md border bg-muted/40 p-3">
              <p className="text-xs font-medium">{fr.invoices.apercuNomFichier}</p>
              <ul className="mt-1 space-y-0.5">
                {previewNames.map((name) => (
                  <li key={name} className="font-mono text-xs text-muted-foreground">
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          )}

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

  const editForm = useForm<ExpenseFormValues>({
    resolver: zodResolver(expenseSchema),
  });

  if (isLoading) return <LoadingSpinner fullPage />;

  if (expenses.length === 0) {
    return <EmptyState title={fr.expenses.aucuneDemande} />;
  }

  const startEdit = (exp: Expense) => {
    setEditing(exp.id);
    editForm.reset({
      date_depense: exp.date_depense.slice(0, 10),
      rattachement: exp.rattachement,
      fournisseur: exp.fournisseur ?? '',
      nature_charge: exp.nature_charge ?? '',
      montant: exp.montant,
      commentaires: exp.commentaires ?? '',
      remboursement_deja_emis: exp.remboursement_deja_emis,
      remise: exp.remise,
    });
  };

  const onSubmitEdit = async (id: number) => {
    const values = editForm.getValues();
    try {
      await update.mutateAsync({ id, data: values });
      toast.success(fr.expenses.noteUpdated);
      setEditing(null);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
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
                  <p className="font-semibold">
                    {formatDate(exp.date_depense)} — {exp.rattachement}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Montant : {formatCurrency(exp.montant)} · Total demandé :{' '}
                    <strong>{formatCurrency(total)}</strong>
                  </p>
                </div>
                <StatusBadge status={exp.status} />
              </div>

              {exp.commentaires_compta && (
                <Alert variant="info">
                  <AlertDescription>
                    💬 Commentaire de la comptabilité : {exp.commentaires_compta}
                  </AlertDescription>
                </Alert>
              )}

              {exp.status === 'En attente' && !isEditing && (
                <Button size="sm" variant="outline" onClick={() => startEdit(exp)}>
                  ✏️ {fr.expenses.editer}
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
                      <Label required>{fr.expenses.rattachement}</Label>
                      <Input {...editForm.register('rattachement')} />
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

// L'onglet « Profil » et la page /profile affichaient deux copies du meme
// formulaire : un champ ajoute d'un cote manquait de l'autre.
function ProfileTab() {
  return <ProfileForm />;
}
