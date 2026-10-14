import { useMemo, useState } from 'react';
import { DoorOpen, Save, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useAgendas,
  useDeduireLesSalles,
  useEnregistrerReglagesAgendas,
  useReglagesAgendas,
} from '@/api/endpoints/calendar';
import { useToast } from '@/hooks/useToast';

/** Ce qu'une ligne du tableau porte, avant enregistrement. */
interface Brouillon {
  salle: string;
  nom_court: string;
  categorie: string;
  sous_categorie: string;
}

const CHAMPS: (keyof Brouillon)[] = ['salle', 'nom_court', 'categorie', 'sous_categorie'];

/**
 * Ranger chaque agenda Google dans une salle.
 *
 * **Pourquoi cet écran existe.** Trois quarts des cours ne réservent aucune
 * salle dans Google : sans correspondance, l'emploi du temps entasserait tout
 * en Imam Maziri, la salle par défaut, et ne servirait à rien. On note donc ici la salle
 * *habituelle* de chaque agenda.
 *
 * **Ce n'est pas une réservation, et la grille le dit.** Un cours placé par
 * cette correspondance s'affiche avec une bordure en pointillés ; une salle
 * réellement bloquée dans Google l'emporte toujours sur ce qui est saisi ici.
 * Confondre les deux enverrait quelqu'un devant une porte occupée.
 *
 * Le nom court, la catégorie et la sous-catégorie sont facultatifs : vides,
 * c'est le calcul depuis le nom de l'agenda qui parle.
 */
