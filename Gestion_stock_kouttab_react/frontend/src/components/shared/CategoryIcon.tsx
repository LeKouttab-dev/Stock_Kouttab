import {
  Archive,
  BookOpen,
  Boxes,
  Brush,
  Car,
  Laptop,
  Lock,
  PartyPopper,
  PenLine,
  Phone,
  SprayCan,
  UtensilsCrossed,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Icône d'une catégorie de stock.
 *
 * Les catégories étaient illustrées par des emojis, dont le dessin change d'un
 * système à l'autre : le même écran n'a pas le même rendu sur Windows, Android
 * et iOS, et les tailles ne s'alignent pas avec le reste de l'interface. Les
 * icônes vectorielles héritent au contraire de la couleur du texte et de la
 * taille demandée.
 *
 * Ne concerne que l'affichage. L'emoji porté par un *article* reste une donnée
 * saisie par les bénévoles, stockée en base : il n'est pas remplacé ici.
 */
const PAR_CATEGORIE: Record<string, LucideIcon> = {
  Nourriture: UtensilsCrossed,
  Fournitures: PenLine,
  Intendance: SprayCan,
  Bibliothèque: BookOpen,
  Hygiène: SprayCan,
  Entretien: Brush,
  Bureau: PenLine,
  Informatique: Laptop,
  Sécurité: Lock,
  Transport: Car,
  Communication: Phone,
  Événementiel: PartyPopper,
  Papeterie: PenLine,
};

/** Repli pour une catégorie créée par un administrateur et non répertoriée. */
const DEFAUT = Boxes;

export function categoryIcon(nom: string): LucideIcon {
  return PAR_CATEGORIE[nom] ?? DEFAUT;
}

export function CategoryIcon({ nom, className }: { nom: string; className?: string }) {
  const Icone = categoryIcon(nom);
  return <Icone className={cn('h-5 w-5', className)} aria-hidden />;
}

export { Archive };
