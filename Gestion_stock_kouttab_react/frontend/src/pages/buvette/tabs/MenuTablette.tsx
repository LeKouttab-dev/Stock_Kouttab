import { useEffect, useMemo, useState } from 'react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ArrowDown, ArrowUp, GripVertical, ListOrdered } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import {
  useBuvetteProducts,
  useEnregistrerOrdreCaisse,
  useOrdreParVentes,
  useProposerOrdreParVentes,
  useUpdateBuvetteProduct,
} from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import {
  COULEURS_ETIQUETTE,
  ETIQUETTES_FIXES,
  ETIQUETTE_TEXTE_MAX,
  ONGLETS_MENU,
  PERIODES_TRI_VENTES,
  appliquerOrdrePropose,
  deplacer,
  longueurEtiquette,
  nettoyerEtiquette,
  produitsDuMenu,
} from '@/lib/buvette';
import { fr } from '@/lib/i18n/fr';
import { cn } from '@/lib/utils';
import type { BuvetteProduct, CaisseCategory, EtiquetteType } from '@/types/api';

const JOURS_VENTES = 30;

/** Pastille telle que la tablette l'affiche (mêmes couleurs). */
export function PastilleEtiquette({ type, texte }: { type: EtiquetteType; texte: string }) {
  return (
    <span
      data-testid="pastille-etiquette"
      data-type={type}
      className={cn(
        'inline-flex max-w-full items-center truncate rounded-full px-2 py-0.5 text-xs font-semibold',
        COULEURS_ETIQUETTE[type],
      )}
    >
      {texte}
    </span>
  );
}

function libelleEtiquette(type: EtiquetteType, texte: string | null | undefined): string {
  if (type === 'libre') return nettoyerEtiquette(texte ?? '');
  return fr.buvette.tablette.menu.libelles[type];
}

function Vignette({ produit }: { produit: BuvetteProduct }) {
  return produit.image_url ? (
    <img
      src={produit.image_url}
      alt=""
      className="h-10 w-10 shrink-0 rounded-md object-cover"
      loading="lazy"
    />
  ) : (
    <span
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted/40 text-2xl"
      aria-hidden
    >
      {produit.emoji || '📦'}
    </span>
  );
}

