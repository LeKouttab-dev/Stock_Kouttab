import { forwardRef, useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { fr } from '@/lib/i18n/fr';

type PasswordInputProps = React.ComponentPropsWithoutRef<typeof Input> & {
  /** Masque l'icône de cadenas quand le champ est déjà dans un contexte explicite. */
  withIcon?: boolean;
};

/**
 * Champ mot de passe avec bouton d'affichage.
 *
 * Saisir un mot de passe à l'aveugle sur un téléphone est la première cause de
 * refus de connexion : les claviers mobiles corrigent, capitalisent, et rien ne
 * permet de s'en apercevoir. Le bouton est donc systématique, pas optionnel.
 *
 * Il porte `tabIndex={-1}` : au clavier, la tabulation doit aller du champ vers
 * le bouton de validation, pas s'arrêter sur une commande d'affichage.
 */
export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, withIcon = true, ...props }, ref) => {
    const [visible, setVisible] = useState(false);

    return (
      <div className="relative">
        {withIcon && (
          <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        )}
        <Input
          ref={ref}
          type={visible ? 'text' : 'password'}
          className={cn(withIcon && 'pl-10', 'pr-10', className)}
          {...props}
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? fr.auth.hidePassword : fr.auth.showPassword}
          aria-pressed={visible}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    );
  },
);

PasswordInput.displayName = 'PasswordInput';
