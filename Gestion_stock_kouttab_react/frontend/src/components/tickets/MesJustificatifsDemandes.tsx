import { FileWarning } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useMyTickets } from '@/api/endpoints/tickets';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

/**
 * Ce que la comptabilité attend de moi.
 *
 * Contrepartie des relances par courriel : le bénévole retrouve la demande dans
 * l'application, à l'endroit même où il dépose la pièce. Un rappel qui n'existe
 * que dans une boîte aux lettres se perd entre deux messages.
 *
 * Rien à faire ici : la demande se solde en déposant la facture, juste en
 * dessous. C'est la comptabilité qui clôt, après avoir vérifié la pièce.
 */
export function MesJustificatifsDemandes() {
  const { data: tickets = [] } = useMyTickets();
  const ouverts = tickets.filter((t) => t.statut === 'ouvert');

  // Aucune demande : le bloc disparaît plutôt que d'afficher un vide. Un
  // encadré « rien à faire » sur chaque dépôt finirait par ne plus être lu.
  if (ouverts.length === 0) return null;

  return (
    <Card className="border-terracotta/40 bg-terracotta/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileWarning className="h-4 w-4 text-terracotta" aria-hidden />
          {fr.tickets.mesDemandes}
          <Badge variant="secondary">{ouverts.length}</Badge>
        </CardTitle>
        <p className="text-xs text-muted-foreground">{fr.tickets.mesDemandesAide}</p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {ouverts.map((ticket) => (
            <li key={ticket.id} className="rounded-md border bg-background px-3 py-2 text-sm">
              <p className="font-medium">{ticket.libelle}</p>
              <p className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                {ticket.montant_attendu != null && (
                  <span>{formatCurrency(Number(ticket.montant_attendu))}</span>
                )}
                {ticket.date_achat && <span>{formatDate(ticket.date_achat)}</span>}
                {ticket.fournisseur && <span>{ticket.fournisseur}</span>}
              </p>
              {ticket.description && (
                <p className="mt-1 text-xs text-muted-foreground">{ticket.description}</p>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