/** Choix de l'étiquette d'un produit : aucune, un type fixe, ou un texte libre. */
function EtiquetteProduit({ produit }: { produit: BuvetteProduct }) {
  const t = fr.buvette.tablette.menu;
  const toast = useToast();
  const maj = useUpdateBuvetteProduct();
  const [choix, setChoix] = useState<EtiquetteType | ''>(produit.etiquette_type ?? '');
  const [texte, setTexte] = useState(produit.etiquette_texte ?? '');
  const [erreur, setErreur] = useState<string | null>(null);

  // Relecture du serveur (après un enregistrement, ou depuis un autre poste).
  useEffect(() => {
    setChoix(produit.etiquette_type ?? '');
    setTexte(produit.etiquette_texte ?? '');
  }, [produit.etiquette_type, produit.etiquette_texte]);

  const enregistrer = (type: EtiquetteType | null, texteLibre?: string) =>
    maj.mutate(
      {
        id: produit.id,
        data:
          type === 'libre'
            ? { etiquette_type: 'libre', etiquette_texte: texteLibre }
            : { etiquette_type: type },
      },
      { onSuccess: () => toast.success(t.etiquetteEnregistree) },
    );

  const changerChoix = (valeur: string) => {
    const type = (valeur || '') as EtiquetteType | '';
    setChoix(type);
    setErreur(null);
    // Le texte libre s'enregistre au clic sur « Valider », une fois saisi.
    if (type !== 'libre') enregistrer(type || null);
  };

  const validerTexte = () => {
    const propre = nettoyerEtiquette(texte);
    if (!propre) {
      setErreur(t.texteVide);
      return;
    }
    if (longueurEtiquette(propre) > ETIQUETTE_TEXTE_MAX) {
      setErreur(t.texteTropLong(ETIQUETTE_TEXTE_MAX));
      return;
    }
    enregistrer('libre', propre);
  };

  const libreModifie =
    choix === 'libre' &&
    (produit.etiquette_type !== 'libre' ||
      nettoyerEtiquette(texte) !== (produit.etiquette_texte ?? ''));
  const apercu = choix ? libelleEtiquette(choix, texte) : '';

  return (
    <div className="flex min-w-0 flex-col gap-1.5 sm:items-end">
      <div className="flex flex-wrap items-center gap-2">
        {choix && apercu && (
          <span title={t.apercu}>
            <PastilleEtiquette type={choix} texte={apercu} />
          </span>
        )}
        <select
          aria-label={t.etiquette(produit.name)}
          value={choix}
          disabled={maj.isPending}
          onChange={(e) => changerChoix(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
        >
          <option value="">{t.aucuneEtiquette}</option>
          {ETIQUETTES_FIXES.map((type) => (
            <option key={type} value={type}>
              {t.libelles[type]}
            </option>
          ))}
          <option value="libre">{t.texteLibre}</option>
        </select>
      </div>
      {choix === 'libre' && (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Input
              aria-label={t.texteLibreLabel(produit.name)}
              placeholder={t.texteLibrePlaceholder}
              className="h-9 w-44"
              value={texte}
              hasError={erreur !== null}
              onChange={(e) => {
                // Borné à 20 caractères (un emoji compte pour un), comme le serveur.
                const caracteres = Array.from(e.target.value);
                setTexte(caracteres.slice(0, ETIQUETTE_TEXTE_MAX).join(''));
                setErreur(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  validerTexte();
                }
              }}
            />
            <span className="w-10 text-xs text-muted-foreground" aria-hidden>
              {t.compteur(longueurEtiquette(texte), ETIQUETTE_TEXTE_MAX)}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={validerTexte}
              disabled={!libreModifie}
              loading={maj.isPending}
            >
              {t.enregistrerTexte}
            </Button>
          </div>
          {erreur && <p className="text-xs text-destructive">{erreur}</p>}
        </div>
      )}
    </div>
  );
}

interface LigneMenuProps {
  produit: BuvetteProduct;
  rang: number;
  total: number;
  ventes: number | undefined;
  occupe: boolean;
  onDeplacer: (de: number, vers: number) => void;
}

function LigneMenu({ produit, rang, total, ventes, occupe, onDeplacer }: LigneMenuProps) {
  const t = fr.buvette.tablette.menu;
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: produit.id, disabled: occupe });

  return (
    <li
      ref={setNodeRef}
      data-testid="ligne-menu"
      data-produit={produit.id}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'flex flex-col gap-3 rounded-md border border-border bg-background p-2 sm:flex-row sm:items-center',
        isDragging && 'relative z-10 shadow-lg',
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <button
          type="button"
          ref={setActivatorNodeRef}
          aria-label={t.deplacer(produit.name)}
          className="flex h-10 w-8 shrink-0 cursor-grab touch-none items-center justify-center rounded text-muted-foreground hover:bg-muted active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-5 w-5" aria-hidden />
        </button>
        <span className="w-6 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
          {rang + 1}
        </span>
        <Vignette produit={produit} />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{produit.name}</p>
          <p className="text-xs text-muted-foreground" data-testid="ventes-produit">
            {ventes === undefined ? ' ' : t.ventes(ventes, JOURS_VENTES)}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 sm:justify-end">
        <EtiquetteProduit produit={produit} />
        <div className="flex shrink-0 gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            aria-label={t.monter(produit.name)}
            disabled={occupe || rang === 0}
            onClick={() => onDeplacer(rang, rang - 1)}
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            aria-label={t.descendre(produit.name)}
            disabled={occupe || rang === total - 1}
            onClick={() => onDeplacer(rang, rang + 1)}
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </li>
  );
}

