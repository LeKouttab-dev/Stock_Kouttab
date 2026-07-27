import { useState } from 'react';
import { Edit2, Eye, EyeOff, Plus, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  useCreatePole,
  useDeletePole,
  usePoles,
  useUpdatePole,
} from '@/api/endpoints/referentials';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Référentiel des pôles de rattachement.
 *
 * Les pôles composent le nom des pièces envoyées à la comptabilité : les
 * renommer change les dépôts futurs, jamais les fichiers déjà transmis (le
 * libellé est figé au dépôt côté serveur).
 */
export function PolesManagementSection() {
  // `include_inactive` : un administrateur doit voir ce qu'il a désactivé,
  // sinon un pôle masqué devient impossible à réactiver.
  const { data: poles = [], isLoading } = usePoles(true);
  const create = useCreatePole();
  const update = useUpdatePole();
  const remove = useDeletePole();
  const toast = useToast();

  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleAdd = async () => {
    if (!newName.trim()) return;
    await create.mutateAsync({ nom: newName.trim(), ordre: poles.length + 1 });
    toast.success(fr.poles.ajoutSucces);
    setNewName('');
  };

  const handleRename = async (id: number, current: string) => {
    if (!editValue.trim() || editValue === current) {
      setEditing(null);
      return;
    }
    await update.mutateAsync({ id, nom: editValue.trim() });
    setEditing(null);
  };

  const handleDelete = async (id: number, nom: string) => {
    if (!confirm(`${fr.poles.confirmSuppression}\n\n${nom}`)) return;
    await remove.mutateAsync(id);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🏛️ {fr.poles.title}</CardTitle>
        <p className="text-xs text-muted-foreground">{fr.poles.subtitle}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder={fr.poles.nom}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button onClick={handleAdd} loading={create.isPending}>
            <Plus className="h-4 w-4" />
            {fr.poles.ajouter}
          </Button>
        </div>

        {isLoading ? (
          <Skeleton className="h-32" />
        ) : poles.length === 0 ? (
          <p className="text-sm text-muted-foreground">{fr.poles.aucun}</p>
        ) : (
          <ul className="space-y-1">
            {poles.map((pole) => (
              <li
                key={pole.id}
                className="flex items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2"
              >
                {editing === pole.id ? (
                  <div className="flex flex-1 gap-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      autoFocus
                    />
                    <Button size="sm" onClick={() => handleRename(pole.id, pole.nom)}>
                      OK
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditing(null)}>
                      Annuler
                    </Button>
                  </div>
                ) : (
                  <>
                    <span className="flex items-center gap-2 font-medium">
                      {pole.nom}
                      {pole.is_default && <Badge variant="secondary">{fr.poles.parDefaut}</Badge>}
                      {!pole.is_active && <Badge variant="outline">{fr.poles.inactif}</Badge>}
                    </span>
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => {
                          setEditing(pole.id);
                          setEditValue(pole.nom);
                        }}
                        aria-label={fr.poles.renommer}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() =>
                          update.mutateAsync({ id: pole.id, is_active: !pole.is_active })
                        }
                        aria-label={pole.is_active ? fr.poles.desactiver : fr.poles.activer}
                        title={pole.is_active ? fr.poles.desactiver : fr.poles.activer}
                      >
                        {pole.is_active ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                      {/* Les pôles de base ne sont pas supprimables : le serveur
                          refuse et invite à les désactiver. */}
                      {!pole.is_default && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => handleDelete(pole.id, pole.nom)}
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
