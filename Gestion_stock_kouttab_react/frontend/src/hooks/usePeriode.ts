import { useState } from 'react';
import { periodeInitiale, type PeriodeChoisie, type PresetPeriode } from '@/lib/periode';

/** État d'une période choisie (cf. `PeriodePreset`), initialisé sur un préréglage. */
export function usePeriode(defaut: PresetPeriode) {
  return useState<PeriodeChoisie>(() => periodeInitiale(defaut));
}
