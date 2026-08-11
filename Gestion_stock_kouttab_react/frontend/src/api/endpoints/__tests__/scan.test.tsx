import { describe, expect, it } from 'vitest';
import { buildScanFormData } from '../scan';

/**
 * Ces tests figent les *noms de champs* du multipart envoyé à
 * `app/api/v1/endpoints/scan.py`. Quatre décalages front/back de ce type ont
 * été trouvés dans l'application, tous invisibles jusqu'à l'exécution.
 *
 * La vérification porte sur la construction du corps plutôt que sur la requête
 * complète : jsdom ne sait pas sérialiser un FormData multipart à travers
 * axios, et un test qui passe par le réseau resterait bloqué sans rien prouver
 * de plus sur le contrat.
 */
describe('api/endpoints/scan — corps multipart', () => {
  const photo = () => new Blob(['x'], { type: 'image/jpeg' });

  it('envoie la photo sous le champ `file`', () => {
    const form = buildScanFormData({ photo: photo() });

    expect(form.has('file')).toBe(true);
    expect((form.get('file') as File).name).toBe('scan.jpg');
  });

  it('sérialise les quatre coins en JSON sous `corners`', () => {
    const corners = [
      { x: 1, y: 2 },
      { x: 3, y: 4 },
      { x: 5, y: 6 },
      { x: 7, y: 8 },
    ];

    const form = buildScanFormData({ photo: photo(), corners });

    expect(JSON.parse(form.get('corners') as string)).toEqual(corners);
  });

  it('omet `corners` quand le cadrage est laissé au serveur', () => {
    expect(buildScanFormData({ photo: photo(), corners: null }).has('corners')).toBe(false);
    expect(buildScanFormData({ photo: photo() }).has('corners')).toBe(false);
  });

  it('active le nettoyage par défaut et respecte une désactivation explicite', () => {
    expect(buildScanFormData({ photo: photo() }).get('enhance')).toBe('true');
    expect(buildScanFormData({ photo: photo(), enhance: false }).get('enhance')).toBe('false');
  });
});
