/**
 * Lecture de codes-barres.
 *
 * Deux moteurs, dans cet ordre :
 *
 * 1. **`BarcodeDetector`**, l'API native du navigateur. Sur Android et Chrome
 *    elle s'appuie sur le décodeur du système — le même que l'appareil photo —
 *    et lit en une fraction de seconde un code que le décodage JavaScript
 *    manque complètement.
 * 2. **ZXing**, en repli, pour les navigateurs qui ne l'exposent pas encore
 *    (Firefox, et Safari hors iOS 17+).
 *
 * Le décodage JavaScript seul était la cause des échecs constatés : il exige
 * une image nette, bien cadrée et contrastée, là où le décodeur natif tolère
 * le flou et les angles.
 */

export type BarcodeFormatName =
  | 'ean_13'
  | 'ean_8'
  | 'upc_a'
  | 'upc_e'
  | 'code_128'
  | 'code_39'
  | 'itf'
  | 'qr_code';

/** Formats utiles ici : produits alimentaires du commerce, et QR en appoint. */
export const FORMATS_PRODUITS: BarcodeFormatName[] = [
  'ean_13',
  'ean_8',
  'upc_a',
  'upc_e',
  'code_128',
  'code_39',
  'itf',
  'qr_code',
];

interface DetectedBarcode {
  rawValue: string;
  format: string;
}

interface BarcodeDetectorLike {
  detect(source: CanvasImageSource): Promise<DetectedBarcode[]>;
}

type BarcodeDetectorCtor = {
  new (options?: { formats?: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
};

function ctorNatif(): BarcodeDetectorCtor | null {
  const w = window as unknown as { BarcodeDetector?: BarcodeDetectorCtor };
  return w.BarcodeDetector ?? null;
}

export function detecteurNatifDisponible(): boolean {
  return ctorNatif() !== null;
}

/**
 * Crée un détecteur natif restreint aux formats réellement supportés.
 *
 * Passer un format inconnu au constructeur le fait échouer entièrement : on
 * intersecte donc avec ce que le navigateur déclare savoir lire.
 */
export async function creerDetecteurNatif(): Promise<BarcodeDetectorLike | null> {
  const Ctor = ctorNatif();
  if (!Ctor) return null;
  try {
    let formats = FORMATS_PRODUITS as string[];
    if (Ctor.getSupportedFormats) {
      const supportes = await Ctor.getSupportedFormats();
      const commun = formats.filter((f) => supportes.includes(f));
      if (commun.length) formats = commun;
    }
    return new Ctor({ formats });
  } catch {
    return null;
  }
}

/**
 * Contraintes de piste qui font la différence sur un code-barres.
 *
 * `focusMode: continuous` est le réglage décisif : sans lui, la caméra reste
 * souvent sur une mise au point lointaine et l'image d'un code tenu à vingt
 * centimètres est floue — illisible par n'importe quel décodeur.
 */
export async function ameliorerPourCodeBarres(stream: MediaStream): Promise<void> {
  const piste = stream.getVideoTracks()[0];
  if (!piste) return;

  const capacites = (piste.getCapabilities?.() ?? {}) as Record<string, unknown>;
  const avancees: Record<string, unknown>[] = [];

  const focus = capacites.focusMode as string[] | undefined;
  if (Array.isArray(focus) && focus.includes('continuous')) {
    avancees.push({ focusMode: 'continuous' });
  }
  const expo = capacites.exposureMode as string[] | undefined;
  if (Array.isArray(expo) && expo.includes('continuous')) {
    avancees.push({ exposureMode: 'continuous' });
  }

  if (!avancees.length) return;
  try {
    await piste.applyConstraints({ advanced: avancees } as unknown as MediaTrackConstraints);
  } catch {
    /* Réglages refusés : la lecture reste possible, simplement moins fiable. */
  }
}

/** Un EAN-13 valide porte une clé de contrôle : elle écarte les lectures fausses. */
export function ean13Valide(code: string): boolean {
  if (!/^\d{13}$/.test(code)) return false;
  const chiffres = code.split('').map(Number);
  const somme = chiffres.slice(0, 12).reduce((acc, n, i) => acc + n * (i % 2 === 0 ? 1 : 3), 0);
  return (10 - (somme % 10)) % 10 === chiffres[12];
}
