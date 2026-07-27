import { useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { BarcodeFormat, DecodeHintType, type Result } from '@zxing/library';
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
import { fr } from '@/lib/i18n/fr';

export interface BarcodeScannerProps {
  open: boolean;
  onClose: () => void;
  onDetected: (barcode: string) => void;
  /** Formats acceptés. Défaut : EAN-13, EAN-8, Code-128, QR */
  formats?: BarcodeFormat[];
}

const DEFAULT_FORMATS: BarcodeFormat[] = [
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
  BarcodeFormat.CODE_128,
  BarcodeFormat.QR_CODE,
];

function isSecureContextOk(): boolean {
  if (typeof window === 'undefined') return true;
  if (window.location.protocol === 'https:') return true;
  if (window.location.hostname === 'localhost') return true;
  if (window.location.hostname === '127.0.0.1') return true;
  return false;
}

export function BarcodeScanner({
  open,
  onClose,
  onDetected,
  formats = DEFAULT_FORMATS,
}: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const detectedRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!open) return;

    detectedRef.current = false;
    setError(null);

    if (!isSecureContextOk()) {
      setError(fr.scanner.httpsRequired);
      return;
    }

    let cancelled = false;
    setStarting(true);

    const hints = new Map<DecodeHintType, unknown>();
    hints.set(DecodeHintType.POSSIBLE_FORMATS, formats);
    hints.set(DecodeHintType.TRY_HARDER, true);

    const codeReader = new BrowserMultiFormatReader(hints, {
      delayBetweenScanAttempts: 150,
    });

    const start = async () => {
      try {
        const videoEl = videoRef.current;
        if (!videoEl) return;

        // Préférer caméra arrière sur mobile.
        const constraints: MediaStreamConstraints = {
          audio: false,
          video: { facingMode: { ideal: 'environment' } },
        };

        const controls = await codeReader.decodeFromConstraints(
          constraints,
          videoEl,
          (result: Result | undefined, _err, ctrl) => {
            if (result && !detectedRef.current) {
              detectedRef.current = true;
              const text = result.getText();
              try {
                ctrl.stop();
              } catch {
                /* noop */
              }
              controlsRef.current = null;
              onDetected(text);
              onClose();
            }
          },
        );

        if (cancelled) {
          try {
            controls.stop();
          } catch {
            /* noop */
          }
          return;
        }
        controlsRef.current = controls;
      } catch (e) {
        if (cancelled) return;
        const err = e as Error;
        const name = err?.name ?? '';
        if (
          name === 'NotAllowedError' ||
          name === 'PermissionDeniedError' ||
          name === 'SecurityError'
        ) {
          setError(fr.scanner.permissionDenied);
        } else if (name === 'NotFoundError' || name === 'OverconstrainedError') {
          setError(
            'Aucune caméra disponible sur cet appareil ou contrainte non supportée.',
          );
        } else {
          setError(err?.message ?? 'Impossible de démarrer le scanner.');
        }
      } finally {
        if (!cancelled) setStarting(false);
      }
    };

    void start();

    return () => {
      cancelled = true;
      const controls = controlsRef.current;
      if (controls) {
        try {
          controls.stop();
        } catch {
          /* noop */
        }
        controlsRef.current = null;
      }
      // Sécurité : couper toutes les pistes du flux pour éteindre la lampe/caméra.
      const videoEl = videoRef.current;
      const stream = videoEl?.srcObject;
      if (stream && stream instanceof MediaStream) {
        stream.getTracks().forEach((track) => {
          try {
            track.stop();
          } catch {
            /* noop */
          }
        });
        if (videoEl) {
          videoEl.srcObject = null;
        }
      }
    };
  }, [open, formats, onDetected, onClose]);

  const handleOpenChange = (next: boolean) => {
    if (!next) onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
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
          <div className="relative w-full overflow-hidden rounded-md bg-black">
            <video
              ref={videoRef}
              className="h-auto w-full"
              autoPlay
              muted
              playsInline
            />
            {/* Cadre de visée */}
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-1/3 w-3/4 rounded-md border-2 border-white/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.25)]" />
            </div>
            {starting && (
              <div className="absolute inset-x-0 bottom-2 text-center text-xs text-white/80">
                Démarrage de la caméra…
              </div>
            )}
          </div>
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
