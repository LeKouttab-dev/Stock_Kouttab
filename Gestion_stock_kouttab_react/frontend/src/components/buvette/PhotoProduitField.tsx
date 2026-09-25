import { useRef, useState } from 'react';
import { Camera, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';

interface PhotoProduitFieldProps {
  /** Photo déjà enregistrée, servie par l'API. */
  photoActuelle?: string | null;
  /** Emoji du produit : ce que la caisse affiche à défaut de photo. */
  emoji?: string | null;
  /** Remonte le fichier choisi ; le parent l'envoie avec le reste de la fiche. */
  onFichier: (fichier: File | null) => void;
  /** Absent à la création : il n'y a encore rien à retirer. */
  onRetirer?: () => void;
  occupe?: boolean;
}

/**
 * Choix de la photo d'un produit de la buvette.
 *
 * `accept="image/*"` sans `capture` : sur un téléphone, le système propose
 * alors l'appareil photo **et** la photothèque, alors que `capture` force la
 * prise de vue — or la photo du produit est souvent déjà dans le téléphone. Sur
 * un ordinateur, c'est l'explorateur de fichiers, sans différence de code.
 *
 * L'aperçu affiche le fichier choisi avant tout envoi : c'est la seule façon de
 * voir qu'on s'est trompé de photo avant qu'elle parte en caisse.
 */
export function PhotoProduitField({
  photoActuelle,
  emoji,
  onFichier,
  onRetirer,
  occupe = false,
}: PhotoProduitFieldProps) {
  const champ = useRef<HTMLInputElement>(null);
  const [apercu, setApercu] = useState<string | null>(null);

  const choisir = (choisi: File | null) => {
    onFichier(choisi);
    // `createObjectURL` plutôt qu'un `FileReader` : rien n'est lu en mémoire,
    // le navigateur pointe directement le fichier.
    setApercu((precedent) => {
      if (precedent) URL.revokeObjectURL(precedent);
      return choisi ? URL.createObjectURL(choisi) : null;
    });
  };

  const visuel = apercu ?? photoActuelle ?? null;

  return (
    <div className="space-y-1.5">
      <Label>Photo</Label>
      <div className="flex items-center gap-3">
        <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
          {visuel ? (
            <img src={visuel} alt="" className="h-full w-full object-contain" />
          ) : (
            <span className="text-3xl">{emoji || '📦'}</span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <input
            ref={champ}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => choisir(e.target.files?.[0] ?? null)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={occupe}
            onClick={() => champ.current?.click()}
          >
            <Camera className="h-4 w-4" />
            {visuel ? 'Changer la photo' : 'Importer une photo'}
          </Button>

          {(photoActuelle || apercu) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={occupe}
              onClick={() => {
                choisir(null);
                // Une photo seulement choisie n'a rien à retirer côté serveur.
                if (photoActuelle) onRetirer?.();
              }}
            >
              <Trash2 className="h-4 w-4" />
              Retirer
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Depuis le téléphone ou l&apos;ordinateur. L&apos;image est réduite automatiquement ; sans
        photo, la caisse affiche l&apos;emoji.
      </p>
    </div>
  );
}
