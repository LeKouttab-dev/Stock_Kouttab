import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import { FileUploader } from '../FileUploader';

/**
 * Une photo déposée partait entière.
 *
 * Le scanner savait déjà cadrer un ticket sur ses quatre coins, mais seulement
 * après une prise de vue. Un justificatif glissé depuis l'ordinateur ou choisi
 * dans la photothèque — le geste le plus courant — n'y avait pas droit : le
 * ticket occupe un dixième de l'image, le reste est la table, et c'est ce PDF
 * là que recevait la comptabilité.
 */

// Le vrai scanner ouvre la caméra au montage : inutilisable sous jsdom, et
// hors sujet ici. Ce qu'on vérifie, c'est QUAND il est proposé.
vi.mock('@/components/scanner/DocumentScanner', () => ({
  DocumentScanner: ({ fichierInitial }: { fichierInitial?: File | null }) => (
    <div data-testid="scanner">{fichierInitial?.name}</div>
  ),
}));

// `accept` explicite : avec le défaut `*`, `userEvent.upload` filtre tout.
const ACCEPT = '.png,.jpg,.jpeg,.pdf,image/*,application/pdf';

const image = (nom = 'ticket.jpg') => new File(['x'], nom, { type: 'image/jpeg' });
const pdf = (nom = 'facture.pdf') => new File(['x'], nom, { type: 'application/pdf' });

describe('components/forms/FileUploader — recadrage', () => {
  it('ouvre le cadrage sur la première image déposée', async () => {
    /* Sans ouverture directe, personne ne pense à recadrer après coup, et le
       gain disparaît. */
    const onChange = vi.fn();
    const { rerender } = renderWithProviders(
      <FileUploader accept={ACCEPT} files={[]} onChange={onChange} recadrage />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, image());

    expect(onChange).toHaveBeenCalled();
    rerender(<FileUploader accept={ACCEPT} files={[image()]} onChange={onChange} recadrage />);
    expect(await screen.findByTestId('scanner')).toHaveTextContent('ticket.jpg');
  });

  it('laisse un PDF tranquille', async () => {
    /* Il est déjà au format attendu par la comptabilité ; le redécouper
       supposerait de le rendre en image, donc de dégrader la pièce. */
    const onChange = vi.fn();
    renderWithProviders(<FileUploader accept={ACCEPT} files={[]} onChange={onChange} recadrage />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, pdf());

    expect(onChange).toHaveBeenCalled();
    expect(screen.queryByTestId('scanner')).not.toBeInTheDocument();
  });

  it('repropose le recadrage sur chaque image de la liste', () => {
    /* Le cadrage se rejuge une fois la pièce vue, et une image ajoutée après
       coup n'aurait sinon aucun moyen d'être recadrée. */
    renderWithProviders(
      <FileUploader
        accept={ACCEPT}
        files={[image('a.jpg'), pdf('b.pdf')]}
        onChange={vi.fn()}
        recadrage
      />,
    );

    expect(screen.getByRole('button', { name: /recadrer a\.jpg/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recadrer b\.pdf/i })).not.toBeInTheDocument();
  });

  it('ne propose rien quand l’option est fermée', async () => {
    /* Import CSV, dépôt de RIB : recadrer un fichier de données n'a aucun sens,
       et le proposer ferait douter de ce qui est attendu. */
    const onChange = vi.fn();
    renderWithProviders(<FileUploader accept={ACCEPT} files={[image()]} onChange={onChange} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, image());

    expect(screen.queryByTestId('scanner')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recadrer/i })).not.toBeInTheDocument();
  });
});
