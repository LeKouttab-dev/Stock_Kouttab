import { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { BarcodeFormat, DecodeHintType } from '@zxing/library';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  ameliorerPourCodeBarres,
  creerDetecteurNatif,
  detecteurNatifDisponible,
} from '@/lib/barcode';
import {
  getRememberedCamera,
  listCameras,
  openCamera,
  rememberCamera,
  type CameraDisponible,
} from '@/lib/camera';
import { fr } from '@/lib/i18n/fr';

export interface BarcodeScannerProps {
  open: boolean;
  onClose: () => void;
  onDetected: (barcode: string) => void;
}

function isSecureContextOk(): boolean {
  if (typeof window === 'undefined') return true;
  if (window.location.protocol === 'https:') return true;
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

/**
 * Lecteur de codes-barres.
 *
 * Le décodage passe d'abord par `BarcodeDetector`, l'API native : elle s'appuie
 * sur le décodeur du système, tolère le flou et les angles, et lit en une
 * fraction de seconde ce que le décodage JavaScript manque. ZXing reste en
 * repli pour les navigateurs qui ne l'exposent pas.
 *
 * S'y ajoutent deux réglages décisifs, indépendants du moteur : la mise au
 * point continue — sans elle un code tenu à vingt centimètres reste flou — et
 * le choix de l'objectif, l'ultra grand-angle étant inexploitable de près.
 *
 * La saisie manuelle en dernier recours : un code abîmé ou une étiquette pliée
 * ne se lisent pas, et il ne faut pas que le déposant reste bloqué.
 */
export function BarcodeScanner({ open, onClose, onDetected }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const zxingRef = useRef<IScannerControls | null>(null);
  const boucleRef = useRef<number | null>(null);
  const detecteRef = useRef(false);

  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [moteur, setMoteur] = useState<'natif' | 'zxing' | null>(null);
  const [cameras, setCameras] = useState<CameraDisponible[]>([]);
  const [cameraChoisie, setCameraChoisie] = useState<string | null>(getRememberedCamera());
  const [saisieManuelle, setSaisieManuelle] = useState('');

  // Le contenu du dialogue est monté dans un portail : à l'ouverture, l'effet
  // s'exécute avant que le `<video>` existe. Sans cette ref callback, le
  // démarrage s'attachait à rien — écran noir sans message.
  const [videoPret, setVideoPret] = useState(false);
  const attacherVideo = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    setVideoPret(Boolean(el));
  }, []);

  const toutArreter = useCallback(() => {
    if (boucleRef.current !== null) {
      cancelAnimationFrame(boucleRef.current);
      boucleRef.current = null;
    }
    try {
      zxingRef.current?.stop();
    } catch {
      /* déjà arrêté */
    }
    zxingRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const signaler = useCallback(
    (code: string) => {
      if (detecteRef.current) return;
      detecteRef.current = true;
      toutArreter();
      onDetected(code.trim());
      onClose();
    },
    [onClose, onDetected, toutArreter],
  );

  useEffect(() => {
    if (!open || !videoPret) return;

    if (!isSecureContextOk()) {
      setError(fr.scanner.httpsRequired);
      return;
    }

    let annule = false;
    detecteRef.current = false;
    setError(null);
    setStarting(true);

    (async () => {
      let stream: MediaStream;
      try {
        stream = await openCamera(cameraChoisie);
      } catch {
        if (!annule) {
          setError(fr.scanner.permissionDenied);
          setStarting(false);
        }
        return;
      }
      if (annule) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      streamRef.current = stream;
      await ameliorerPourCodeBarres(stream);

      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play().catch(() => undefined);
      }

      const dispo = await listCameras();
      if (!annule) {
        setCameras(dispo);
        if (!cameraChoisie) {
          const actif = stream.getVideoTracks()[0]?.getSettings().deviceId;
          if (actif) setCameraChoisie(actif);
        }
      }

      const detecteur = await creerDetecteurNatif();

      if (detecteur && video) {
        setMoteur('natif');
        setStarting(false);
        const boucle = async () => {
          if (annule || detecteRef.current) return;
          try {
            // `videoWidth` à 0 = première image pas encore décodée.
            if (video.videoWidth) {
              const trouves = await detecteur.detect(video);
              if (trouves.length && trouves[0].rawValue) {
                signaler(trouves[0].rawValue);
                return;
              }
            }
          } catch {
            /* Une image illisible n'est pas une erreur : on réessaie. */
          }
          boucleRef.current = requestAnimationFrame(() => void boucle());
        };
        void boucle();
        return;
      }

      // --- Repli ZXing ---
      setMoteur('zxing');
      const hints = new Map<DecodeHintType, unknown>();
      hints.set(DecodeHintType.POSSIBLE_FORMATS, [
        BarcodeFormat.EAN_13,
        BarcodeFormat.EAN_8,
        BarcodeFormat.UPC_A,
        BarcodeFormat.UPC_E,
        BarcodeFormat.CODE_128,
        BarcodeFormat.CODE_39,
        BarcodeFormat.ITF,
        BarcodeFormat.QR_CODE,
      ]);
      hints.set(DecodeHintType.TRY_HARDER, true);

      try {
        const lecteur = new BrowserMultiFormatReader(hints, {
          delayBetweenScanAttempts: 100,
        });
        // On réutilise le flux déjà ouvert : redemander la caméra ici
        // rouvrirait l'objectif par défaut, en écartant le choix de l'objectif.
        zxingRef.current = await lecteur.decodeFromStream(
          stream,
          videoRef.current ?? undefined,
          (result) => {
            if (result) signaler(result.getText());
          },
        );
      } catch (e) {
        if (!annule) setError((e as Error)?.message ?? fr.scanner.cameraError);
      } finally {
        if (!annule) setStarting(false);
      }
    })();

    return () => {
      annule = true;
      toutArreter();
    };
  }, [open, videoPret, cameraChoisie, signaler, toutArreter]);

  useEffect(() => {
    if (!open) {
      toutArreter();
      setSaisieManuelle('');
      setError(null);
      setMoteur(null);
    }
  }, [open, toutArreter]);

  const changerCamera = useCallback((deviceId: string) => {
    rememberCamera(deviceId);
    setCameraChoisie(deviceId);
  }, []);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{fr.scanner.title}</DialogTitle>
          <DialogDescription>{fr.scanner.hint}</DialogDescription>
        </DialogHeader>

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          <>
            {cameras.length > 1 && (
              <select
                aria-label={fr.scanner.chooseCamera}
                value={cameraChoisie ?? ''}
                onChange={(e) => changerCamera(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
              >
                {cameras.map((c) => (
                  <option key={c.deviceId} value={c.deviceId}>
                    {c.label}
                    {c.ultraWide ? ' — grand-angle' : ''}
                  </option>
                ))}
              </select>
            )}

            <div className="relative w-full overflow-hidden rounded-md bg-black">
              <video ref={attacherVideo} className="h-auto w-full" autoPlay muted playsInline />
              {/* Cadre de visée : un code-barres se lit mieux cadré large et
                  tenu à plat, pas centré au millimètre. */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-1/3 w-4/5 rounded-md border-2 border-white/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.25)]" />
              </div>
              {starting && (
                <div className="absolute inset-x-0 bottom-2 text-center text-xs text-white/80">
                  {fr.scanner.starting}
                </div>
              )}
            </div>

            {moteur === 'zxing' && !detecteurNatifDisponible() && (
              <p className="text-[11px] text-muted-foreground">{fr.scanner.fallbackEngine}</p>
            )}

            <div className="space-y-1.5 border-t pt-3">
              <Label htmlFor="code-manuel" className="text-xs">
                {fr.scanner.manualEntry}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="code-manuel"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="3017620422003"
                  value={saisieManuelle}
                  onChange={(e) => setSaisieManuelle(e.target.value.replace(/\D/g, ''))}
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={saisieManuelle.length < 8}
                  onClick={() => signaler(saisieManuelle)}
                >
                  {fr.scanner.useCode}
                </Button>
              </div>
            </div>
          </>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {fr.scanner.cancel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
