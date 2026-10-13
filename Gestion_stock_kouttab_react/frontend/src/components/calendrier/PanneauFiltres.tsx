import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import type { Agenda } from '@/types/api';

interface PanneauFiltresProps {
  agendas: Agenda[];
  chargement: boolean;
  recherche: string;
  masques: string[];
  salles: Record<string, string>;
  sallesMasquees: string[];
  parSalle: boolean;
  onRecherche: (terme: string) => void;
  onBasculerAgenda: (id: string) => void;
  onBasculerSalle: (cle: string) => void;
  onTousAgendas: (visibles: boolean) => void;
}

/**
 * Le filtre : quels agendas, quelles salles.
 *
 * On mémorise ce qui est **masqué**, pas ce qui est affiché — pour les salles
 * comme pour les agendas. Un agenda créé à la rentrée apparaît alors de
 * lui-même, là où une liste de cases cochées l'aurait laissé invisible
 * jusqu'à ce que quelqu'un pense à le rétablir.
 *
 * Le filtre par salle est ce qui rend la vue Semaine praticable : vingt-huit
 * colonnes sont illisibles, mais quelqu'un qui n'enseigne qu'à Maziri les
 * ramène à sept.
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
  onBasculerAgenda,
  onBasculerSalle,
  onTousAgendas,
}: PanneauFiltresProps) {
  const terme = recherche.trim().toLowerCase();
  const listeAgendas = terme
    ? agendas.filter((a) => a.nom.toLowerCase().includes(terme))
    : agendas;
  const visibles = agendas.length - masques.length;

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
          <Button type="button" variant="ghost" size="sm" onClick={() => onTousAgendas(true)}>
            Tout afficher
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => onTousAgendas(false)}>
            Tout masquer
          </Button>
        </div>

        {chargement ? (
          <Skeleton className="h-64" />
        ) : (
          <ul className="space-y-0.5">
            {listeAgendas.map((agenda) => (
              <li key={agenda.id}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-cream-100">
                  <Checkbox
                    checked={!masques.includes(agenda.id)}
                    onCheckedChange={() => onBasculerAgenda(agenda.id)}
                    style={
                      { '--couleur-agenda': agenda.couleur ?? '#3d4f3d' } as React.CSSProperties
                    }
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
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
