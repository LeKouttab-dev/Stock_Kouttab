import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** Serveur MSW partagé entre tous les tests (lifecycle géré dans setup.ts). */
export const server = setupServer(...handlers);
