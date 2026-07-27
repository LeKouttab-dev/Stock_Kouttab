import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from './StatusBadge';

describe('components/shared/StatusBadge', () => {
  it('renders text + emoji for a known status', () => {
    render(<StatusBadge status="En attente" />);
    // L'emoji est rendu en aria-hidden, on peut l'attraper dans le contenu textuel
    const badge = screen.getByText(/En attente/);
    expect(badge).toBeInTheDocument();
    // Couleur "sand" présente
    expect(badge.className).toContain('bg-sand-100');
  });

  it('uses the validated palette for "Approuvée"', () => {
    render(<StatusBadge status="Approuvée" />);
    const badge = screen.getByText(/Approuvée/);
    expect(badge.className).toContain('bg-sage-200');
  });

  it('falls back to the default gray palette for an unknown status', () => {
    render(<StatusBadge status="ÉtatInconnu" />);
    const badge = screen.getByText(/ÉtatInconnu/);
    expect(badge.className).toContain('bg-gray-100');
  });

  it('does not render emoji when withEmoji=false', () => {
    const { container } = render(<StatusBadge status="En attente" withEmoji={false} />);
    // L'élément emoji a aria-hidden ; vérifions qu'il n'existe pas
    expect(container.querySelector('[aria-hidden]')).toBeNull();
  });
});
