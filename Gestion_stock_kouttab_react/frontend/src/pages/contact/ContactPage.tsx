import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { LifeBuoy, Send } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSendContact, type ContactCible } from '@/api/endpoints/contact';
import { contactSchema, type ContactFormValues } from '@/lib/schemas/contact';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Poser une question sans quitter l'application.
 *
 * Les bénévoles écrivaient par messages privés, à qui ils trouvaient : une
 * question de remboursement partait à l'administration, une demande de compte à
 * la comptabilité, et beaucoup restaient sans réponse.
 *
 * Aucun champ « votre nom » ni « votre adresse » : le serveur reprend l'identité
 * du compte connecté. Un nom saisi à la main se remplit de n'importe quoi, et
 * une question signée d'un nom inventé ne se traite pas.
 */
export function ContactPage() {
  const envoyer = useSendContact();
  const toast = useToast();

  const form = useForm<ContactFormValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: { destinataire: 'compta', sujet: '', message: '' },
  });

  const onSubmit = (values: ContactFormValues) => {
    envoyer.mutate(values, {
      onSuccess: (reponse) => {
        toast.success(reponse.message);
        form.reset({ destinataire: values.destinataire, sujet: '', message: '' });
      },
    });
  };

  const destinataire = form.watch('destinataire');

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <LifeBuoy className="h-6 w-6" aria-hidden />
          {fr.contact.title}
        </h1>
        <p className="text-sm text-muted-foreground">{fr.contact.subtitle}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{fr.contact.formTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Label required>{fr.contact.destinataire}</Label>
              <Select
                value={destinataire}
                onValueChange={(v) => form.setValue('destinataire', v as ContactCible)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="compta">{fr.contact.versCompta}</SelectItem>
                  <SelectItem value="admin">{fr.contact.versAdmin}</SelectItem>
                </SelectContent>
              </Select>
              <p className="mt-1 text-xs text-muted-foreground">
                {destinataire === 'compta' ? fr.contact.aideCompta : fr.contact.aideAdmin}
              </p>
            </div>

            <div>
              <Label required htmlFor="contact-sujet">
                {fr.contact.sujet}
              </Label>
              <Input
                id="contact-sujet"
                placeholder={fr.contact.sujetPlaceholder}
                {...form.register('sujet')}
              />
              {form.formState.errors.sujet && (
                <p className="mt-1 text-xs text-destructive">
                  {form.formState.errors.sujet.message}
                </p>
              )}
            </div>

            <div>
              <Label required htmlFor="contact-message">
                {fr.contact.message}
              </Label>
              <Textarea id="contact-message" rows={7} {...form.register('message')} />
              {form.formState.errors.message && (
                <p className="mt-1 text-xs text-destructive">
                  {form.formState.errors.message.message}
                </p>
              )}
            </div>

            <p className="text-xs text-muted-foreground">{fr.contact.identiteAuto}</p>

            <Button type="submit" loading={envoyer.isPending}>
              <Send className="mr-1 h-4 w-4" />
              {fr.contact.envoyer}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
