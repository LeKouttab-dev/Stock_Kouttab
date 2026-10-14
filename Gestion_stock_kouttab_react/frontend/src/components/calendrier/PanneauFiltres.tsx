import { useEffect, useMemo, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { Agenda } from '@/types/api';

/** Les nœuds dépliés. On mémorise le non-défaut : tout est replié d'abord. */
const CLE_DEPLIES = 'calendrier.filtre-deplies';

function lireDeplies(): Set<string> {
  try {
    const brut = localStorage.getItem(CLE_DEPLIES);
    const valeur: unknown = brut ? JSON.parse(brut) : [];
    return new Set(Array.isArray(valeur) ? valeur.filter((v) => typeof v === 'string') : []);
  } catch {
    return new Set();
  }
}

interface PanneauFiltresProps {
  agendas: Agenda[];
  chargement: boolean;
  recherche: string;
  masques: string[];
  salles: Record<string, string>;
  sallesMasquees: string[];
  parSalle: boolean;
  onRecherche: (terme: string) => void;
  /** Affiche (`true`) ou masque (`false`) tout un lot d'agendas d'un coup. */
  onReglerAgendas: (ids: string[], visibles: boolean) => void;
  onBasculerSalle: (cle: string) => void;
}

interface SousCategorie {
  nom: string | null;
  agendas: Agenda[];
}

interface Categorie {
  nom: string;
  rang: number;
  sous: SousCategorie[];
  agendas: Agenda[];
}

/** Cochée, décochée, ou partielle : ce que dit une case qui en regroupe d'autres. */
function etatDe(ids: string[], masques: Set<string>): boolean | 'indeterminate' {
  const caches = ids.filter((id) => masques.has(id)).length;
  if (caches === 0) return true;
  if (caches === ids.length) return false;
  return 'indeterminate';
}

function sansAccents(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * Le filtre : quelles salles, quels agendas.
 *
 * **Un arbre replié**, et non quarante-cinq cases à plat : par matière
 * (« Coran »), puis par public (« Coran enfants »), puis les agendas. La place
 * de chaque agenda est calculée par le serveur depuis son nom, et corrigeable
 * dans *Réglages des agendas*. Une case par nœud coche ou décoche tout ce
 * qu'elle contient, et dit « partiel » quand une partie seulement l'est.
 *
 * On mémorise ce qui est **masqué**, pas ce qui est affiché : un agenda créé à
 * la rentrée apparaît alors de lui-même, dans sa catégorie.
 */
export function PanneauFiltres({
  agendas,
  chargement,
  recherche,
  masques,
  salles,
  sallesMasquees,
  parSalle,
  onRecherche,
  onReglerAgendas,
  onBasculerSalle,
}: PanneauFiltresProps) {
  const [deplies, setDeplies] = useState<Set<string>>(lireDeplies);

  useEffect(() => {
    try {
      localStorage.setItem(CLE_DEPLIES, JSON.stringify([...deplies]));
    } catch {
      // Navigation privée, stockage plein : le filtre fonctionne quand même.
    }
  }, [deplies]);

  const masquesSet = useMemo(() => new Set(masques), [masques]);
  const terme = sansAccents(recherche.trim());
  const enRecherche = terme.length > 0;

  const arbre = useMemo(() => {
    const retenus = enRecherche
      ? agendas.filter((a) => sansAccents(`${a.nom} ${a.nom_court}`).includes(terme))
      : agendas;
    const parCategorie = new Map<string, Categorie>();
    for (const agenda of retenus) {
      const nom = agenda.categorie || 'Autres';
      const categorie = parCategorie.get(nom) ?? {
        nom,
        rang: agenda.categorie_rang ?? 0,
        sous: [],
        agendas: [],
      };
      categorie.agendas.push(agenda);
      const cle = agenda.sous_categorie ?? null;
      let sous = categorie.sous.find((s) => s.nom === cle);
      if (!sous) {
        sous = { nom: cle, agendas: [] };
        categorie.sous.push(sous);
      }
      sous.agendas.push(agenda);
      parCategorie.set(nom, categorie);
    }
    const parNom = (a: Agenda, b: Agenda) =>
      (a.nom_court || a.nom).localeCompare(b.nom_court || b.nom, 'fr');
    return [...parCategorie.values()]
      .sort((a, b) => a.rang - b.rang || a.nom.localeCompare(b.nom, 'fr'))
      .map((categorie) => ({
        ...categorie,
        // Les agendas sans sous-catégorie d'abord, puis les branches nommées.
        sous: categorie.sous
          .map((s) => ({ ...s, agendas: [...s.agendas].sort(parNom) }))
          .sort((a, b) =>
            a.nom === null ? -1 : b.nom === null ? 1 : a.nom.localeCompare(b.nom, 'fr'),
          ),
      }));
  }, [agendas, enRecherche, terme]);

  // Pendant une recherche, tout ce qui contient un résultat s'ouvre : chercher
  // « soundousse » et devoir déplier trois niveaux pour le voir n'aurait pas
  // de sens.
  const estDeplie = (cle: string) => enRecherche || deplies.has(cle);
  const basculer = (cle: string) =>
    setDeplies((actuels) => {
      const suite = new Set(actuels);
      if (suite.has(cle)) suite.delete(cle);
      else suite.add(cle);
      return suite;
    });

  const visibles = agendas.filter((a) => !masquesSet.has(a.id)).length;

  const ligneAgenda = (agenda: Agenda) => (
    <li key={agenda.id}>
      <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-cream-100">
        <Checkbox
          checked={!masquesSet.has(agenda.id)}
          onCheckedChange={() => onReglerAgendas([agenda.id], masquesSet.has(agenda.id))}
        />
        <span
          aria-hidden
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: agenda.couleur ?? '#3d4f3d' }}
        />
        <span className="truncate text-xs" title={agenda.nom}>
          {agenda.nom_court || agenda.nom}
        </span>
        {agenda.restreint && (
          <Badge variant="outline" className="shrink-0 text-[10px]">
            Réservé
          </Badge>
        )}
      </label>
    </li>
  );

  const noeud = (
    cle: string,
    libelle: string,
    ids: string[],
    enfants: React.ReactNode,
    niveau: 0 | 1,
  ) => {
    const ouvert = estDeplie(cle);
    const etat = etatDe(ids, masquesSet);
    const nbVisibles = ids.filter((id) => !masquesSet.has(id)).length;
    return (
      <li key={cle}>
        <div
          className={cn(
            'flex items-center gap-1 rounded py-0.5 pr-1 hover:bg-cream-100',
            niveau === 0 ? 'font-semibold' : 'pl-3',
          )}
        >
          <button
            type="button"
            onClick={() => basculer(cle)}
            aria-expanded={ouvert}
            aria-label={`${ouvert ? 'Replier' : 'Déplier'} ${libelle}`}
            className="rounded p-0.5 text-forest/60 hover:text-forest"
          >
            <ChevronRight
              className={cn('h-3.5 w-3.5 transition-transform', ouvert && 'rotate-90')}
            />
          </button>
          <Checkbox
            checked={etat}
            aria-label={`Afficher ${libelle}`}
            // Une case partielle se complète : cliquer affiche tout. Sinon
            // elle bascule.
            onCheckedChange={() => onReglerAgendas(ids, etat !== true)}
          />
          <button
            type="button"
            onClick={() => basculer(cle)}
            className="min-w-0 flex-1 truncate text-left text-xs text-forest"
          >
            {libelle}
          </button>
          <span className="shrink-0 text-[10px] tabular-nums text-forest/50">
            {nbVisibles}/{ids.length}
          </span>
        </div>
        {ouvert && <ul className={cn('space-y-0.5', niveau === 0 ? 'pl-4' : 'pl-7')}>{enfants}</ul>}
      </li>
    );
  };

  return (
    <div
      id="panneau-filtres"
      className="flex w-64 shrink-0 flex-col gap-3 overflow-y-auto border-r border-sand-200 bg-cream-50 p-3 scrollbar-thin"
    >
      {parSalle && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-forest/60">Salles</p>
          {Object.entries(salles).map(([cle, libelle]) => (
            <label
              key={cle}
              className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-cream-100"
            >
              <Checkbox
                checked={!sallesMasquees.includes(cle)}
                onCheckedChange={() => onBasculerSalle(cle)}
              />
              <span className="truncate">{libelle}</span>
            </label>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-forest/60">Agendas</p>
          <span className="text-xs text-forest/50">
            {visibles}/{agendas.length}
          </span>
        </div>

        <Input
          className="h-8 text-sm"
          placeholder="Filtrer les agendas…"
          value={recherche}
          onChange={(e) => onRecherche(e.target.value)}
        />

        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onReglerAgendas(agendas.map((a) => a.id), true)}
          >
            Tout afficher
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onReglerAgendas(agendas.map((a) => a.id), false)}
          >
            Tout masquer
          </Button>
        </div>

        {chargement ? (
          <Skeleton className="h-64" />
        ) : (
          <ul className="space-y-0.5" aria-label="Agendas par catégorie">
            {arbre.map((categorie) =>
              noeud(
                categorie.nom,
                categorie.nom,
                categorie.agendas.map((a) => a.id),
                categorie.sous.map((sous) =>
                  sous.nom === null
                    ? sous.agendas.map(ligneAgenda)
                    : noeud(
                        `${categorie.nom}::${sous.nom}`,
                        sous.nom,
                        sous.agendas.map((a) => a.id),
                        sous.agendas.map(ligneAgenda),
                        1,
                      ),
                ),
                0,
              ),
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
