import { useState } from 'react';
import { Edit2, Plus, Tag, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useRenameCategory,
} from '@/api/endpoints/stock';
import { useToast } from '@/hooks/useToast';

export function CategoriesManagementSection() {
  const { data: categories = [], isLoading } = useCategories();
  const create = useCreateCategory();
  const rename = useRenameCategory();
  const remove = useDeleteCategory();
  const toast = useToast();

  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleAdd = () => {
    if (!newName.trim()) return;
    create.mutate(newName.trim(), {
      onSuccess: () => {
        toast.success('Catégorie ajoutée');
        setNewName('');
      },
    });
  };

  const handleRename = (oldName: string) => {
    if (!editValue.trim() || editValue === oldName) {
      setEditing(null);
      return;
    }
    rename.mutate(
      { oldName, newName: editValue.trim() },
      {
        onSuccess: () => {
          toast.success('Catégorie renommée');
          setEditing(null);
        },
      },
    );
  };

  const handleDelete = (name: string) => {
    if (!confirm(`Supprimer la catégorie "${name}" ?`)) return;
    remove.mutate(name, { onSuccess: () => toast.success('Catégorie supprimée') });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Tag className="h-4 w-4" aria-hidden />
          Catégories
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Nom de la catégorie"
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
        ) : (
          <ul className="space-y-1">
            {categories.map((cat) => (
              <li
                key={cat.nom}
                className="flex items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2"
              >
                {editing === cat.nom ? (
                  <div className="flex flex-1 gap-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      autoFocus
                    />
                    <Button size="sm" onClick={() => handleRename(cat.nom)}>
                      OK
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditing(null)}>
                      Annuler
                    </Button>
                  </div>
                ) : (
                  <>
                    <span className="font-medium">
                      {cat.nom}
                      {cat.is_default && (
                        <Label className="ml-2 text-xs text-muted-foreground">(défaut)</Label>
                      )}
                    </span>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => {
                          setEditing(cat.nom);
                          setEditValue(cat.nom);
                        }}
                        aria-label="Renommer"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => handleDelete(cat.nom)}
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
      </CardContent>
    </Card>
  );
}
