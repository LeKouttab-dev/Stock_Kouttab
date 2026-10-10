import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { fr } from '@/lib/i18n/fr';
import {
  PRESETS_PERIODE,
  bornesPreset,
  type PeriodeChoisie,
  type PresetPeriode,
} from '@/lib/periode';

interface Props {
  /** Préfixe des identifiants des champs de date (`<id>-du`, `<id>-au`). */
  id: string;
  valeur: PeriodeChoisie;
  onChange: (valeur: PeriodeChoisie) => void;
}

/**
 * Aujourd'hui · 7 derniers jours · Ce mois-ci · 3 derniers mois · Personnalisé.
 * « Personnalisé » affiche les deux champs de date, partis des dates en cours.
 */
export function PeriodePreset({ id, valeur, onChange }: Props) {
  const t = fr.periodes;
  const choisir = (preset: PresetPeriode) =>
    onChange({ preset, ...bornesPreset(preset, new Date(), valeur) });

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <p className="text-sm font-medium">{t.libelle}</p>
        <div className="flex flex-wrap gap-1" role="group" aria-label={t.libelle}>
          {PRESETS_PERIODE.map((p) => (
            <Button
              key={p}
              type="button"
              size="sm"
              variant={valeur.preset === p ? 'primary' : 'outline'}
              aria-pressed={valeur.preset === p}
              onClick={() => choisir(p)}
            >
              {t.presets[p]}
            </Button>
          ))}
        </div>
      </div>
      {valeur.preset === 'perso' && (
        <>
          <div className="space-y-1">
            <Label htmlFor={`${id}-du`}>{t.du}</Label>
            <Input
              id={`${id}-du`}
              type="date"
              value={valeur.debut}
              max={valeur.fin}
              onChange={(e) => e.target.value && onChange({ ...valeur, debut: e.target.value })}
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${id}-au`}>{t.au}</Label>
            <Input
              id={`${id}-au`}
              type="date"
              value={valeur.fin}
              min={valeur.debut}
              onChange={(e) => e.target.value && onChange({ ...valeur, fin: e.target.value })}
              className="w-40"
            />
          </div>
        </>
      )}
    </div>
  );
}
