import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Camera, Check, RotateCcw, Maximize } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useApplyScan, useDetectDocument } from '@/api/endpoints/scan';
import {
  getRememberedCamera,
  listCameras,
  openCamera,
  rememberCamera,
  type CameraDisponible,
} from '@/lib/camera';
import { fr } from '@/lib/i18n/fr';
import type { ScanCorner } from '@/types/api';

export interface DocumentScannerProps {
  open: boolean;
  onClose: () => void;
  /** Reçoit le justificatif redressé en PDF, prêt à joindre au dépôt. */
  onScanned: (file: File) => void;
}

type Etape = 'camera' | 'cadrage';

/** Ordre imposé par le serveur : haut-gauche, haut-droit, bas-droit, bas-gauche. */
const ARETES: Array<[number, number]> = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 0],
];

function isSecureContextOk(): boolean {
  if (typeof window === 'undefined') return true;
  if (window.location.protocol === 'https:') return true;
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

/**
 * Scanner de justificatifs : photo, détection des bords, redressement, PDF.
 *
 * Le cadrage se manipule par huit poignées — quatre coins et le milieu de
 * chaque côté. Les milieux translatent le côté entier : recadrer une facture
 * dont un seul bord dépasse ne demande alors qu'un geste au lieu de deux, et
 * c'est ce qui rend le réglage rapide sur les scanners du commerce.
 *
 * La correction de perspective est faite côté serveur
 * (`app/services/document_scan.py`) : un document photographié de biais est
 * redressé à partir de ses quatre coins, quel que soit l'angle de prise de vue.
 */
export function DocumentScanner({ open, onClose, onScanned }: DocumentScannerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const [etape, setEtape] = useState<Etape>('camera');
  const [erreur, setErreur] = useState<string | null>(null);
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [apercu, setApercu] = useState<string | null>(null);
  const [taille, setTaille] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [coins, setCoins] = useState<ScanCorner[]>([]);
  const [pointActif, setPointActif] = useState<{ type: 'coin' | 'arete'; index: number } | null>(
    null,
  );
  const dernierPointeur = useRef<{ x: number; y: number } | null>(null);
  const [cameras, setCameras] = useState<CameraDisponible[]>([]);
  const [cameraChoisie, setCameraChoisie] = useState<string | null>(getRememberedCamera());

  const detect = useDetectDocument();
  const apply = useApplyScan();

  const arreterCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  /* ---------- Caméra ---------- */
  // `videoPret` est mis à jour par une ref callback : le contenu du dialogue est
  // monté dans un portail, donc `videoRef.current` est encore `null` quand
  // l'effet s'exécute à l'ouverture. Démarrer la caméra à ce moment-là revenait
  // à l'attacher à rien — d'où un écran noir permanent.
  const [videoPret, setVideoPret] = useState(false);
  const attacherVideo = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    setVideoPret(Boolean(el));
  }, []);

  useEffect(() => {
    if (!open || etape !== 'camera' || !videoPret) return;

    if (!isSecureContextOk()) {
      setErreur(fr.scanner.httpsRequired);
      return;
    }

    let annule = false;
    setErreur(null);

    openCamera(cameraChoisie)
      .then(async (stream) => {
        if (annule) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play().catch(() => undefined);
        }
        // Les libellés ne sont renseignés qu'une fois l'autorisation accordée :
        // la liste ne peut donc être remplie qu'après l'ouverture du flux.
        const dispo = await listCameras();
        if (!annule) {
          setCameras(dispo);
          if (!cameraChoisie) {
            const actif = stream.getVideoTracks()[0]?.getSettings().deviceId;
            if (actif) setCameraChoisie(actif);
          }
        }
      })
      .catch(() => setErreur(fr.scanner.cameraError));

    return () => {
      annule = true;
      arreterCamera();
    };
  }, [open, etape, videoPret, cameraChoisie, arreterCamera]);

  const changerCamera = useCallback((deviceId: string) => {
    rememberCamera(deviceId);
    setCameraChoisie(deviceId); // relance l'effet ci-dessus
  }, []);

  useEffect(() => {
    if (!open) {
      arreterCamera();
      setEtape('camera');
      setPhoto(null);
      setApercu(null);
      setCoins([]);
      setErreur(null);
    }
  }, [open, arreterCamera]);

  // Object URL : sans révocation, chaque photo laisse fuir plusieurs
  // mégaoctets tant que l'onglet reste ouvert.
  useEffect(() => {
    if (!apercu) return;
    return () => URL.revokeObjectURL(apercu);
  }, [apercu]);

  /* ---------- Capture ---------- */
  const capturer = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        arreterCamera();
        setPhoto(blob);
        setApercu(URL.createObjectURL(blob));
        setTaille({ w: canvas.width, h: canvas.height });
        setEtape('cadrage');

        detect.mutate(blob, {
          onSuccess: (res) => {
            setCoins(
              res.corners ?? [
                // Repli : un cadre en retrait de 10 %, que le déposant ajuste.
                { x: canvas.width * 0.1, y: canvas.height * 0.1 },
                { x: canvas.width * 0.9, y: canvas.height * 0.1 },
                { x: canvas.width * 0.9, y: canvas.height * 0.9 },
                { x: canvas.width * 0.1, y: canvas.height * 0.9 },
              ],
            );
          },
        });
      },
      'image/jpeg',
      1.0,
    );
  }, [arreterCamera, detect]);

  /* ---------- Manipulation du cadrage ---------- */
  const versImage = useCallback(
    (clientX: number, clientY: number) => {
      const rect = imageRef.current?.getBoundingClientRect();
      if (!rect) return null;
      // Les coins sont stockés en pixels de la photo d'origine, pas de
      // l'affichage : le serveur découpe dans l'image pleine résolution.
      return {
        x: ((clientX - rect.left) / rect.width) * taille.w,
        y: ((clientY - rect.top) / rect.height) * taille.h,
      };
    },
    [taille],
  );

  const borner = useCallback(
    (p: ScanCorner): ScanCorner => ({
      x: Math.max(0, Math.min(taille.w, p.x)),
      y: Math.max(0, Math.min(taille.h, p.y)),
    }),
    [taille],
  );

  const deplacer = useCallback(
    (clientX: number, clientY: number) => {
      if (!pointActif) return;
      const point = versImage(clientX, clientY);
      if (!point) return;

      if (pointActif.type === 'coin') {
        setCoins((prev) => prev.map((c, i) => (i === pointActif.index ? borner(point) : c)));
        return;
      }

      // Poignée de côté : les deux coins de l'arête suivent le même
      // déplacement, ce qui translate le côté sans le faire pivoter.
      const precedent = dernierPointeur.current;
      dernierPointeur.current = point;
      if (!precedent) return;

      const dx = point.x - precedent.x;
      const dy = point.y - precedent.y;
      const [a, b] = ARETES[pointActif.index];
      setCoins((prev) =>
        prev.map((c, i) => (i === a || i === b ? borner({ x: c.x + dx, y: c.y + dy }) : c)),
      );
    },
    [borner, pointActif, versImage],
  );

  const relacher = useCallback(() => {
    setPointActif(null);
    dernierPointeur.current = null;
  }, []);

  const cadrerToutePhoto = useCallback(() => {
    setCoins([
      { x: 0, y: 0 },
      { x: taille.w, y: 0 },
      { x: taille.w, y: taille.h },
      { x: 0, y: taille.h },
    ]);
  }, [taille]);

  const valider = useCallback(() => {
    if (!photo) return;
    apply.mutate(
      { photo, corners: coins.length === 4 ? coins : null },
      {
        onSuccess: (blob) => {
          const horodatage = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
          onScanned(new File([blob], `scan-${horodatage}.pdf`, { type: 'application/pdf' }));
          onClose();
        },
      },
    );
  }, [apply, coins, onClose, onScanned, photo]);

  const reprendre = useCallback(() => {
    setPhoto(null);
    setApercu(null);
    setCoins([]);
    setEtape('camera');
  }, []);

  /* ---------- Rendu ---------- */
  const pct = useCallback(
    (c: ScanCorner) => ({ left: `${(c.x / taille.w) * 100}%`, top: `${(c.y / taille.h) * 100}%` }),
    [taille],
  );

  const polygone = coins
    .map((c) => `${(c.x / taille.w) * 100},${(c.y / taille.h) * 100}`)
    .join(' ');

  const milieux = useMemo(
    () =>
      coins.length === 4
        ? ARETES.map(([a, b]) => ({
            x: (coins[a].x + coins[b].x) / 2,
            y: (coins[a].y + coins[b].y) / 2,
          }))
        : [],
    [coins],
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      {/* Fenêtre PLEIN ÉCRAN, ancrée en haut — et non centrée comme les autres.

          Le dialogue est en `position: fixed`, et sur iOS un élément fixe se
          cale sur le viewport **barre d'adresse masquée**, plus haut que la
          zone réellement visible. Centrer par `top: 50%` y place donc le milieu
          de la fenêtre trop bas, et le pied — le bouton de prise de vue —
          termine sous le bord de l'écran. Borner la hauteur n'y change rien :
          c'est la position qui est fausse, pas la taille. D'où `top: 0` et une
          hauteur en `svh`, la hauteur garantie visible.

          `overflow-hidden` et `p-0` : le contenu par défaut du dialogue ajoute
          son propre défilement, qui se superposait à celui de la page. Ici tout
          tient dans la fenêtre, sans rien à faire défiler. */}
      <DialogContent className="!left-0 !top-0 flex !max-h-none h-ecran-sur w-full max-w-none !translate-x-0 !translate-y-0 flex-col gap-0 overflow-hidden rounded-none border-0 p-0">
        {/* `pr-12` : le bouton de fermeture du dialogue est posé en absolu dans
            ce coin, et recouvrait le sélecteur d'objectif sur écran étroit. */}
        <div className="flex shrink-0 items-start justify-between gap-3 border-b py-3 pl-4 pr-12">
          <div>
            <DialogTitle className="text-base">{fr.scanner.documentTitle}</DialogTitle>
            <p className="text-xs text-muted-foreground">
              {etape === 'camera' ? fr.scanner.documentHelp : fr.scanner.documentAdjust}
            </p>
          </div>
          {/* Sélecteur d'objectif : n'apparaît que s'il y a un choix à faire.
              L'heuristique automatique écarte l'ultra grand-angle quand le
              libellé le trahit, mais sur Android ces libellés sont souvent
              génériques (« camera2 0, facing back ») : le dernier mot revient
              donc au déposant, et son choix est mémorisé. */}
          {etape === 'camera' && cameras.length > 1 && (
            <select
              aria-label={fr.scanner.chooseCamera}
              value={cameraChoisie ?? ''}
              onChange={(e) => changerCamera(e.target.value)}
              className="max-w-[45%] rounded-md border border-input bg-background px-2 py-1 text-xs"
            >
              {cameras.map((c) => (
                <option key={c.deviceId} value={c.deviceId}>
                  {c.label}
                  {c.ultraWide ? ' — grand-angle' : ''}
                </option>
              ))}
            </select>
          )}

          {etape === 'cadrage' && (
            <Button type="button" variant="ghost" size="sm" onClick={cadrerToutePhoto}>
              <Maximize className="h-4 w-4" />
              {fr.scanner.fullFrame}
            </Button>
          )}
        </div>

        <div className="min-h-0 flex-1 bg-neutral-900">
          {erreur ? (
            <div className="p-4">
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            </div>
          ) : etape === 'camera' ? (
            <video
              ref={attacherVideo}
              className="mx-auto max-h-full max-w-full object-contain"
              autoPlay
              playsInline
              muted
              aria-label={fr.scanner.documentTitle}
            />
          ) : (
            <div
              className="relative mx-auto flex h-full w-full touch-none select-none items-center justify-center"
              onPointerMove={(e) => deplacer(e.clientX, e.clientY)}
              onPointerUp={relacher}
              onPointerCancel={relacher}
              onPointerLeave={relacher}
            >
              {/* Une seule limite de hauteur sur l'aperçu : cumuler
                  `max-h-full` ferait dépendre la règle gagnante de l'ordre de
                  compilation du CSS, et elle ne bornerait rien de toute façon —
                  le parent immédiat a une hauteur automatique. */}
              <div className="relative">
                <img
                  ref={imageRef}
                  src={apercu ?? ''}
                  alt=""
                  className="max-h-apercu max-w-full object-contain"
                />

                {coins.length === 4 && (
                  <>
                    <svg
                      viewBox="0 0 100 100"
                      preserveAspectRatio="none"
                      className="pointer-events-none absolute inset-0 h-full w-full"
                    >
                      <polygon
                        points={polygone}
                        fill="rgba(37, 99, 235, 0.18)"
                        stroke="#2563eb"
                        strokeWidth={0.6}
                        vectorEffect="non-scaling-stroke"
                      />
                    </svg>

                    {/* Poignées de côté : translatent l'arête entière. */}
                    {milieux.map((m, i) => (
                      <button
                        key={`arete-${i}`}
                        type="button"
                        aria-label={`${fr.scanner.edge} ${i + 1}`}
                        onPointerDown={(e) => {
                          e.currentTarget.setPointerCapture(e.pointerId);
                          dernierPointeur.current = versImage(e.clientX, e.clientY);
                          setPointActif({ type: 'arete', index: i });
                        }}
                        className="absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-blue-600/80 shadow"
                        style={pct(m)}
                      />
                    ))}

                    {/* Poignées de coin, plus grandes : ce sont elles qui
                        portent la correction de perspective. */}
                    {coins.map((c, i) => (
                      <button
                        key={`coin-${i}`}
                        type="button"
                        aria-label={`${fr.scanner.corner} ${i + 1}`}
                        onPointerDown={(e) => {
                          e.currentTarget.setPointerCapture(e.pointerId);
                          setPointActif({ type: 'coin', index: i });
                        }}
                        className="absolute h-9 w-9 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-blue-600 shadow-lg ring-2 ring-blue-600/40"
                        style={pct(c)}
                      />
                    ))}
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* `pb-securise` : sur les iPhone à barre de navigation gestuelle, le
            pied tombait sous cette barre — visible, mais un appui sur deux
            partait à côté. `shrink-0` : ces boutons ne cèdent jamais leur place
            à l'aperçu, ce sont eux qui font sortir du scanner. */}
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t px-4 pt-3 pb-securise">
          <Button type="button" variant="outline" onClick={onClose}>
            {fr.common.cancel}
          </Button>

          {etape === 'camera' ? (
            <Button type="button" onClick={capturer} disabled={!!erreur}>
              <Camera className="h-4 w-4" />
              {fr.scanner.capture}
            </Button>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={reprendre}>
                <RotateCcw className="h-4 w-4" />
                {fr.scanner.retake}
              </Button>
              <Button type="button" onClick={valider} loading={apply.isPending || detect.isPending}>
                <Check className="h-4 w-4" />
                {fr.scanner.validate}
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
