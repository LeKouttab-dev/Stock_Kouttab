/**
 * Choix et ouverture de la caméra.
 *
 * Deux pièges, tous deux vécus sur ce projet :
 *
 * 1. **L'ultra grand-angle.** Sur les téléphones à plusieurs objectifs,
 *    `facingMode: environment` laisse le navigateur choisir, et il retient
 *    volontiers le module ultra grand-angle (le « 0,5× »). C'est le plus petit
 *    capteur du bloc photo : image molle, déformée sur les bords — exactement ce
 *    qu'il ne faut pas pour lire le montant d'un ticket.
 *
 * 2. **Le zoom résiduel.** Une caméra rouvre parfois avec le zoom de la session
 *    précédente. On le remet à 1 quand la piste l'expose.
 *
 * L'heuristique de sélection automatique ne suffit pas toujours : sur Android,
 * les libellés sont souvent génériques (« camera2 0, facing back »), sans rien
 * qui distingue l'ultra grand-angle. D'où le choix manuel, mémorisé.
 */

const CLE_MEMOIRE = 'kouttab.camera.deviceId';

const INDICES_ULTRA_WIDE = ['ultra', 'wide angle', 'grand angle', 'grand-angle', '0.5', '0,5'];

function estUltraWide(label: string): boolean {
  const l = label.toLowerCase();
  // « wide » seul ne suffit pas : « Back Wide Camera » désigne l'objectif
  // principal sur iOS, alors que « Back Ultra Wide Camera » est le 0,5×.
  return INDICES_ULTRA_WIDE.some((mot) => l.includes(mot));
}

function estArriere(label: string): boolean {
  return /back|arrière|arriere|rear|environment/i.test(label);
}

/**
 * Résolution demandée. Volontairement haute : le document est ensuite redressé,
 * ré-encodé puis converti en PDF, et chaque étape coûte du détail. Partir d'une
 * image large laisse de la marge ; `ideal` n'impose rien, la caméra fournit ce
 * qu'elle peut.
 */
const IDEAL: MediaTrackConstraints = {
  width: { ideal: 3840 },
  height: { ideal: 2160 },
};

export interface CameraDisponible {
  deviceId: string;
  label: string;
  /** Vrai quand le libellé trahit un ultra grand-angle. */
  ultraWide: boolean;
}

/**
 * Liste les caméras exploitables.
 *
 * Les libellés ne sont renseignés qu'après une première autorisation : appeler
 * cette fonction avant `openCamera` renvoie des entrées anonymes.
 */
export async function listCameras(): Promise<CameraDisponible[]> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices
      .filter((d) => d.kind === 'videoinput')
      .map((d, i) => ({
        deviceId: d.deviceId,
        label: d.label || `Caméra ${i + 1}`,
        ultraWide: estUltraWide(d.label),
      }));
  } catch {
    return [];
  }
}

export function getRememberedCamera(): string | null {
  try {
    return localStorage.getItem(CLE_MEMOIRE);
  } catch {
    return null;
  }
}

export function rememberCamera(deviceId: string): void {
  try {
    localStorage.setItem(CLE_MEMOIRE, deviceId);
  } catch {
    /* Stockage indisponible (navigation privée) : le choix vaut pour la session. */
  }
}

async function reglerZoomANeutre(stream: MediaStream): Promise<void> {
  const piste = stream.getVideoTracks()[0];
  const capacites = piste?.getCapabilities?.() as { zoom?: { min: number } } | undefined;
  if (!piste || !capacites?.zoom) return;
  try {
    // `zoom` est supporté par les navigateurs mobiles mais absent des types
    // standards, d'où le passage par `unknown`.
    await piste.applyConstraints({ advanced: [{ zoom: 1 }] } as unknown as MediaTrackConstraints);
  } catch {
    /* Zoom non réglable : sans conséquence. */
  }
}

/**
 * Ouvre la caméra demandée, ou la meilleure caméra arrière disponible.
 *
 * `deviceId` explicite l'emporte toujours : c'est le choix de l'utilisateur, il
 * ne doit pas être corrigé par l'heuristique.
 */
export async function openCamera(deviceId?: string | null): Promise<MediaStream> {
  if (deviceId) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { deviceId: { exact: deviceId }, ...IDEAL },
      });
      await reglerZoomANeutre(stream);
      return stream;
    } catch {
      // Caméra débranchée, ou identifiant périmé après changement de navigateur :
      // on retombe sur la sélection automatique plutôt que d'échouer.
    }
  }

  const premier = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { facingMode: { ideal: 'environment' }, ...IDEAL },
  });

  let stream = premier;

  try {
    const cameras = await listCameras();
    const arriere = cameras.filter((c) => estArriere(c.label));

    if (arriere.length > 1) {
      const principale = arriere.find((c) => !c.ultraWide);
      const actuelle = premier.getVideoTracks()[0]?.getSettings().deviceId;

      if (principale && principale.deviceId !== actuelle) {
        // On n'échange qu'une fois le remplaçant obtenu : si la demande échoue,
        // mieux vaut un flux ultra grand-angle que pas d'image du tout.
        const remplacant = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { deviceId: { exact: principale.deviceId }, ...IDEAL },
        });
        premier.getTracks().forEach((t) => t.stop());
        stream = remplacant;
      }
    }
  } catch {
    /* Énumération refusée ou objectif indisponible : on garde le flux initial. */
  }

  await reglerZoomANeutre(stream);
  return stream;
}

/** Conservé pour compatibilité : équivaut à `openCamera()` sans choix explicite. */
export const openBackCamera = () => openCamera();
