import { LogOut, Menu, ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown';
import { RoleBadge } from '@/components/shared/RoleBadge';
import { useAuth } from '@/hooks/useAuth';
import { useLogout } from '@/api/endpoints/auth';
import { getInitials } from '@/lib/utils';
import { fr } from '@/lib/i18n/fr';

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const handleLogout = async () => {
    await logoutMutation.mutateAsync();
    navigate('/login', { replace: true });
  };

  if (!user) return null;

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-card/90 px-4 text-forest backdrop-blur lg:px-6">
      <Button
        variant="ghost"
        size="icon"
        onClick={onMenuClick}
        className="lg:hidden"
        aria-label="Ouvrir le menu"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <h1 className="font-serif text-base font-semibold text-forest lg:text-lg">{fr.app.title}</h1>

      <div className="ml-auto flex items-center gap-3">
        <RoleBadge role={user.role} className="hidden sm:inline-flex" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent transition-colors"
              aria-label="Menu utilisateur"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {getInitials(user.prenom, user.nom)}
              </div>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-medium leading-tight">
                  {user.prenom} {user.nom}
                </p>
                <p className="text-xs text-muted-foreground leading-tight">@{user.username}</p>
              </div>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <p className="font-medium">
                {user.prenom} {user.nom}
              </p>
              <p className="text-xs text-muted-foreground">{user.email}</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => navigate('/profile')}>
              {fr.nav.profile}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={handleLogout}
              className="text-destructive focus:text-destructive"
            >
              <LogOut className="mr-2 h-4 w-4" />
              {fr.nav.logout}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
