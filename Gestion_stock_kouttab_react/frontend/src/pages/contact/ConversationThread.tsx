import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Send } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useConversation,
  useReplyToConversation,
  useSetConversationStatut,
} from '@/api/endpoints/contact';
import type { ConversationStatut } from '@/types/api';
import { cn } from '@/lib/utils';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

const STATUTS: ConversationStatut[] = ['ouverte', 'en_cours', 'traitee'];

const LIBELLE_STATUT: Record<ConversationStatut, string> = {
  ouverte: fr.contact.statutOuverte,
  en_cours: fr.contact.statutEnCours,
  traitee: fr.contact.statutTraitee,
};

/**
 * Un fil, ses messages, et de quoi répondre.
 *
 * Pas de temps réel : le fil se recharge à chaque envoi, et c'est tout. Une
 * question de bénévole se traite dans la journée, pas à la seconde — ouvrir une
 * connexion permanente pour cela coûterait un serveur de plus à surveiller.
 */
export function ConversationThread({
  conversationId,
  onBack,
  gestion = false,
}: {
  conversationId: number;
  onBack: () => void;
  /** L'équipe : elle peut changer le statut du fil. */
  gestion?: boolean;
}) {
  const { data: fil, isLoading } = useConversation(conversationId);
  const repondre = useReplyToConversation();
  const changerStatut = useSetConversationStatut();
  const toast = useToast();
  const [brouillon, setBrouillon] = useState('');
  const finDuFil = useRef<HTMLDivElement>(null);

  // Le dernier message est celui qui compte : sans cela, un fil un peu long
  // s'ouvre sur la question posée trois semaines plus tôt.
  useEffect(() => {
    finDuFil.current?.scrollIntoView({ block: 'nearest' });
  }, [fil?.nombre_messages]);

  if (isLoading || !fil) return <LoadingSpinner fullPage />;

  const envoyer = () => {
    const corps = brouillon.trim();
    if (!corps) return;
    repondre.mutate({ id: fil.id, corps }, { onSuccess: () => setBrouillon('') });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          {fr.contact.retourListe}
        </Button>

        {gestion ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{fr.contact.statut}</span>
            <Select
              value={fil.statut}
              onValueChange={(v) =>
                changerStatut.mutate(
                  { id: fil.id, statut: v as ConversationStatut },
                  { onSuccess: () => toast.success(fr.contact.statutMisAJour) },
                )
              }
            >
              <SelectTrigger className="h-8 w-[170px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUTS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {LIBELLE_STATUT[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <StatutPuce statut={fil.statut} />
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold">{fil.sujet}</h2>
        <p className="text-xs text-muted-foreground">
          {gestion && fil.demandeur ? `${fil.demandeur} — ` : ''}
          {fil.destinataire === 'compta' ? fr.contact.versCompta : fr.contact.versAdmin}
        </p>
      </div>

      <Card>
        <CardContent className="max-h-[50vh] space-y-3 overflow-y-auto p-4">
          {fil.messages.map((m) => (
            <div
              key={m.id}
              className={cn('flex flex-col gap-1', m.est_moi ? 'items-end' : 'items-start')}
            >
              <div
                className={cn(
                  'max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm',
                  m.est_moi ? 'bg-terracotta text-cream-50' : 'bg-muted',
                )}
              >
                {m.corps}
              </div>
              <span className="text-[11px] text-muted-foreground">
                {m.auteur_nom}
                {m.de_l_equipe ? ` · ${fr.contact.equipe}` : ''}
              </span>
            </div>
          ))}
          <div ref={finDuFil} />
        </CardContent>
      </Card>

      {/* Répondre reste possible sur un fil traité : une précision demandée
          après coup rouvre le fil côté serveur, plutôt que de se perdre. */}
      <div className="space-y-2">
        <Textarea
          rows={3}
          value={brouillon}
          onChange={(e) => setBrouillon(e.target.value)}
          placeholder={fr.contact.reponsePlaceholder}
          aria-label={fr.contact.votreReponse}
        />
        <Button onClick={envoyer} loading={repondre.isPending} disabled={!brouillon.trim()}>
          <Send className="mr-1 h-4 w-4" />
          {fr.contact.repondre}
        </Button>
      </div>
    </div>
  );
}

export function StatutPuce({ statut }: { statut: ConversationStatut }) {
  return (
    <span
      className={cn(
        'rounded-full px-2.5 py-1 text-[11px] font-semibold',
        statut === 'traitee' && 'bg-emerald-100 text-emerald-800',
        statut === 'en_cours' && 'bg-amber-100 text-amber-900',
        statut === 'ouverte' && 'bg-terracotta/10 text-terracotta',
      )}
    >
      {LIBELLE_STATUT[statut]}
    </span>
  );
}
