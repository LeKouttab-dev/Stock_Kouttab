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

  const isConfigured = status.data?.isConfigured ?? false;

  const handleActivate = async () => {
    try {
      await configure.mutateAsync(undefined);
      toast.success(fr.buvette.webhookActivated);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  const handleDeactivate = async () => {
    try {
      await remove.mutateAsync();
      toast.success(fr.buvette.webhookDeactivated);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
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
            ) : isConfigured ? (
              <Badge variant="success">{fr.buvette.webhookConfigured}</Badge>
            ) : (
              <Badge variant="outline">{fr.buvette.webhookNotConfigured}</Badge>
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
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.close}
          </Button>
          {isConfigured ? (
            <Button
              type="button"
              variant="destructive"
              loading={remove.isPending}
              onClick={handleDeactivate}
            >
              {fr.buvette.webhookDeactivate}
            </Button>
          ) : (
            <Button type="button" loading={configure.isPending} onClick={handleActivate}>
              {fr.buvette.webhookActivate}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
