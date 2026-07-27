import { Check, X } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { passwordStrength } from '@/lib/schemas/auth';
import { cn } from '@/lib/utils';

interface PasswordStrengthMeterProps {
  password: string;
}

const labels = ['Très faible', 'Faible', 'Moyen', 'Bon', 'Excellent'];
// Échelle progressive cohérente avec la charte (du danger au sage validé)
const tones = [
  'bg-red-500',
  'bg-terracotta-400',
  'bg-terracotta-500',
  'bg-sage-500',
  'bg-sage-700',
];

export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  if (!password) return null;
  const { score, checks } = passwordStrength(password);
  const pct = (score / 4) * 100;

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground">
          Force du mot de passe : <strong>{labels[score]}</strong>
        </span>
        <span className="text-xs text-muted-foreground">{score}/4</span>
      </div>
      <Progress value={pct} indicatorClassName={tones[score]} />
      <ul className="space-y-1 mt-2">
        {checks.map((c) => (
          <li
            key={c.label}
            className={cn(
              'flex items-center gap-1.5 text-xs',
              c.ok ? 'text-sage-700' : 'text-muted-foreground',
            )}
          >
            {c.ok ? (
              <Check className="h-3.5 w-3.5 text-sage-700" />
            ) : (
              <X className="h-3.5 w-3.5 text-red-500" />
            )}
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
