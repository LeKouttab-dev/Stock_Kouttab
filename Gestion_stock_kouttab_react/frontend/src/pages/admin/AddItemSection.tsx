import { useForm } from 'react-hook-form';
import { Plus } from 'lucide-react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCategories, useCreateStockItem, useSubcategories } from '@/api/endpoints/stock';
import { stockItemSchema, type StockItemFormValues } from '@/lib/schemas/stock';
import { EMOJI_OPTIONS } from '@/lib/constants';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

export function AddItemSection() {
  const { data: categories = [] } = useCategories();
  const create = useCreateStockItem();
  const toast = useToast();

  const form = useForm<StockItemFormValues>({
    resolver: zodResolver(stockItemSchema),
    defaultValues: {
      nom: '',
      categorie: '',
      sous_categorie: null,
      quantite: 0,
      seuil_alerte: 5,
      emoji: '📦',
    },
  });

  const selectedCategory = form.watch('categorie');
  const { data: subs = [] } = useSubcategories(selectedCategory);

  const onSubmit = (values: StockItemFormValues) => {
    create.mutate(values, {
      onSuccess: () => {
        toast.success(`L'article "${values.nom}" ${fr.admin.articleAjoute}`);
        form.reset({
          nom: '',
          categorie: values.categorie,
          sous_categorie: null,
          quantite: 0,
          seuil_alerte: 5,
          emoji: '📦',
        });
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Plus className="h-4 w-4" aria-hidden />
          {fr.admin.ajouterArticle}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5 md:col-span-2">
            <Label required>{fr.admin.nomArticle}</Label>
            <Input hasError={Boolean(form.formState.errors.nom)} {...form.register('nom')} />
            {form.formState.errors.nom && (
              <p className="text-xs text-destructive">{form.formState.errors.nom.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label required>{fr.admin.categorie}</Label>
            <Select
              value={form.watch('categorie')}
              onValueChange={(v) => {
                form.setValue('categorie', v, { shouldValidate: true });
                form.setValue('sous_categorie', null);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Choisir…" />
              </SelectTrigger>
              <SelectContent>
                {categories.map((c) => (
                  <SelectItem key={c.nom} value={c.nom}>
                    {c.nom}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.formState.errors.categorie && (
              <p className="text-xs text-destructive">{form.formState.errors.categorie.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>{fr.admin.sousCategorie}</Label>
            <Select
              value={form.watch('sous_categorie') ?? ''}
              onValueChange={(v) => form.setValue('sous_categorie', v || null)}
              disabled={subs.length === 0}
            >
              <SelectTrigger>
                <SelectValue placeholder={subs.length === 0 ? '— aucune —' : 'Choisir…'} />
              </SelectTrigger>
              <SelectContent>
                {subs.map((s) => (
                  <SelectItem key={s.id} value={s.nom_sous_categorie}>
                    {s.nom_sous_categorie}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label required>{fr.admin.quantiteInitiale}</Label>
            <Input type="number" min={0} {...form.register('quantite', { valueAsNumber: true })} />
          </div>

          <div className="space-y-1.5">
            <Label required>{fr.stock.seuilAlerte}</Label>
            <Input
              type="number"
              min={0}
              {...form.register('seuil_alerte', { valueAsNumber: true })}
            />
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <Label required>{fr.admin.emoji}</Label>
            <div className="flex flex-wrap gap-2">
              {EMOJI_OPTIONS.map((e) => {
                const active = form.watch('emoji') === e;
                return (
                  <button
                    key={e}
                    type="button"
                    onClick={() => form.setValue('emoji', e, { shouldValidate: true })}
                    className={`h-9 w-9 rounded-md border text-lg transition-colors ${
                      active ? 'border-primary bg-primary/10' : 'hover:bg-muted'
                    }`}
                    aria-label={`Emoji ${e}`}
                  >
                    {e}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="md:col-span-2">
            <Button type="submit" loading={create.isPending}>
              {fr.admin.ajouter}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
