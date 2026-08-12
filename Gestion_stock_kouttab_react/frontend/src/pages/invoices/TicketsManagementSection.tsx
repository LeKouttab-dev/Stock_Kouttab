import { useState } from 'react';
import { Bell, Check, FileWarning, Plus, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useCloseTicket,
  useCreateTicket,
  useRemindTicket,
  useTicketRecipients,
  useTickets,
} from '@/api/endpoints/tickets';
import { useToast } from '@/hooks/useToast';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

/**
 * Demandes de justificatif : ouvrir, relancer, clore.
 *
 * Placée sur l'écran des factures parce que c'est une facture qu'on réclame :
 * la comptabilité constate le manque en parcourant les pièces reçues, et ouvre
 * la demande sans changer de page.
 *
 * La clôture est manuelle et le rattachement de la pièce aussi : deviner qu'une
 * facture déposée correspond à un ticket le fermerait à tort dès que le
 * bénévole dépose autre chose, et les relances cesseraient alors que la pièce
 * attendue manque toujours.
 */
export function TicketsManagementSection() {
  const { data: tickets = [], isLoading } = useTickets();
  const { data: destinataires = [] } = useTicketRecipients();
  const create = useCreateTicket();
  const close = useCloseTicket();
  const remind = useRemindTicket();
  const toast = useToast();

  const [ouvertureVisible, setOuvertureVisible] = useState(false);
  const [idUser, setIdUser] = useState<string>('');
  const [libelle, setLibelle] = useState('');
  const [montant, setMontant] = useState('');
  const [dateAchat, setDateAchat] = useState('');
  const [fournisseur, setFournisseur] = useState('');
  const [description, setDescription] = useState('');

  const ouverts = tickets.filter((t) => t.statut === 'ouvert');
  const clos = tickets.filter((t) => t.statut !== 'ouvert');

  const reinitialiser = () => {
    setIdUser('');
    setLibelle('');
    setMontant('');
    setDateAchat('');
    setFournisseur('');
    setDescription('');
    setOuvertureVisible(false);
  };

  const ouvrir = () => {
    if (!idUser || !libelle.trim()) return;
    create.mutate(
      {
        id_user: Number(idUser),
        libelle: libelle.trim(),
        montant_attendu: montant || undefined,
        date_achat: dateAchat || undefined,
        fournisseur: fournisseur.trim() || undefined,
        description: description.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success(fr.tickets.ouvert, fr.tickets.ouvertAide);
          reinitialiser();
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileWarning className="h-4 w-4" aria-hidden />
              {fr.tickets.titre}
              {ouverts.length > 0 && <Badge variant="secondary">{ouverts.length}</Badge>}
            </CardTitle>
            <p className="text-xs text-muted-foreground">{fr.tickets.sousTitre}</p>
          </div>
          <Button
            variant={ouvertureVisible ? 'outline' : 'primary'}
            size="sm"
            onClick={() => setOuvertureVisible(!ouvertureVisible)}
          >
            <Plus className="h-4 w-4" />
            {fr.tickets.demander}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {ouvertureVisible && (
          <div className="space-y-3 rounded-md border bg-muted/10 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label required>{fr.tickets.benevole}</Label>
                <Select value={idUser} onValueChange={setIdUser}>
                  <SelectTrigger>
                    <SelectValue placeholder={fr.tickets.choisirBenevole} />
                  </SelectTrigger>
                  <SelectContent>
                    {destinataires.map((d) => (
                      <SelectItem key={d.id} value={String(d.id)}>
                        {d.nom_complet}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ticket_libelle" required>
                  {fr.tickets.libelle}
                </Label>
                <Input
                  id="ticket_libelle"
                  value={libelle}
                  onChange={(e) => setLibelle(e.target.value)}
                  placeholder={fr.tickets.libellePlaceholder}
                />
              </div>
            </div>

            {/* Tout ce qui suit est facultatif : la comptabilité ouvre la
                demande avec ce qu'elle sait, et le courriel de relance ne
                mentionne que les champs remplis. */}
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="ticket_montant">{fr.tickets.montant}</Label>
                <Input
                  id="ticket_montant"
                  type="number"
                  step="0.01"
                  min="0"
                  value={montant}
                  onChange={(e) => setMontant(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ticket_date">{fr.tickets.dateAchat}</Label>
                <Input
                  id="ticket_date"
                  type="date"
                  value={dateAchat}
                  onChange={(e) => setDateAchat(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ticket_fournisseur">{fr.tickets.fournisseur}</Label>
                <Input
                  id="ticket_fournisseur"
                  value={fournisseur}
                  onChange={(e) => setFournisseur(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ticket_description">{fr.tickets.precision}</Label>
              <Textarea
                id="ticket_description"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={reinitialiser}>
                {fr.common.cancel}
              </Button>
              <Button
                size="sm"
                onClick={ouvrir}
                loading={create.isPending}
                disabled={!idUser || !libelle.trim()}
              >
                {fr.tickets.envoyerDemande}
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <Skeleton className="h-24" />
        ) : tickets.length === 0 ? (
          <p className="text-sm text-muted-foreground">{fr.tickets.aucun}</p>
        ) : (
          <ul className="space-y-2">
            {[...ouverts, ...clos].map((ticket) => (
              <li
                key={ticket.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-md border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {ticket.libelle}
                    {ticket.statut !== 'ouvert' && (
                      <Badge variant="outline">
                        {ticket.statut === 'clos' ? fr.tickets.clos : fr.tickets.annule}
                      </Badge>
                    )}
                  </p>
                  <p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                    <span>{ticket.user_full_name ?? '—'}</span>
                    {ticket.montant_attendu != null && (
                      <span>{formatCurrency(Number(ticket.montant_attendu))}</span>
                    )}
                    {ticket.date_achat && <span>{formatDate(ticket.date_achat)}</span>}
                    {ticket.statut === 'ouvert' && (
                      <span>
                        {ticket.rappels_envoyes} {fr.tickets.rappels}
                      </span>
                    )}
                  </p>
                </div>

                {ticket.statut === 'ouvert' && (
                  <div className="flex flex-shrink-0 gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      title={fr.tickets.relancer}
                      aria-label={`${fr.tickets.relancer} — ${ticket.libelle}`}
                      onClick={() =>
                        remind.mutate(ticket.id, {
                          onSuccess: () => toast.success(fr.tickets.relance),
                        })
                      }
                    >
                      <Bell className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      title={fr.tickets.clore}
                      aria-label={`${fr.tickets.clore} — ${ticket.libelle}`}
                      onClick={() =>
                        close.mutate(
                          { id: ticket.id },
                          { onSuccess: () => toast.success(fr.tickets.cloture) },
                        )
                      }
                    >
                      <Check className="h-4 w-4 text-forest" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      title={fr.tickets.annuler}
                      aria-label={`${fr.tickets.annuler} — ${ticket.libelle}`}
                      onClick={() => {
                        if (!confirm(fr.tickets.confirmAnnulation)) return;
                        close.mutate({ id: ticket.id, annule: true });
                      }}
                    >
                      <X className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