export function CalendrierSallesSection() {
  const { data: agendas = [], isLoading: agendasEnCours } = useAgendas();
  const { data: reglages, isLoading: reglagesEnCours } = useReglagesAgendas();
  const enregistrer = useEnregistrerReglagesAgendas();
  const deduction = useDeduireLesSalles();
  const toast = useToast();

  // On ne garde que ce qui a été touché : le PUT n'envoie que les lignes
  // modifiées, et ce qui n'est pas envoyé n'est pas écrit.
  const [brouillons, setBrouillons] = useState<Record<string, Brouillon>>({});

  const salles = reglages?.salles ?? {};
  const poses = useMemo(
    () => Object.fromEntries((reglages?.reglages ?? []).map((r) => [r.agenda_id, r])),
    [reglages],
  );

  const valeur = (agendaId: string, champ: keyof Brouillon): string => {
    const brouillon = brouillons[agendaId];
    if (brouillon) return brouillon[champ];
    return poses[agendaId]?.[champ] ?? '';
  };

  const modifier = (agendaId: string, champ: keyof Brouillon, nouvelle: string) =>
    setBrouillons((actuels) => {
      const suite = Object.fromEntries(
        CHAMPS.map((c) => [c, c === champ ? nouvelle : valeur(agendaId, c)]),
      ) as unknown as Brouillon;
      return { ...actuels, [agendaId]: suite };
    });

  // Les catégories déjà connues, proposées à la saisie : retaper « Coran »
  // à la main finirait en « coran », « Coran » et « Coran  » côte à côte.
  const categoriesConnues = useMemo(
    () => [...new Set(agendas.map((a) => a.categorie).filter(Boolean))].sort(),
    [agendas],
  );
  const sousCategoriesConnues = useMemo(
    () => [...new Set(agendas.map((a) => a.sous_categorie).filter(Boolean) as string[])].sort(),
    [agendas],
  );

  const proposer = () => {
    deduction.refetch().then(({ data }) => {
      if (!data?.length) {
        toast.info("Aucune salle n'a pu être déduite : aucun cours ne réserve de salle.");
        return;
      }
      setBrouillons((actuels) => {
        const suite = { ...actuels };
        for (const p of data) {
          suite[p.agenda_id] = {
            salle: p.salle,
            nom_court: valeur(p.agenda_id, 'nom_court'),
            categorie: valeur(p.agenda_id, 'categorie'),
            sous_categorie: valeur(p.agenda_id, 'sous_categorie'),
          };
        }
        return suite;
      });
      // Volontairement non enregistré : la proposition remplit le formulaire,
      // une personne valide. Deviner sans contrôle ferait dire à la grille
      // qu'un cours se tient quelque part alors que rien ne l'atteste.
      toast.success(
        `${data.length} salle(s) proposée(s) d'après Google. Vérifiez, puis enregistrez.`,
      );
    });
  };

  const envoyer = () => {
    const lot = Object.fromEntries(
      Object.entries(brouillons).map(([agendaId, b]) => [
        agendaId,
        {
          salle: b.salle || null,
          nom_court: b.nom_court.trim() || null,
          categorie: b.categorie.trim() || null,
          sous_categorie: b.sous_categorie.trim() || null,
        },
      ]),
    );
    enregistrer.mutate(lot, {
      onSuccess: () => {
        toast.success('Salles enregistrées.');
        setBrouillons({});
      },
    });
  };

  const modifiees = Object.keys(brouillons).length;
  const sansSalle = agendas.filter((a) => !valeur(a.id, 'salle')).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DoorOpen className="h-5 w-5" />
          Salles de l&apos;emploi du temps
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-forest/70">
          La salle habituelle de chaque agenda, pour les cours qui n&apos;en réservent pas dans
          Google. Une salle réellement réservée l&apos;emporte toujours sur ce qui est saisi ici.
        </p>

        {sansSalle > 0 && agendas.length > 0 && (
          <Alert variant="warning">
            <AlertDescription>
              {sansSalle} agenda(s) sur {agendas.length} n&apos;ont pas de salle : leurs cours
              sont rangés par défaut en Imam Maziri.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={deduction.isFetching}
            onClick={proposer}
          >
            <Sparkles className="h-4 w-4" />
            Proposer d&apos;après Google
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={modifiees === 0}
            loading={enregistrer.isPending}
            onClick={envoyer}
          >
            <Save className="h-4 w-4" />
            Enregistrer {modifiees > 0 && `(${modifiees})`}
          </Button>
        </div>

        {agendasEnCours || reglagesEnCours ? (
          <Skeleton className="h-64" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-sand-200 text-left text-xs text-forest/60">
                  <th className="py-2 pr-3 font-medium">Agenda Google</th>
                  <th className="py-2 pr-3 font-medium">Salle habituelle</th>
                  <th className="py-2 pr-3 font-medium">Nom court (vide = automatique)</th>
                  <th className="py-2 pr-3 font-medium">Catégorie</th>
                  <th className="py-2 font-medium">Sous-catégorie</th>
                </tr>
              </thead>
              <tbody>
                {agendas.map((agenda) => (
                  <tr key={agenda.id} className="border-b border-sand-100 last:border-0">
                    <td className="py-1.5 pr-3">
                      <span className="block max-w-xs truncate" title={agenda.nom}>
                        {agenda.nom}
                      </span>
                      {agenda.enseignant && (
                        <span className="text-xs text-forest/50">{agenda.enseignant}</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3">
                      <select
                        aria-label={`Salle de ${agenda.nom}`}
                        className="h-8 w-40 rounded border border-sand-200 bg-white px-2 text-sm"
                        value={valeur(agenda.id, 'salle')}
                        onChange={(e) => modifier(agenda.id, 'salle', e.target.value)}
                      >
                        <option value="">— aucune —</option>
                        {Object.entries(salles).map(([cle, libelle]) => (
                          <option key={cle} value={cle}>
                            {libelle}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1.5">
                      <Input
                        aria-label={`Nom court de ${agenda.nom}`}
                        className="h-8 w-48 text-sm"
                        maxLength={22}
                        // Le calcul en cours, pour que vider le champ soit un
                        // geste lisible plutôt qu'un saut dans le vide.
                        placeholder={agenda.nom_court}
                        value={valeur(agenda.id, 'nom_court')}
                        onChange={(e) => modifier(agenda.id, 'nom_court', e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 pr-3">
                      <Input
                        aria-label={`Catégorie de ${agenda.nom}`}
                        className="h-8 w-40 text-sm"
                        list="calendrier-categories"
                        maxLength={64}
                        placeholder={agenda.categorie}
                        value={valeur(agenda.id, 'categorie')}
                        onChange={(e) => modifier(agenda.id, 'categorie', e.target.value)}
                      />
                    </td>
                    <td className="py-1.5">
                      <Input
                        aria-label={`Sous-catégorie de ${agenda.nom}`}
                        className="h-8 w-40 text-sm"
                        list="calendrier-sous-categories"
                        maxLength={64}
                        placeholder={agenda.sous_categorie ?? '—'}
                        value={valeur(agenda.id, 'sous_categorie')}
                        onChange={(e) => modifier(agenda.id, 'sous_categorie', e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <datalist id="calendrier-categories">
              {categoriesConnues.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
            <datalist id="calendrier-sous-categories">
              {sousCategoriesConnues.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
