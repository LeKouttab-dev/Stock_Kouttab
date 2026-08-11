import logoCarre from '@/assets/logo-kouttab.png';
import logoLarge from '@/assets/logo-kouttab-large.png';
import { cn } from '@/lib/utils';

/**
 * Logo de l'institut.
 *
 * Deux déclinaisons, choisies selon la place disponible plutôt qu'en
 * redimensionnant la même image : la version large est illisible dans un carré
 * de 36 pixels, et la version carrée paraît tassée sur une pleine largeur.
 *
 * - `mark` : version compacte, fond crème, pour un emplacement carré ;
 * - `full` : version horizontale sur fond transparent, pour un en-tête.
 *
 * Remplace le « K » de secours qui tenait lieu d'emblème.
 */
interface LogoProps {
  variant?: 'mark' | 'full';
  className?: string;
  /**
   * Le logo est décoratif quand un titre le double, ce qui est le cas partout
   * où il est utilisé. `alt=""` évite au lecteur d'écran de répéter le nom.
   */
  alt?: string;
}

export function Logo({ variant = 'mark', className, alt = '' }: LogoProps) {
  const src = variant === 'full' ? logoLarge : logoCarre;
  return (
    <img
      src={src}
      alt={alt}
      aria-hidden={alt === '' ? true : undefined}
      className={cn('select-none object-contain', className)}
      draggable={false}
    />
  );
}
