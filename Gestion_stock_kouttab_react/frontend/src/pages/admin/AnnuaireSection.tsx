import { Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnnuaire } from '@/api/endpoints/users';
import { fr } from '@/lib/i18n/fr';

/**
 * Annuaire des bénévoles inscrits, **en lecture seule**.
 *
 * La comptabilité rembourse ces personnes et leur réclame des pièces : savoir
 * qui est inscrit et sous quel rôle fait partie de son travail. Gérer les
 * comptes, non — cela reste au Super Admin, dans la section voisine.
 *
 * Aucun RIB ici : c'est un annuaire, et la coordonnée bancaire s'affiche là où
 * elle sert, sur la note de frais à payer.
 */
export function AnnuaireSection() {
  const { data: membres = [], isLoading } = useAnnuaire();

  const actifs = membres.filter((m) => m.validation_status === 'active');
  const autres = membres.filter((m) => m.validation_status !== 'active');

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" aria-hidden />
          {fr.annuaire.titre}
          <Badge variant="secondary">{actifs.length}</Badge>
        </CardTitle>
        <p className="text-xs text-muted-foreground">{fr.annuaire.sousTitre}</p>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : membres.length === 0 ? (
          <p className="text-sm text-muted-foreground">{fr.annuaire.aucun}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">{fr.annuaire.nom}</th>
                  <th className="py-2 pr-3 font-medium">{fr.annuaire.role}</th>
                  <th className="py-2 pr-3 font-medium">{fr.annuaire.contact}</th>
                </tr>
              </thead>
              <tbody>
                {[...actifs, ...autres].map((membre) => (
                  <tr key={membre.id} className="border-b last:border-0">
                    <td className="py-2 pr-3">
                      <span className="font-medium">
                        {[membre.prenom, membre.nom].filter(Boolean).join(' ') || membre.username}
                      </span>
                      {membre.validation_status !== 'active' && (
                        <Badge variant="outline" className="ml-2">
                          {membre.validation_status === 'pending'
                            ? fr.annuaire.enAttente
                            : fr.annuaire.refuse}
                        </Badge>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">{membre.role}</td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {membre.email || membre.telephone || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
