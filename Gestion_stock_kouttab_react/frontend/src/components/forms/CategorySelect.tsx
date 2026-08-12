import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useExpenseCategories } from '@/api/endpoints/referentials';
import { fr } from '@/lib/i18n/fr';

interface CategorySelectProps {
  /** Catégorie choisie, `null` tant que rien n'est sélectionné. */
  categoryId: number | null;
  onChange: (id: number | null) => void;
  disabled?: boolean;
}

/**
 * Catégorie d'une dépense sous un pôle sans événement.
 *
 * Pas de saisie libre ici, contrairement aux événements : la liste est courte,
 * administrable, et sert à regrouper les dépenses. Un champ libre la remplirait
 * de variantes (« courses », « Courses », « course ») qui rendraient tout
 * regroupement illusoire. Une catégorie manquante s'ajoute dans l'espace
 * d'administration.
 */
export function CategorySelect({ categoryId, onChange, disabled }: CategorySelectProps) {
  const { data: categories, isLoading, isError } = useExpenseCategories();

  return (
    <div className="space-y-2">
      <Select
        value={categoryId !== null ? String(categoryId) : ''}
        onValueChange={(next) => onChange(Number(next))}
        disabled={disabled || isLoading}
      >
        <SelectTrigger>
          <SelectValue placeholder={fr.categories.selectPlaceholder} />
        </SelectTrigger>
        <SelectContent>
          {(categories ?? []).map((categorie) => (
            <SelectItem key={categorie.id} value={String(categorie.id)}>
              {categorie.nom}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {isError && <p className="text-xs text-destructive">{fr.categories.unavailable}</p>}
    </div>
  );
}
