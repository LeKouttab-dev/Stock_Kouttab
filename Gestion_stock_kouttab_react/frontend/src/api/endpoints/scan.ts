import { api } from '../client';
import { useApiMutation } from '@/hooks/useApiMutation';
import type { ScanCorner, ScanDetectResponse } from '@/types/api';

/**
 * Le scan se fait en deux appels : `detect` propose un cadrage que l'écran
 * affiche par-dessus la photo, `apply` produit l'image redressée une fois le
 * cadrage confirmé ou corrigé. Une détection automatique se trompe (nappe à
 * motifs, ticket blanc sur table blanche) ; sans reprise manuelle, le déposant
 * n'aurait aucun recours.
 */

// L'instance axios impose `application/json` : il faut le surcharger pour un
// envoi de fichier. La valeur est écrite en dur, sans *boundary*, comme sur les
// autres dépôts de l'application : en environnement navigateur axios réécrit
// l'en-tête avec la boundary correcte dès que le corps est un FormData.
const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } } as const;

/**
 * Construit le corps multipart attendu par `app/api/v1/endpoints/scan.py`.
 *
 * Isolée de l'envoi pour être vérifiable : les noms de champs sont le contrat
 * avec le serveur, et c'est très exactement le genre de détail qui casse en
 * silence — quatre décalages de ce type ont été trouvés dans l'application.
 */
export function buildScanFormData(params: {
  photo: Blob;
  corners?: ScanCorner[] | null;
  enhance?: boolean;
  output?: 'pdf' | 'jpeg';
}): FormData {
  const form = new FormData();
  form.append('file', params.photo, 'scan.jpg');
  if (params.corners) form.append('corners', JSON.stringify(params.corners));
  form.append('enhance', String(params.enhance ?? true));
  // PDF par défaut : c'est la pièce que reçoit le comptable, pas une photo.
  form.append('output', params.output ?? 'pdf');
  return form;
}

async function detectDocument(photo: Blob): Promise<ScanDetectResponse> {
  const form = new FormData();
  form.append('file', photo, 'scan.jpg');
  const { data } = await api.post<ScanDetectResponse>('/scan/detect', form, MULTIPART);
  return data;
}

async function applyScan(params: {
  photo: Blob;
  corners?: ScanCorner[] | null;
  enhance?: boolean;
  output?: 'pdf' | 'jpeg';
}): Promise<Blob> {
  const { data } = await api.post<Blob>('/scan/apply', buildScanFormData(params), {
    ...MULTIPART,
    responseType: 'blob',
  });
  return data;
}

export function useDetectDocument() {
  // silentToast : une détection qui échoue n'est pas une erreur à signaler —
  // l'écran bascule simplement sur un cadrage manuel.
  return useApiMutation({ mutationFn: detectDocument, silentToast: true });
}

export function useApplyScan() {
  return useApiMutation({ mutationFn: applyScan });
}
