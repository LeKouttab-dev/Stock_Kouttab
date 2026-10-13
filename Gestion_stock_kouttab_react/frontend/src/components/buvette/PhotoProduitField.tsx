import { useRef, useState } from 'react';
import { Camera, Images, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { BuvetteProduct } from '@/types/api';

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
  /** Produits dont on peut reprendre la photo (sans eux, pas de bouton « Reprendre »). */
  sources?: BuvetteProduct[];
  /** Remonte le produit dont la photo est reprise ; le parent l'applique avec la fiche. */
  onSource?: (source: BuvetteProduct | null) => void;
}

/** Sans accents ni casse : « peche » trouve « PÊCHE ». */
function comparable(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
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
  sources,
  onSource,
}: PhotoProduitFieldProps) {
  const champ = useRef<HTMLInputElement>(null);
  const [apercu, setApercu] = useState<string | null>(null);
  const [galerieOuverte, setGalerieOuverte] = useState(false);
  const [recherche, setRecherche] = useState('');
  const [source, setSource] = useState<BuvetteProduct | null>(null);

  // Une même image n'est proposée qu'une fois (un produit et ses déclinaisons).
  const avecPhoto = (sources ?? []).filter(
    (p, i, liste) => p.image_url && liste.findIndex((q) => q.image_url === p.image_url) === i,
  );
  const proposes = avecPhoto.filter((p) =>
    comparable(p.name).includes(comparable(recherche.trim())),
  );

  const reprendre = (choisie: BuvetteProduct | null) => {
    setSource(choisie);
    onSource?.(choisie);
    if (choisie) {
      // Un fichier et une photo reprise s'excluent : le dernier choix gagne.
      onFichier(null);
      setApercu((precedent) => {
        if (precedent) URL.revokeObjectURL(precedent);
        return null;
      });
      setGalerieOuverte(false);
    }
  };

  const choisir = (choisi: File | null) => {
    if (choisi) {
      setSource(null);
      onSource?.(null);
    }
    onFichier(choisi);
    // `createObjectURL` plutôt qu'un `FileReader` : rien n'est lu en mémoire,
    // le navigateur pointe directement le fichier.
    setApercu((precedent) => {
      if (precedent) URL.revokeObjectURL(precedent);
      return choisi ? URL.createObjectURL(choisi) : null;
    });
  };

  const visuel = apercu ?? source?.image_url ?? photoActuelle ?? null;

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

          {onSource && avecPhoto.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={occupe}
              aria-expanded={galerieOuverte}
              onClick={() => setGalerieOuverte((v) => !v)}
            >
              <Images className="h-4 w-4" />
              Reprendre la photo d&apos;un produit
            </Button>
          )}

          {(photoActuelle || apercu || source) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={occupe}
              onClick={() => {
                reprendre(null);
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
      {galerieOuverte && (
        <div className="space-y-2 rounded-md border border-border p-2">
          <Input
            placeholder="Rechercher un produit"
            aria-label="Rechercher un produit"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
          <ul className="grid max-h-60 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4">
            {proposes.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="flex w-full flex-col items-center gap-1 rounded-md border border-border p-1 text-xs hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => reprendre(p)}
                >
                  <img src={p.image_url ?? ''} alt="" className="h-14 w-14 object-contain" />
                  <span className="line-clamp-2 text-center">{p.name}</span>
                </button>
              </li>
            ))}
          </ul>
          {proposes.length === 0 && (
            <p className="text-xs text-muted-foreground">Aucun produit trouvé.</p>
          )}
        </div>
      )}
      {source && (
        <p className="text-xs text-muted-foreground">
          Photo reprise de « {source.name} », enregistrée avec la fiche.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Depuis le téléphone ou l&apos;ordinateur. L&apos;image est réduite automatiquement ; sans
        photo, la caisse affiche l&apos;emoji.
      </p>
    </div>
  );
}
