import { describe, expect, it } from 'vitest';
import { api } from './client';

/**
 * Un envoi de fichier ne doit jamais partir étiqueté « JSON ».
 *
 * L'instance axios pose `Content-Type: application/json` par défaut, ce qui
 * écrase la détection d'axios : un `FormData` partait sans sa frontière
 * (`boundary`), le serveur ne parvenait pas à le découper, et rendait un
 * `VAL_5001` que rien n'expliquait à l'écran.
 *
 * Chaque appel multipart devait donc penser à rétablir l'en-tête à la main.
 * Cinq le faisaient ; le dépôt du RIB l'avait oublié, et échouait pour cette
 * seule raison. L'interception supprime la classe de bug plutôt que le cas.
 */
async function entetesDe(config: Parameters<typeof api.request>[0]) {
  // On exécute la chaîne d'intercepteurs de requête sans partir sur le réseau.
  const handlers = (api.interceptors.request as unknown as {
    handlers: { fulfilled: (c: unknown) => unknown }[];
  }).handlers;

  let resultat: Record<string, unknown> = {
    ...config,
    headers: { 'Content-Type': 'application/json', ...(config.headers ?? {}) },
  };
  for (const handler of handlers) {
    if (handler?.fulfilled) resultat = (await handler.fulfilled(resultat)) as typeof resultat;
  }
  return resultat.headers as Record<string, string>;
}

describe('api/client — en-têtes', () => {
  it('retire le Content-Type JSON quand le corps est un FormData', async () => {
    const corps = new FormData();
    corps.append('file', new File(['%PDF-1.4'], 'rib.pdf', { type: 'application/pdf' }));

    const headers = await entetesDe({ url: '/users/me/rib-document', method: 'post', data: corps });

    // Absent, et non « multipart/form-data » : seul le navigateur connaît la
    // frontière qu'il va employer.
    expect(headers['Content-Type']).toBeUndefined();
  });

  it('laisse le Content-Type JSON sur un corps ordinaire', async () => {
    const headers = await entetesDe({ url: '/auth/login/json', method: 'post', data: { a: 1 } });
    expect(headers['Content-Type']).toBe('application/json');
  });
});
