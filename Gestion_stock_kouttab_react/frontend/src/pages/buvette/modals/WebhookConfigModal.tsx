import { Copy } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useConfigureWebhook, useDeleteWebhook, useWebhookStatus } from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import { copyToClipboard } from '@/lib/utils';
import { formatDateTime } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

interface WebhookConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function WebhookConfigModal({ open, onOpenChange }: WebhookConfigModalProps) {
  const status = useWebhookStatus();
  const configure = useConfigureWebhook();
  const remove = useDeleteWebhook();
  const toast = useToast();

  // Trois etats, pas deux : HelloAsso ne permet pas de relire l'URL enregistree,
  // donc l'absence de confirmation n'est pas une absence de webhook.
  const configured = status.data?.configured ?? null;
  const salesCount = status.data?.sales_count ?? 0;
  const lastSaleAt = status.data?.last_sale_at ?? null;

  const handleActivate = () => {
    configure.mutate(undefined, { onSuccess: () => toast.success(fr.buvette.webhookActivated) });
  };

  const handleDeactivate = () => {
    remove.mutate(undefined, { onSuccess: () => toast.success(fr.buvette.webhookDeactivated) });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{fr.buvette.webhookTitle}</DialogTitle>
          <DialogDescription>{fr.buvette.webhookExplanation}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-md border bg-muted/30 px-4 py-3">
            <span className="text-sm font-medium">Statut</span>
            {status.isLoading ? (
              <span className="text-xs text-muted-foreground">{fr.common.loading}</span>
            ) : configured === true ? (
              <Badge variant="success">{fr.buvette.webhookConfigured}</Badge>
            ) : configured === false ? (
              <Badge variant="outline">{fr.buvette.webhookNotConfigured}</Badge>
            ) : (
              <Badge variant="outline">{fr.buvette.webhookUnknown}</Badge>
            )}
          </div>

          {status.data?.url && (
            <Alert variant="info">
              <AlertTitle>URL configurée</AlertTitle>
              <AlertDescription>
                <code className="break-all text-xs">{status.data.url}</code>
              </AlertDescription>
            </Alert>
          )}

          {configured === null && (
            <Alert variant="info">
              <AlertTitle>{fr.buvette.webhookUnverifiableTitle}</AlertTitle>
              <AlertDescription>{fr.buvette.webhookUnverifiable}</AlertDescription>
            </Alert>
          )}

          {/* L'adresse à recopier, toujours affichée.
              HelloAsso réserve l'enregistrement automatique à ses comptes
              partenaires et refuse le nôtre par un 403 au corps vide. Le bouton
              d'activation ne peut donc pas aboutir : reste à coller l'adresse
              dans leur interface — et un jeton de 43 caractères ne se recopie
              pas de mémoire. */}
          {status.data?.url_a_enregistrer && (
            <Alert variant="warning">
              <AlertTitle>{fr.buvette.webhookManuelTitre}</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{fr.buvette.webhookManuel}</p>
                <code className="block break-all rounded bg-background px-2 py-1 text-xs">
                  {status.data.url_a_enregistrer}
                </code>
                <p className="text-xs">{fr.buvette.webhookJetonAvertissement}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    await copyToClipboard(status.data!.url_a_enregistrer as string);
                    toast.success(fr.buvette.webhookUrlCopiee);
                  }}
                >
                  <Copy className="mr-1 h-3.5 w-3.5" />
                  {fr.buvette.webhookCopierUrl}
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {salesCount > 0 && (
            <Alert variant="success">
              <AlertTitle>{fr.buvette.webhookProofTitle}</AlertTitle>
              <AlertDescription>
                {salesCount} {fr.buvette.webhookProofSales}
                {lastSaleAt
                  ? ` ${fr.buvette.webhookProofLast} ${formatDateTime(lastSaleAt)}.`
                  : '.'}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.close}
          </Button>
          {/* Etat inconnu : on propose les deux actions plutot que de deviner.
              Reenregistrer est sans risque, HelloAsso remplace simplement l'URL. */}
          {configured !== false && (
            <Button
              type="button"
              variant="destructive"
              loading={remove.isPending}
              onClick={handleDeactivate}
            >
              {fr.buvette.webhookDeactivate}
            </Button>
          )}
          {configured !== true && (
            <Button type="button" loading={configure.isPending} onClick={handleActivate}>
              {fr.buvette.webhookActivate}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
