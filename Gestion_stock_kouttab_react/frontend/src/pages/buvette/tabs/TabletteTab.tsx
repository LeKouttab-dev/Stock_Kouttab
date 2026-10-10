import { useEffect, useState, type ReactNode } from 'react';
import { BatteryCharging, BatteryMedium, Plus, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import {
  useBuvetteReglages,
  useCaisseEtat,
  useUpdateBuvetteReglages,
  useUpdateTauxFraisCarte,
} from '@/api/endpoints/buvette';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import { emailValide, formatDepuis, tabletteSilencieuse } from '@/lib/buvette';
import { formatDateTime, formatTauxPb, parseTauxPb } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { cn } from '@/lib/utils';
import type { CaisseEtat } from '@/types/api';

function Ligne({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm font-medium">{children}</dd>
    </div>
  );
}

/** ok = vert, veille = gris neutre (rien d'anormal), ko = rouge. */
type Ton = 'ok' | 'veille' | 'ko';

interface EtatAffiche {
  ton: Ton;
  libelle: string;
}

/**
 * Compte SumUp : l'état fin prime ; à défaut (ancienne version de l'app), le
 * booléen. « Enregistré » = jeton pas encore rechargé après un redémarrage, le
 * compte se réveille seul au prochain paiement : rien à faire, donc vert.
 */
function etatSumup(etat: CaisseEtat): EtatAffiche {
  const t = fr.buvette.tablette;
  switch (etat.sumup_etat) {
    case 'connecte':
      return { ton: 'ok', libelle: t.connecte };
    case 'enregistre':
      return { ton: 'ok', libelle: t.sumupEnregistre };
    case 'deconnecte':
      return { ton: 'ko', libelle: t.deconnecte };
    default:
      return etat.sumup_connecte
        ? { ton: 'ok', libelle: t.connecte }
        : { ton: 'ko', libelle: t.deconnecte };
  }
}

/**
 * Lecteur de carte : en veille (Bluetooth coupé, il se réveille au paiement)
 * n'est pas une panne, d'où le gris neutre et non le rouge.
 */
function etatLecteur(etat: CaisseEtat): EtatAffiche {
  const t = fr.buvette.tablette;
  switch (etat.lecteur_etat) {
    case 'connecte':
      return { ton: 'ok', libelle: t.connecte };
    case 'en_veille':
      return { ton: 'veille', libelle: t.lecteurEnVeille };
    case 'non_appaire':
      return { ton: 'ko', libelle: t.lecteurNonAppaire };
    default:
      return etat.lecteur_connecte
        ? { ton: 'ok', libelle: t.connecte }
        : { ton: 'ko', libelle: t.deconnecte };
  }
}

function Connexion({ etat, testId }: { etat: EtatAffiche; testId: string }) {
  return (
    <Badge
      data-testid={testId}
      data-ton={etat.ton}
      variant={etat.ton === 'ok' ? 'success' : etat.ton === 'ko' ? 'destructive' : 'outline'}
      className={cn(etat.ton === 'veille' && 'border-gray-300 bg-gray-100 text-gray-700')}
    >
      {etat.libelle}
    </Badge>
  );
}

function pct(v: number | null): string {
  return v === null ? '?' : `${v} %`;
}

function DetailEtat({ etat }: { etat: CaisseEtat }) {
  const t = fr.buvette.tablette;
  const sumup = etatSumup(etat);
  const lecteur = etatLecteur(etat);
  return (
    <dl>
      <Ligne label={t.batterie}>
        <span className="inline-flex items-center gap-1.5">
          {etat.en_charge ? (
            <BatteryCharging className="h-4 w-4 text-sage-700" aria-hidden />
          ) : (
            <BatteryMedium className="h-4 w-4" aria-hidden />
          )}
          {pct(etat.batterie_pct)}
          {etat.en_charge && <span className="text-muted-foreground">({t.enCharge})</span>}
        </span>
      </Ligne>
      <Ligne label={t.version}>
        {etat.version_name} <span className="text-muted-foreground">({etat.version_code})</span>
      </Ligne>
      <Ligne label={t.sumup}>
        <Connexion etat={sumup} testId="etat-sumup" />
      </Ligne>
      <Ligne label={t.lecteur}>
        <span className="inline-flex items-center gap-2">
          {lecteur.ton === 'ok' && etat.lecteur_batterie_pct !== null && (
            <span className="text-muted-foreground">{pct(etat.lecteur_batterie_pct)}</span>
          )}
          <Connexion etat={lecteur} testId="etat-lecteur" />
        </span>
      </Ligne>
      <Ligne label={t.ventesAttente}>
        <span className={cn(etat.ventes_en_attente > 0 && 'text-orange-600')}>
          {etat.ventes_en_attente}
        </span>
      </Ligne>
      <Ligne label={t.ventesRejetees}>
        <span className={cn(etat.ventes_rejetees > 0 && 'text-red-700')}>
          {etat.ventes_rejetees}
        </span>
      </Ligne>
      <Ligne label={t.ecran}>{t.ecrans[etat.ecran] ?? etat.ecran}</Ligne>
    </dl>
  );
}

export function EtatTablette() {
  const t = fr.buvette.tablette;
  const { data, isLoading, isError, error } = useCaisseEtat();
  const etat = data?.etat ?? null;
  const secondes = etat ? etat.secondes_depuis : null;
  const silencieuse = tabletteSilencieuse(secondes);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t.etat}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isError ? (
          <ErrorAlert title={t.erreur} error={error} />
        ) : isLoading ? (
          <Skeleton className="h-48" />
        ) : (
          <>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.dernierContact}
              </p>
              <p
                data-testid="dernier-contact"
                data-silencieuse={silencieuse}
                className={cn(
                  'font-serif text-2xl font-bold',
                  silencieuse ? 'text-red-700' : 'text-sage-700',
                )}
                title={etat ? formatDateTime(etat.recu_at) : undefined}
              >
                {formatDepuis(secondes)}
              </p>
              {etat && silencieuse && <p className="text-xs text-red-700">{t.horsLigne}</p>}
            </div>
            {etat ? (
              <DetailEtat etat={etat} />
            ) : (
              <p className="text-sm text-muted-foreground">{t.jamaisVue}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ReglagesDestinataires() {
  const t = fr.buvette.tablette;
  const toast = useToast();
  const reglages = useBuvetteReglages();
  const enregistrer = useUpdateBuvetteReglages();

  const [adresses, setAdresses] = useState<string[]>([]);
  const [nouvelle, setNouvelle] = useState('');
  const [erreur, setErreur] = useState<string | null>(null);

  // La liste éditée repart de ce que le serveur a enregistré, à chaque relecture.
  useEffect(() => {
    if (reglages.data) setAdresses(reglages.data.recap_destinataires);
  }, [reglages.data]);

  const ajouter = () => {
    const email = nouvelle.trim();
    if (!emailValide(email)) {
      setErreur(t.adresseInvalide);
      return;
    }
    if (adresses.some((a) => a.toLowerCase() === email.toLowerCase())) {
      setErreur(t.adresseDoublon);
      return;
    }
    setAdresses([...adresses, email]);
    setNouvelle('');
    setErreur(null);
  };

  const modifie =
    reglages.data !== undefined &&
    JSON.stringify(adresses) !== JSON.stringify(reglages.data.recap_destinataires);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t.reglages}</CardTitle>
        <CardDescription>{t.reglagesAide}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {reglages.isError ? (
          <ErrorAlert error={reglages.error} />
        ) : reglages.isLoading ? (
          <Skeleton className="h-32" />
        ) : (
          <>
            <ul className="space-y-1.5">
              {adresses.length === 0 && (
                <li className="text-sm text-muted-foreground">{t.aucuneAdresse}</li>
              )}
              {adresses.map((a) => (
                <li
                  key={a}
                  className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5 text-sm"
                >
                  <span className="truncate">{a}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    aria-label={t.retirer(a)}
                    onClick={() => setAdresses(adresses.filter((x) => x !== a))}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>

            <div className="space-y-1">
              <div className="flex gap-2">
                <Input
                  type="email"
                  aria-label={t.nouvelleAdresse}
                  placeholder={t.nouvelleAdresse}
                  value={nouvelle}
                  hasError={erreur !== null}
                  onChange={(e) => {
                    setNouvelle(e.target.value);
                    setErreur(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      ajouter();
                    }
                  }}
                />
                <Button variant="outline" onClick={ajouter} disabled={nouvelle.trim() === ''}>
                  <Plus className="h-4 w-4" />
                  {t.ajouterAdresse}
                </Button>
              </div>
              {erreur && <p className="text-xs text-destructive">{erreur}</p>}
            </div>

            <Button
              onClick={() =>
                enregistrer.mutate(adresses, { onSuccess: () => toast.success(t.enregistre) })
              }
              disabled={!modifie}
              loading={enregistrer.isPending}
            >
              {t.enregistrer}
            </Button>

            <div className="space-y-2 border-t border-border pt-4">
              <p className="text-sm font-medium">{t.comptesAdminStock}</p>
              {(reglages.data?.comptes_admin_stock ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">{t.aucunCompteAdminStock}</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {reglages.data?.comptes_admin_stock.map((c) => (
                    <li key={c.id}>
                      {c.nom} <span className="text-muted-foreground">({c.email})</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Taux des frais SumUp sur la carte : saisi en %, stocké en points de base. */
function ReglageFraisCarte() {
  const t = fr.buvette.tablette;
  const toast = useToast();
  const reglages = useBuvetteReglages();
  const enregistrer = useUpdateTauxFraisCarte();
  const [saisie, setSaisie] = useState('');
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (reglages.data) setSaisie(formatTauxPb(reglages.data.taux_frais_carte_pb).replace(' %', ''));
  }, [reglages.data]);

  const taux = parseTauxPb(saisie);
  // Saisie illisible : bouton actif, pour afficher l'erreur au clic.
  const modifie = reglages.data !== undefined && taux !== reglages.data.taux_frais_carte_pb;

  const valider = () => {
    if (taux === null || taux > 1000) {
      setErreur(t.fraisInvalide);
      return;
    }
    enregistrer.mutate(taux, { onSuccess: () => toast.success(t.fraisEnregistre) });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t.fraisTitre}</CardTitle>
        <CardDescription>{t.fraisAide}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {reglages.isError ? (
          <ErrorAlert error={reglages.error} />
        ) : reglages.isLoading ? (
          <Skeleton className="h-10" />
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Input
                aria-label={t.fraisLabel}
                inputMode="decimal"
                className="w-28"
                value={saisie}
                hasError={erreur !== null}
                onChange={(e) => {
                  setSaisie(e.target.value);
                  setErreur(null);
                }}
              />
              <span className="text-sm text-muted-foreground">%</span>
              <Button onClick={valider} disabled={!modifie} loading={enregistrer.isPending}>
                {t.enregistrer}
              </Button>
            </div>
            {erreur && <p className="text-xs text-destructive">{erreur}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function TabletteTab() {
  const { can } = useAuth();
  // Les réglages sont réservés aux gestionnaires (le serveur refuse la lecture aux autres).
  const canReglages = can(ACTIONS.BUVETTE_REGLAGES);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <EtatTablette />
      {canReglages && <ReglagesDestinataires />}
      {canReglages && <ReglageFraisCarte />}
    </div>
  );
}
