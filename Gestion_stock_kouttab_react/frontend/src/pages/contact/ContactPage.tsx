import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { LifeBuoy, MessageSquarePlus, Send } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useMyConversations, useOpenConversation, useTeamConversations } from '@/api/endpoints/contact';
import { usePendingSummary } from '@/api/endpoints/notifications';
import { contactSchema, type ContactFormValues } from '@/lib/schemas/contact';
import type { ContactCible, Conversation } from '@/types/api';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/format';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';
import { ConversationThread, StatutPuce } from './ConversationThread';

/**
 * Espace de contact : des conversations, et non un formulaire d'envoi.
 *
 * Le formulaire précédent envoyait un courriel et n'en gardait rien. La réponse
 * partait de la boîte du comptable, hors de l'application : personne ne pouvait
 * dire quelles questions restaient sans réponse, ni retrouver ce qui avait été
 * répondu six mois plus tôt.
 *
 * Aucun champ « votre nom » ni « votre adresse » : le serveur reprend l'identité
 * du compte connecté. Un nom saisi à la main se remplit de n'importe quoi.
 */
export function ContactPage() {
  const { can } = useAuth();
  // Le serveur renvoie de toute façon une liste vide aux autres rôles, mais
  // autant ne pas afficher un onglet qui ne montrerait jamais rien.
  const gereDesFils = can(ACTIONS.CONVERSATIONS_HANDLE);
  const { data: aTraiter } = usePendingSummary();
  const [onglet, setOnglet] = useState('mes-fils');
  const [ouvert, setOuvert] = useState<number | null>(null);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <LifeBuoy className="h-6 w-6" aria-hidden />
          {fr.contact.title}
        </h1>
        <p className="text-sm text-muted-foreground">{fr.contact.subtitle}</p>
      </div>

      <Tabs
        value={onglet}
        onValueChange={(v) => {
          setOnglet(v);
          setOuvert(null);
        }}
      >
        <TabsList
          className={cn('grid w-full grid-cols-1', gereDesFils ? 'sm:grid-cols-3' : 'sm:grid-cols-2')}
        >
          <TabsTrigger value="mes-fils" className="gap-1.5">
            {fr.contact.mesConversations}
            <Pastille nombre={aTraiter?.conversations_non_lues} />
          </TabsTrigger>
          <TabsTrigger value="nouveau">{fr.contact.nouvelleConversation}</TabsTrigger>
          {gereDesFils && (
            <TabsTrigger value="equipe" className="gap-1.5">
              {fr.contact.aTraiter}
              <Pastille nombre={aTraiter?.conversations_a_traiter} />
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="mes-fils">
          {ouvert !== null ? (
            <ConversationThread conversationId={ouvert} onBack={() => setOuvert(null)} />
          ) : (
            <MesConversations onOuvrir={setOuvert} />
          )}
        </TabsContent>

        <TabsContent value="nouveau">
          <NouvelleConversation
            onOuverte={(id) => {
              setOnglet('mes-fils');
              setOuvert(id);
            }}
          />
        </TabsContent>

        {gereDesFils && (
          <TabsContent value="equipe">
            {ouvert !== null ? (
              <ConversationThread conversationId={ouvert} onBack={() => setOuvert(null)} gestion />
            ) : (
              <BoiteEquipe onOuvrir={setOuvert} />
            )}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function Pastille({ nombre }: { nombre?: number }) {
  if (!nombre) return null;
  return (
    <span className="rounded-full bg-terracotta px-1.5 py-0.5 text-[11px] font-semibold leading-none text-cream-50">
      {nombre}
    </span>
  );
}

function MesConversations({ onOuvrir }: { onOuvrir: (id: number) => void }) {
  const { data: fils = [], isLoading } = useMyConversations();
  if (isLoading) return <LoadingSpinner fullPage />;
  if (fils.length === 0) return <EmptyState title={fr.contact.aucuneConversation} />;
  return <ListeFils fils={fils} onOuvrir={onOuvrir} />;
}

function BoiteEquipe({ onOuvrir }: { onOuvrir: (id: number) => void }) {
  const { data: fils = [], isLoading } = useTeamConversations();
  if (isLoading) return <LoadingSpinner fullPage />;
  if (fils.length === 0) return <EmptyState title={fr.contact.aucuneATraiter} />;
  return <ListeFils fils={fils} onOuvrir={onOuvrir} montrerDemandeur />;
}

function ListeFils({
  fils,
  onOuvrir,
  montrerDemandeur = false,
}: {
  fils: Conversation[];
  onOuvrir: (id: number) => void;
  montrerDemandeur?: boolean;
}) {
  return (
    <div className="space-y-2">
      {fils.map((fil) => (
        <Card key={fil.id}>
          <CardContent className="p-0">
            <button
              onClick={() => onOuvrir(fil.id)}
              className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-muted/30"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-medium">
                  {/* Le point remplace un compteur : ce qui compte est qu'il y
                      ait du nouveau, pas combien. */}
                  {fil.a_signaler && (
                    <span
                      className="h-2 w-2 flex-shrink-0 rounded-full bg-terracotta"
                      aria-label={fr.contact.nouveau}
                    />
                  )}
                  {fil.sujet}
                </span>
                <StatutPuce statut={fil.statut} />
              </div>
              <span className="line-clamp-1 text-xs text-muted-foreground">
                {montrerDemandeur && fil.demandeur ? `${fil.demandeur} — ` : ''}
                {fil.dernier_message}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {fil.nombre_messages} {fr.contact.messages} ·{' '}
                {formatDate(fil.dernier_message_at ?? fil.created_at)}
              </span>
            </button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function NouvelleConversation({ onOuverte }: { onOuverte: (id: number) => void }) {
  const ouvrir = useOpenConversation();
  const toast = useToast();

  const form = useForm<ContactFormValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: { destinataire: 'compta', sujet: '', message: '' },
  });

  const destinataire = form.watch('destinataire');

  const onSubmit = (values: ContactFormValues) => {
    ouvrir.mutate(values, {
      onSuccess: (fil) => {
        toast.success(fr.contact.conversationOuverte);
        form.reset({ destinataire: values.destinataire, sujet: '', message: '' });
        onOuverte(fil.id);
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquarePlus className="h-4 w-4" aria-hidden />
          {fr.contact.formTitle}
        </CardTitle>
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
              <p className="mt-1 text-xs text-destructive">{form.formState.errors.sujet.message}</p>
            )}
          </div>

          <div>
            <Label required htmlFor="contact-message">
              {fr.contact.message}
            </Label>
            <Textarea id="contact-message" rows={6} {...form.register('message')} />
            {form.formState.errors.message && (
              <p className="mt-1 text-xs text-destructive">
                {form.formState.errors.message.message}
              </p>
            )}
          </div>

          <p className="text-xs text-muted-foreground">{fr.contact.identiteAuto}</p>

          <Button type="submit" loading={ouvrir.isPending}>
            <Send className="mr-1 h-4 w-4" />
            {fr.contact.envoyer}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
