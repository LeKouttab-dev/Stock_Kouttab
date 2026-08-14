import { useMemo, useState } from 'react';
import { FileText, ScanLine } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { FileUploader } from '@/components/forms/FileUploader';
import { CategorySelect } from '@/components/forms/CategorySelect';
import { EventSelect } from '@/components/forms/EventSelect';
import { AttachmentNamesPreview } from '@/components/forms/AttachmentNamesPreview';
import { DocumentScanner } from '@/components/scanner/DocumentScanner';
import { MesJustificatifsDemandes } from '@/components/tickets/MesJustificatifsDemandes';
import { useCreateInvoice } from '@/api/endpoints/invoices';
import { useExpenseCategories, usePoles } from '@/api/endpoints/referentials';
import { invoiceUploadSchema, type InvoiceUploadFormValues } from '@/lib/schemas/invoice';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

export function InvoiceUploadPage() {
  const create = useCreateInvoice();
  const toast = useToast();
  const { data: poles } = usePoles();
  const [files, setFiles] = useState<File[]>([]);
  const [scanOpen, setScanOpen] = useState(false);

  const form = useForm<InvoiceUploadFormValues>({
    resolver: zodResolver(invoiceUploadSchema),
    defaultValues: {
      comment: '',
      poleId: undefined,
      requiertEvenement: false,
      eventId: null,
      eventLibre: '',
      dateEvenement: '',
      categorieId: null,
      fournisseur: '',
      montant: '',
    },
  });

  const poleId = form.watch('poleId');
  const eventId = form.watch('eventId');
  const eventLibre = form.watch('eventLibre');
  const dateEvenement = form.watch('dateEvenement');
  const categorieId = form.watch('categorieId');

  const selectedPole = poles?.find((p) => p.id === poleId) ?? null;
  const requiertEvenement = Boolean(selectedPole?.requiert_evenement);
  const selectedEventName = useMemo(() => eventLibre || null, [eventLibre]);
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
    form.setValue('poleId', id, { shouldValidate: true });
    form.setValue('requiertEvenement', Boolean(pole?.requiert_evenement));
    form.setValue('eventId', null);
    form.setValue('eventLibre', '');
    form.setValue('dateEvenement', '');
  };

  /**
   * Aperçu des noms de fichiers réellement envoyés au comptable.
   *
   * Le déposant voit avant de valider ce que recevra la comptabilité : une
   * faute de frappe dans le nom d'événement se corrige ici plutôt qu'après
   * l'envoi. Calculé par `lib/naming.ts`, jumeau exact du module backend.
   *
   * Deuxième composant : l'événement sous un pôle événementiel, la catégorie
   * sous les autres.
   */
  const previewNames = useMemo(() => {
    if (files.length === 0) return [];
    const rattachement = requiertEvenement
      ? (selectedEventName ?? (eventId !== null ? (fr.events.selected as string) : null))
      : (selectedCategorie?.nom ?? null);
    const base = files.map(() =>
      buildAttachmentFilename(
        [selectedPole?.nom, rattachement],
        (requiertEvenement ? dateEvenement : '') || null,
      ),
    );
    return deduplicateFilenames(base);
  }, [
    files,
    selectedPole,
    requiertEvenement,
    selectedCategorie,
    selectedEventName,
    eventId,
    dateEvenement,
  ]);

  const onSubmit = (values: InvoiceUploadFormValues) => {
    if (files.length === 0) {
      toast.warning(fr.invoices.aucunFichier);
      return;
    }
    // Les effets de succès passent par `onSuccess` : `useApiMutation` affiche
    // déjà le toast d'erreur, il n'y a donc rien à rattraper ici.
    create.mutate(
      {
        comment: values.comment,
        files,
        poleId: values.poleId!,
        // Sous un pôle sans événement, ces champs sont vidés à la sélection :
        // les envoyer quand même ferait refuser le dépôt par l'API.
        eventId: values.eventId ?? null,
        eventLibre: values.eventLibre ?? '',
        dateEvenement: values.dateEvenement ?? '',
        categorieId: values.categorieId ?? null,
        fournisseur: values.fournisseur,
        montant: values.montant,
      },
      {
        onSuccess: () => {
          toast.success(fr.invoices.envoiSucces);
          form.reset();
          setFiles([]);
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <FileText className="h-6 w-6" aria-hidden />
          {fr.invoices.title}
        </h1>
        <p className="text-sm text-muted-foreground">{fr.invoices.subtitle}</p>
      </div>

      <Alert variant="warning">
        <AlertTitle>{fr.invoices.important}</AlertTitle>
        <AlertDescription>{fr.invoices.importantText}</AlertDescription>
      </Alert>

      {/* Ce que la comptabilité attend, juste au-dessus du formulaire qui sert
          à le lui donner. */}
      <MesJustificatifsDemandes />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{fr.invoices.depositTab}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
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
                {form.formState.errors.poleId && (
                  <p className="text-xs text-destructive">{form.formState.errors.poleId.message}</p>
                )}
              </div>

              {/* La nature de la dépense, demandée partout : elle dit ce qui
                  a été acheté, là où l'événement dit à quelle occasion. */}
              <div className="space-y-1.5">
                <Label required>{fr.categories.label}</Label>
                <CategorySelect
                  categoryId={categorieId ?? null}
                  onChange={(id) => form.setValue('categorieId', id, { shouldValidate: true })}
                />
                {form.formState.errors.categorieId && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.categorieId.message}
                  </p>
                )}
              </div>

              {/* L'événement et sa date, seulement sous un pôle qui en attend
                  un. Une facture du local n'en a pas — la ligne disparaît
                  plutôt que d'obliger à en inventer un. */}
              {requiertEvenement && (
                <>
                  <div className="space-y-1.5">
                    <Label required>{fr.invoices.evenement}</Label>
                    <EventSelect
                      eventId={eventId ?? null}
                      freeText={eventLibre ?? ''}
                      onEventIdChange={(id) =>
                        form.setValue('eventId', id, { shouldValidate: true })
                      }
                      onFreeTextChange={(v) =>
                        form.setValue('eventLibre', v, { shouldValidate: true })
                      }
                      typeEvenement={selectedPole?.type_evenement}
                      onEventDate={(d) => {
                        if (d && !form.getValues('dateEvenement')) {
                          form.setValue('dateEvenement', d, { shouldValidate: true });
                        }
                      }}
                    />
                    {form.formState.errors.eventId && (
                      <p className="text-xs text-destructive">
                        {form.formState.errors.eventId.message}
                      </p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="dateEvenement" required>
                      {fr.invoices.dateEvenement}
                    </Label>
                    <Input id="dateEvenement" type="date" {...form.register('dateEvenement')} />
                    {form.formState.errors.dateEvenement && (
                      <p className="text-xs text-destructive">
                        {form.formState.errors.dateEvenement.message}
                      </p>
                    )}
                  </div>
                </>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="fournisseur">{fr.invoices.fournisseur}</Label>
                <Input id="fournisseur" {...form.register('fournisseur')} />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="montant">{fr.invoices.montant}</Label>
                <Input
                  id="montant"
                  type="number"
                  step="0.01"
                  min="0"
                  {...form.register('montant')}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Label required>{fr.invoices.upload}</Label>
                <Button type="button" variant="outline" size="sm" onClick={() => setScanOpen(true)}>
                  <ScanLine className="h-4 w-4" />
                  {fr.scanner.documentTitle}
                </Button>
              </div>
              <FileUploader
                accept=".png,.jpg,.jpeg,.pdf,.heic,.heif,.webp,image/*,application/pdf"
                files={files}
                onChange={setFiles}
                helperText={fr.invoices.uploadHelper}
              />
            </div>

            <DocumentScanner
              open={scanOpen}
              onClose={() => setScanOpen(false)}
              onScanned={(scanned) => setFiles((prev) => [...prev, scanned])}
            />

            <AttachmentNamesPreview names={previewNames} />

            {/* Sous un pôle sans événement, la description prend la place que
                l'événement occupait : c'est elle qui dit ce qui a été acheté. */}
            <div className="space-y-1.5">
              <Label htmlFor="comment" required={!requiertEvenement}>
                {requiertEvenement ? fr.invoices.comment : fr.categories.description}
              </Label>
              <Textarea
                id="comment"
                rows={3}
                placeholder={
                  requiertEvenement
                    ? fr.invoices.commentPlaceholder
                    : fr.categories.descriptionPlaceholder
                }
                {...form.register('comment')}
              />
              {form.formState.errors.comment && (
                <p className="text-xs text-destructive">{form.formState.errors.comment.message}</p>
              )}
            </div>

            <Button type="submit" loading={create.isPending}>
              {fr.invoices.deposer}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
