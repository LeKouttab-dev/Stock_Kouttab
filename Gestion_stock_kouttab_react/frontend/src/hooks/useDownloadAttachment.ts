import { useCallback, useState } from 'react';
import { api, extractErrorMessage } from '@/api/client';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Télécharge un justificatif protégé par JWT.
 *
 * Les liens pointaient directement sur l'API (`<a href={url} download>`) : un
 * navigateur ne joint aucun en-tête `Authorization` à une navigation, si bien
 * que chaque téléchargement revenait en `AUTH_1011 Not authenticated`. Passer
 * par l'instance axios rétablit le jeton, et l'intercepteur de rafraîchissement
 * couvre le cas du token expiré.
 *
 * `filename` permet de servir la pièce sous son nom comptable plutôt que sous
 * le nom d'origine du téléphone (`_p9.png`), illisible pour le comptable.
 */
export function useDownloadAttachment() {
  const toast = useToast();
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const download = useCallback(
    async (url: string, filename: string, fileId?: number) => {
      setDownloadingId(fileId ?? null);
      try {
        const { data } = await api.get<Blob>(url, { responseType: 'blob' });

        const objectUrl = URL.createObjectURL(data);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        // Révocation différée : Safari interrompt le téléchargement si l'URL
        // est libérée dans la foulée du clic.
        setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
      } catch (e) {
        toast.error(fr.common.error, extractErrorMessage(e));
      } finally {
        setDownloadingId(null);
      }
    },
    [toast],
  );

  return { download, downloadingId };
}
