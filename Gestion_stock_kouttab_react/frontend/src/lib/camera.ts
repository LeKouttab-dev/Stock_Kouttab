/**
 * Sélection de la caméra arrière principale.
 *
 * Deux pièges, tous deux vécus sur ce projet :
 *
 * 1. **L'ultra grand-angle.** Sur les téléphones à plusieurs objectifs,
 *    demander `facingMode: environment` avec une résolution très élevée pousse
 *    le navigateur à choisir le module ultra grand-angle (le « 0,5× »). Il a le
 *    plus petit capteur du bloc photo : l'image est molle et déformée sur les
 *    bords, exactement ce qu'il ne faut pas pour lire le montant d'un ticket.
 *    On énumère donc les objectifs et on écarte ceux dont le libellé trahit un
 *    ultra grand-angle.
 *
 * 2. **Le zoom résiduel.** Une caméra rouvre parfois avec le zoom de la session
 *    précédente. On le remet à 1 quand la piste l'expose.
 *
 * L'énumération n'est possible qu'après une première autorisation : avant, les
 * libellés sont vides. La fonction procède donc en deux temps, et se contente
 * du flux initial si rien de mieux ne se présente.
 */

const INDICES_ULTRA_WIDE = ['ultra', 'wide angle', 'grand angle', 'grand-angle', '0.5', '0,5'];

function estUltraWide(label: string): boolean {
  const l = label.toLowerCase();
  // « wide » seul ne suffit pas : « Back Wide Camera » désigne l'objectif
  // principal sur iOS, alors que « Back Ultra Wide Camera » est le 0,5×.
  return INDICES_ULTRA_WIDE.some((mot) => l.includes(mot));
}

/** Résolution demandée : suffisante pour lire un ticket, sans exiger l'impossible. */
const IDEAL = { width: { ideal: 1920 }, height: { ideal: 1080 } };

export async function openBackCamera(): Promise<MediaStream> {
  const premier = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { facingMode: { ideal: 'environment' }, ...IDEAL },
  });

  let stream = premier;

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const camerasArriere = devices.filter(
      (d) => d.kind === 'videoinput' && /back|arrière|rear|environment/i.test(d.label),
    );

    if (camerasArriere.length > 1) {
      const principale = camerasArriere.find((d) => !estUltraWide(d.label));
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

  const piste = stream.getVideoTracks()[0];
  const capacites = piste?.getCapabilities?.() as { zoom?: { min: number } } | undefined;
  if (piste && capacites?.zoom) {
    try {
      // `zoom` est supporté par les navigateurs mobiles mais absent des types
      // standards, d'où le passage par `unknown`.
      await piste.applyConstraints({
        advanced: [{ zoom: 1 }],
      } as unknown as MediaTrackConstraints);
    } catch {
      /* Zoom non réglable : sans conséquence. */
    }
  }

  return stream;
}
