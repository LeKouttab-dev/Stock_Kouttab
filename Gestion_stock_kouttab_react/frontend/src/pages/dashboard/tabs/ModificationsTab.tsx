import { useState } from 'react';
import { ChevronDown, ChevronRight, Info, CheckCircle2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useApproveModification, useRefuseModification, useStockModifications } from '@/api/endpoints/stock';
import { formatDateTime } from '@/lib/format';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { fr } from '@/lib/i18n/fr';

export function ModificationsTab() {
  const { can } = useAuth();
  const canApprove = can(ACTIONS.STOCK_APPROVE_MODS);
  const { data: mods = [], isLoading } = useStockModifications({ status: 'En attente', days: 30 });
  const approve = useApproveModification();
  const refuse = useRefuseModification();
  const toast = useToast();
  const [expanded, setExpanded] = useState<number | null>(null);

  if (isLoading) return <Skeleton className="h-64 w-full" />;

  if (mods.length === 0) {
    return (
      <Alert variant="success">
        <CheckCircle2 className="h-4 w-4" />
        <AlertTitle>{fr.dashboard.toutTraitees}</AlertTitle>
        <AlertDescription>{fr.dashboard.aucuneModifAValider}</AlertDescription>
      </Alert>
    );
  }

  const toggle = (id: number) => setExpanded((cur) => (cur === id ? null : id));

  const handleApprove = async (id: number) => {
    try {
      await approve.mutateAsync(id);
      toast.success('Modification approuvée');
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  const handleRefuse = async (id: number) => {
    try {
      await refuse.mutateAsync(id);
      toast.info('Modification refusée');
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <div className="space-y-3">
      <Alert variant="warning">
        <AlertDescription>
          📋 {mods.length} modification(s) en attente de validation
        </AlertDescription>
      </Alert>

      {mods.map((m, idx) => {
        const isOpen = expanded === m.id;
        return (
          <Card key={m.id}>
            <CardContent className="p-0">
              <button
                onClick={() => toggle(m.id)}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="font-medium">
                    🔄 Modification #{idx + 1} — {m.stock_nom} ({m.quantite_actuelle} →{' '}
                    {m.quantite_demandee})
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(m.date_demande)}
                </span>
              </button>

              {isOpen && (
                <div className="border-t bg-muted/10 px-4 py-3 space-y-1 text-sm">
                  <p>
                    <strong>Article :</strong> {m.stock_nom}
                  </p>
                  <p>
                    <strong>Catégorie :</strong> {m.categorie}
                  </p>
                  {m.sous_categorie && (
                    <p>
                      <strong>Sous-catégorie :</strong> {m.sous_categorie}
                    </p>
                  )}
                  <p>
                    <strong>Quantité actuelle :</strong> {m.quantite_actuelle}
                  </p>
                  <p>
                    <strong>Quantité demandée :</strong> {m.quantite_demandee}
                  </p>
                  <p>
                    <strong>Demandé par :</strong> {m.user_prenom} {m.user_nom}
                  </p>
                  <p>
                    <strong>Date :</strong> {formatDateTime(m.date_demande)}
                  </p>
                  {canApprove ? (
                    <div className="flex gap-2 pt-3">
                      <Button
                        size="sm"
                        onClick={() => handleApprove(m.id)}
                        loading={approve.isPending}
                      >
                        Approuver
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRefuse(m.id)}
                        loading={refuse.isPending}
                      >
                        Refuser
                      </Button>
                    </div>
                  ) : (
                    <Alert variant="info" className="mt-3">
                      <Info className="h-4 w-4" />
                      <AlertDescription>
                        Pour approuver ou refuser, allez dans <strong>Administration</strong>.
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
