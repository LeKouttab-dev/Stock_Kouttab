/** Côté le plus long d'une image envoyée au recadrage.
 *
 * Une photo de téléphone récente dépasse 4000 px : au-delà, on paie de la bande
 * passante et de la mémoire sans rien gagner en lisibilité sur un ticket de
 * caisse. La borne s'applique AVANT le choix des coins, donc les coordonnées
 * envoyées au serveur sont déjà dans l'espace de l'image réduite — il n'y a
 * aucune remise à l'échelle à faire ensuite, et donc aucune occasion de se
 * tromper d'un facteur.
 */
const COTE_MAX = 3000;

export interface ImageScannable {
  /** JPEG, seul format que `/scan/detect` et `/scan/apply` acceptent avec PNG. */
  blob: Blob;
  largeur: number;
  hauteur: number;
}

/**
 * Prépare un fichier déposé pour le recadrage, ou dit qu'il ne s'y prête pas.
 *
 * Rend `null` — et c'est un cas NORMAL, pas une erreur — pour tout ce qui n'est
 * pas une image décodable par le navigateur :
 *
 * - un **PDF** : il est déjà au format attendu par la comptabilité, et le
 *   redécouper supposerait de le rendre d'abord en image, donc de dégrader un
 *   document qui n'a rien à y gagner ;
 * - un **HEIC** sous Chrome ou Firefox, qui ne savent pas le décoder. Safari le
 *   décode, l'iPhone passe donc par le recadrage — ailleurs, le fichier part
 *   tel quel et le serveur le convertit comme avant.
 *
 * L'appelant traite ce `null` en laissant le fichier intact : refuser le dépôt
 * parce que le recadrage est impossible retirerait une fonctionnalité qui
 * marchait.
 */
export async function versImageScannable(file: File): Promise<ImageScannable | null> {
  if (!file.type.startsWith('image/')) return null;
  if (typeof createImageBitmap !== 'function') return null;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // Format que ce navigateur ne décode pas. Rien à signaler : le fichier
    // suivra le chemin habituel.
    return null;
  }

  try {
    const facteur = Math.min(1, COTE_MAX / Math.max(bitmap.width, bitmap.height));
    const largeur = Math.round(bitmap.width * facteur);
    const hauteur = Math.round(bitmap.height * facteur);

    const canvas = document.createElement('canvas');
    canvas.width = largeur;
    canvas.height = hauteur;
    const contexte = canvas.getContext('2d');
    if (!contexte) return null;
    contexte.drawImage(bitmap, 0, 0, largeur, hauteur);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.92),
    );
    return blob ? { blob, largeur, hauteur } : null;
  } finally {
    // Sans cette libération, chaque fichier déposé retient sa pleine résolution
    // décodée en mémoire tant que l'onglet reste ouvert.
    bitmap.close?.();
  }
}
