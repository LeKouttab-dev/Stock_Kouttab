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
import { EventSelect } from '@/components/forms/EventSelect';
import { AttachmentNamesPreview } from '@/components/forms/AttachmentNamesPreview';
import { DocumentScanner } from '@/components/scanner/DocumentScanner';
import { useCreateInvoice } from '@/api/endpoints/invoices';
import { usePoles } from '@/api/endpoints/referentials';
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
      eventId: null,
      eventLibre: '',
      dateEvenement: '',
      fournisseur: '',
      montant: '',
    },
  });

  const poleId = form.watch('poleId');
  const eventId = form.watch('eventId');
  const eventLibre = form.watch('eventLibre');
  const dateEvenement = form.watch('dateEvenement');

  const selectedPole = poles?.find((p) => p.id === poleId) ?? null;
  const selectedEventName = useMemo(() => eventLibre || null, [eventLibre]);

  /**
   * Aperçu des noms de fichiers réellement envoyés au comptable.
   *
   * Le déposant voit avant de valider ce que recevra la comptabilité : une
   * faute de frappe dans le nom d'événement se corrige ici plutôt qu'après
   * l'envoi. Calculé par `lib/naming.ts`, jumeau exact du module backend.
   */
  const previewNames = useMemo(() => {
    if (files.length === 0) return [];
    const eventLabel =
      selectedEventName ?? (eventId !== null ? (fr.events.selected as string) : null);
    const base = files.map(() =>
      buildAttachmentFilename([selectedPole?.nom, eventLabel], dateEvenement || null),
    );
    return deduplicateFilenames(base);
  }, [files, selectedPole, selectedEventName, eventId, dateEvenement]);

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
        eventId: values.eventId ?? null,
        eventLibre: values.eventLibre ?? '',
        dateEvenement: values.dateEvenement,
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
                  onValueChange={(v) =>
                    form.setValue('poleId', Number(v), { shouldValidate: true })
                  }
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

              <div className="space-y-1.5">
                <Label required>{fr.invoices.evenement}</Label>
                <EventSelect
                  eventId={eventId ?? null}
                  freeText={eventLibre ?? ''}
                  onEventIdChange={(id) => form.setValue('eventId', id, { shouldValidate: true })}
                  onFreeTextChange={(v) => form.setValue('eventLibre', v, { shouldValidate: true })}
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
                accept=".pdf,.png,.jpg,.jpeg"
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

            <div className="space-y-1.5">
              <Label htmlFor="comment">{fr.invoices.comment}</Label>
              <Textarea
                id="comment"
                rows={3}
                placeholder={fr.invoices.commentPlaceholder}
                {...form.register('comment')}
              />
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
