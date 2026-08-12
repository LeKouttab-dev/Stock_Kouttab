import { useState } from 'react';
import { Edit2, Eye, EyeOff, Plus, Tags, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  useCreateExpenseCategory,
  useDeleteExpenseCategory,
  useExpenseCategories,
  useUpdateExpenseCategory,
} from '@/api/endpoints/referentials';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Référentiel des catégories de dépense.
 *
 * Ce que l'événement est au pôle événementiel, la catégorie l'est aux autres :
 * la deuxième composante du nom de la pièce envoyée à la comptabilité. La
 * renommer change les dépôts futurs, jamais les fichiers déjà transmis — le
 * libellé est figé au dépôt côté serveur.
 *
 * Jumelle de `PolesManagementSection`, dont elle reprend la disposition : les
 * deux référentiels se gèrent côte à côte, autant qu'ils se ressemblent.
 */
export function ExpenseCategoriesManagementSection() {
  // `include_inactive` : un administrateur doit voir ce qu'il a désactivé,
  // sinon une catégorie masquée devient impossible à réactiver.
  const { data: categories = [], isLoading } = useExpenseCategories(true);
  const create = useCreateExpenseCategory();
  const update = useUpdateExpenseCategory();
  const remove = useDeleteExpenseCategory();
  const toast = useToast();

  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleAdd = () => {
    if (!newName.trim()) return;
    create.mutate(
      { nom: newName.trim(), ordre: categories.length + 1 },
      {
        onSuccess: () => {
          toast.success(fr.categories.creee);
          setNewName('');
        },
      },
    );
  };

  const handleRename = (id: number, current: string) => {
    if (!editValue.trim() || editValue === current) {
      setEditing(null);
      return;
    }
    update.mutate({ id, nom: editValue.trim() }, { onSuccess: () => setEditing(null) });
  };

  const handleDelete = (id: number, nom: string) => {
    if (!confirm(`${fr.poles.confirmSuppression}\n\n${nom}`)) return;
    remove.mutate(id, { onSuccess: () => toast.success(fr.categories.supprimee) });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Tags className="h-4 w-4" aria-hidden />
          {fr.categories.title}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{fr.categories.subtitle}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder={fr.categories.nom}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button onClick={handleAdd} loading={create.isPending}>
            <Plus className="h-4 w-4" />
            {fr.categories.ajouter}
          </Button>
        </div>

        {isLoading ? (
          <Skeleton className="h-32" />
        ) : categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">{fr.categories.aucune}</p>
        ) : (
          <ul className="space-y-1">
            {categories.map((categorie) => (
              <li
                key={categorie.id}
                className="flex items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2"
              >
                {editing === categorie.id ? (
                  <div className="flex flex-1 gap-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      autoFocus
                    />
                    <Button size="sm" onClick={() => handleRename(categorie.id, categorie.nom)}>
                      OK
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditing(null)}>
                      Annuler
                    </Button>
                  </div>
                ) : (
                  <>
                    <span className="flex items-center gap-2 font-medium">
                      {categorie.nom}
                      {categorie.is_default && (
                        <Badge variant="secondary">{fr.poles.parDefaut}</Badge>
                      )}
                      {!categorie.is_active && <Badge variant="outline">{fr.poles.inactif}</Badge>}
                    </span>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => {
                          setEditing(categorie.id);
                          setEditValue(categorie.nom);
                        }}
                        aria-label={fr.poles.renommer}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() =>
                          update.mutate({ id: categorie.id, is_active: !categorie.is_active })
                        }
                        aria-label={categorie.is_active ? fr.poles.desactiver : fr.poles.activer}
                        title={categorie.is_active ? fr.poles.desactiver : fr.poles.activer}
                      >
                        {categorie.is_active ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                      {/* Les catégories de base ne sont pas supprimables : le
                          serveur refuse et invite à les désactiver. */}
                      {!categorie.is_default && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => handleDelete(categorie.id, categorie.nom)}
                          aria-label={fr.poles.supprimer}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
