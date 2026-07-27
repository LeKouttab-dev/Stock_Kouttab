import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { FileUploader } from '@/components/forms/FileUploader';
import { useCreateInvoice } from '@/api/endpoints/invoices';
import { invoiceUploadSchema, type InvoiceUploadFormValues } from '@/lib/schemas/invoice';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { fr } from '@/lib/i18n/fr';

export function InvoiceUploadPage() {
  const create = useCreateInvoice();
  const toast = useToast();
  const [files, setFiles] = useState<File[]>([]);

  const form = useForm<InvoiceUploadFormValues>({
    resolver: zodResolver(invoiceUploadSchema),
    defaultValues: { comment: '' },
  });

  const onSubmit = async (values: InvoiceUploadFormValues) => {
    if (files.length === 0) {
      toast.warning(fr.invoices.aucunFichier);
      return;
    }
    try {
      await create.mutateAsync({ comment: values.comment, files });
      toast.success(fr.invoices.envoiSucces);
      form.reset();
      setFiles([]);
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">🧾 {fr.invoices.title}</h1>
        <p className="text-sm text-muted-foreground">
          Déposez vos factures pour traitement par la comptabilité.
        </p>
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
            <div className="space-y-1.5">
              <Label required>{fr.invoices.upload}</Label>
              <FileUploader
                accept=".pdf,.png,.jpg,.jpeg"
                files={files}
                onChange={setFiles}
                helperText="PDF, PNG, JPG. 10 Mo max par fichier."
              />
            </div>

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
