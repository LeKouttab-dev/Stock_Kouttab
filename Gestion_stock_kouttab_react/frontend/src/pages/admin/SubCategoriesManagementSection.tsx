import { useState } from 'react';
import { Edit2, Plus, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import {
  useCategories,
  useCreateSubcategory,
  useDeleteSubcategory,
  useSubcategories,
  useUpdateSubcategory,
} from '@/api/endpoints/stock';
import { useToast } from '@/hooks/useToast';

export function SubCategoriesManagementSection() {
  const { data: categories = [] } = useCategories();
  const [selectedCat, setSelectedCat] = useState<string>('');
  const { data: subs = [], isLoading } = useSubcategories(selectedCat);
  const create = useCreateSubcategory();
  const update = useUpdateSubcategory();
  const remove = useDeleteSubcategory();
  const toast = useToast();

  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleAdd = async () => {
    if (!selectedCat || !newName.trim()) return;
    try {
      await create.mutateAsync({
        nom_categorie: selectedCat,
        nom_sous_categorie: newName.trim(),
      });
      toast.success('Sous-catégorie ajoutée');
      setNewName('');
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  const handleRename = async (id: number) => {
    if (!editValue.trim()) return;
    try {
      await update.mutateAsync({ id, data: { nom_sous_categorie: editValue.trim() } });
      toast.success('Sous-catégorie renommée');
      setEditing(null);
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Supprimer cette sous-catégorie ?')) return;
    try {
      await remove.mutateAsync(id);
      toast.success('Sous-catégorie supprimée');
    } catch {
      /* Erreur deja signalee par useApiMutation : un second toast
         ferait doublon a l'ecran. */
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🏷️ Sous-catégories</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label>Catégorie</Label>
          <Select value={selectedCat} onValueChange={setSelectedCat}>
            <SelectTrigger>
              <SelectValue placeholder="Choisir une catégorie…" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.nom} value={c.nom}>
                  {c.nom}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedCat && (
          <>
            <div className="flex gap-2">
              <Input
                placeholder="Nom de la sous-catégorie"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <Button onClick={handleAdd} loading={create.isPending}>
                <Plus className="h-4 w-4" />
                Ajouter
              </Button>
            </div>

            {isLoading ? (
              <Skeleton className="h-32" />
            ) : subs.length === 0 ? (
              <EmptyState title="Aucune sous-catégorie." />
            ) : (
              <ul className="space-y-1">
                {subs.map((sc) => (
                  <li
                    key={sc.id}
                    className="flex items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2"
                  >
                    {editing === sc.id ? (
                      <div className="flex flex-1 gap-2">
                        <Input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          autoFocus
                        />
                        <Button size="sm" onClick={() => handleRename(sc.id)}>
                          OK
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditing(null)}>
                          Annuler
                        </Button>
                      </div>
                    ) : (
                      <>
                        <span>{sc.nom_sous_categorie}</span>
                        <div className="flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => {
                              setEditing(sc.id);
                              setEditValue(sc.nom_sous_categorie);
                            }}
                            aria-label="Renommer"
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => handleDelete(sc.id)}
                            aria-label="Supprimer"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