function OngletMenu({
  categorie,
  produits,
}: {
  categorie: CaisseCategory;
  produits: BuvetteProduct[];
}) {
  const t = fr.buvette.tablette.menu;
  const toast = useToast();
  const ventes = useOrdreParVentes(categorie, JOURS_VENTES);
  const enregistrerOrdre = useEnregistrerOrdreCaisse();
  const proposer = useProposerOrdreParVentes();
  const [periode, setPeriode] = useState<number>(JOURS_VENTES);
  const [confirmation, setConfirmation] = useState(false);

  const duServeur = useMemo(() => produitsDuMenu(produits, categorie), [produits, categorie]);
  const idsServeur = useMemo(() => duServeur.map((p) => p.id), [duServeur]);
  // Ordre affiché : celui du serveur, remplacé aussitôt par le nouvel ordre à
  // chaque déplacement (l'écran n'attend pas la réponse pour bouger).
  const [ordre, setOrdre] = useState<number[]>(idsServeur);
  useEffect(() => setOrdre(idsServeur), [idsServeur]);

  const parId = useMemo(() => new Map(duServeur.map((p) => [p.id, p])), [duServeur]);
  const lignes = ordre
    .map((id) => parId.get(id))
    .filter((p): p is BuvetteProduct => p !== undefined);
  const ventesParId = useMemo(
    () => new Map((ventes.data?.produits ?? []).map((p) => [p.product_id, p.quantite_vendue ?? 0])),
    [ventes.data],
  );
  const occupe = enregistrerOrdre.isPending || proposer.isPending;

  const enregistrer = (ids: number[], succes?: string) => {
    setOrdre(ids);
    enregistrerOrdre.mutate(
      { categorie, product_ids: ids },
      {
        onSuccess: () => toast.success(succes ?? t.ordreEnregistre),
        // Refusé : on revient à l'ordre enregistré (le toast d'erreur est déjà affiché).
        onError: () => setOrdre(idsServeur),
      },
    );
  };

  const deplacerLigne = (de: number, vers: number) => {
    if (de === vers || vers < 0 || vers >= lignes.length) return;
    enregistrer(
      deplacer(
        lignes.map((p) => p.id),
        de,
        vers,
      ),
    );
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const finGlisser = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const ids = lignes.map((p) => p.id);
    deplacerLigne(ids.indexOf(Number(active.id)), ids.indexOf(Number(over.id)));
  };

  const trier = () =>
    proposer.mutate(
      { categorie, jours: periode },
      {
        onSuccess: (propose) => {
          setConfirmation(false);
          enregistrer(
            appliquerOrdrePropose(
              lignes.map((p) => p.id),
              propose.produits.map((p) => p.product_id),
            ),
            t.trie,
          );
        },
      },
    );

  if (lignes.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">{t.vide}</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={t.periode}
          value={periode}
          onChange={(e) => setPeriode(Number(e.target.value))}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
        >
          {PERIODES_TRI_VENTES.map((jours) => (
            <option key={jours} value={jours}>
              {t.periodes[jours]}
            </option>
          ))}
        </select>
        <Button variant="outline" size="sm" onClick={() => setConfirmation(true)} disabled={occupe}>
          <ListOrdered className="h-4 w-4" />
          {t.trierParVentes}
        </Button>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={finGlisser}>
        <SortableContext items={lignes.map((p) => p.id)} strategy={verticalListSortingStrategy}>
          <ol className="space-y-2" aria-label={fr.buvette.groupes[categorie]}>
            {lignes.map((produit, rang) => (
              <LigneMenu
                key={produit.id}
                produit={produit}
                rang={rang}
                total={lignes.length}
                ventes={ventes.data ? (ventesParId.get(produit.id) ?? 0) : undefined}
                occupe={occupe}
                onDeplacer={deplacerLigne}
              />
            ))}
          </ol>
        </SortableContext>
      </DndContext>

      <Dialog open={confirmation} onOpenChange={(o) => !proposer.isPending && setConfirmation(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.trierTitre}</DialogTitle>
            <DialogDescription>
              {t.trierTexte(fr.buvette.groupes[categorie], t.periodes[periode])}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmation(false)}>
              {t.annuler}
            </Button>
            <Button onClick={trier} loading={proposer.isPending}>
              <ListOrdered className="h-4 w-4" />
              {t.trierConfirmer}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * Menu de la tablette : ordre des produits de chaque onglet (glisser-déposer,
 * flèches ↑ ↓ au clavier, « Trier par ventes ») et étiquette de chaque produit.
 */
export function MenuTablette() {
  const t = fr.buvette.tablette.menu;
  const produits = useBuvetteProducts();
  const [onglet, setOnglet] = useState<CaisseCategory>(ONGLETS_MENU[0]);

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">{t.titre}</CardTitle>
        <CardDescription>{t.aide}</CardDescription>
      </CardHeader>
      <CardContent>
        {produits.isError ? (
          <ErrorAlert title={t.erreur} error={produits.error} />
        ) : produits.isLoading ? (
          <Skeleton className="h-48" />
        ) : (
          <Tabs value={onglet} onValueChange={(v) => setOnglet(v as CaisseCategory)}>
            <TabsList className="flex-wrap">
              {ONGLETS_MENU.map((categorie) => (
                <TabsTrigger key={categorie} value={categorie}>
                  {fr.buvette.groupes[categorie]}
                </TabsTrigger>
              ))}
            </TabsList>
            {ONGLETS_MENU.map((categorie) => (
              <TabsContent key={categorie} value={categorie}>
                <OngletMenu categorie={categorie} produits={produits.data ?? []} />
              </TabsContent>
            ))}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
