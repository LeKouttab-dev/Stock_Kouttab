import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { fr } from '@/lib/i18n/fr';
import { ONGLETS_CAISSE, type OngletCaisse } from '@/lib/schemas/buvette';

interface OngletCaisseSelectProps {
  value: OngletCaisse;
  onChange: (onglet: OngletCaisse) => void;
}

/**
 * Choix de l'onglet de la tablette de caisse.
 *
 * C'est le seul geste qui met un produit en vente sur la tablette : les
 * produits importés de HelloAsso arrivent sans onglet, et l'aide le dit pour
 * qu'un produit absent de la caisse ne se cherche pas ailleurs.
 */
export function OngletCaisseSelect({ value, onChange }: OngletCaisseSelectProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="onglet_caisse">{fr.buvette.ongletCaisse}</Label>
      <Select value={value} onValueChange={(v) => onChange(v as OngletCaisse)}>
        <SelectTrigger id="onglet_caisse">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ONGLETS_CAISSE.map((onglet) => (
            <SelectItem key={onglet} value={onglet}>
              {fr.buvette.onglets[onglet]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">{fr.buvette.ongletCaisseAide}</p>
    </div>
  );
}
