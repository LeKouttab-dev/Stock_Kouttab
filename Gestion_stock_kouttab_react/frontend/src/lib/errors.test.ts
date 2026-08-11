import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { ERROR_MESSAGES, getErrorCode, getErrorMessage, getErrorStatus } from './errors';

function makeAxiosError(opts: {
  status?: number;
  data?: Record<string, unknown>;
  message?: string;
}): AxiosError {
  const err = new AxiosError(opts.message ?? 'Request failed');
  err.response = {
    status: opts.status ?? 400,
    statusText: 'Bad Request',
    data: opts.data ?? {},
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe('lib/errors', () => {
  describe('getErrorMessage', () => {
    it('returns the FR message for a known code (AUTH_1001)', () => {
      const err = makeAxiosError({
        status: 401,
        data: { code: 'AUTH_1001', message: 'Invalid creds' },
      });
      expect(getErrorMessage(err)).toBe(ERROR_MESSAGES.AUTH_1001);
    });

    it('falls back to backend message when code is unknown', () => {
      const err = makeAxiosError({
        status: 400,
        data: { code: 'UNKNOWN_9999', message: 'Erreur backend brute' },
      });
      expect(getErrorMessage(err)).toBe('Erreur backend brute');
    });

    it('accepts a native Error and returns its message', () => {
      const err = new Error('Boom');
      expect(getErrorMessage(err)).toBe('Boom');
    });

    it('uses the custom fallback when the error has nothing exploitable', () => {
      expect(getErrorMessage(undefined, 'Pas de chance')).toBe('Pas de chance');
    });

    it('returns generic fallback for unknown shapes without fallback', () => {
      expect(getErrorMessage(null)).toBe('Une erreur inattendue est survenue.');
    });

    it('prefers `message` over `detail` (legacy FastAPI shape)', () => {
      const err = makeAxiosError({
        data: { detail: 'old detail', message: 'new message' },
      });
      expect(getErrorMessage(err)).toBe('new message');
    });
  });

  describe('getErrorCode', () => {
    it('extracts the code from an AxiosError payload', () => {
      const err = makeAxiosError({ data: { code: 'AUTH_1001' } });
      expect(getErrorCode(err)).toBe('AUTH_1001');
    });

    it('returns null for non-axios errors', () => {
      expect(getErrorCode(new Error('x'))).toBeNull();
    });
  });

  describe('getErrorStatus', () => {
    it('returns the HTTP status from an AxiosError', () => {
      const err = makeAxiosError({ status: 409 });
      expect(getErrorStatus(err)).toBe(409);
    });

    it('returns null for unknown errors', () => {
      expect(getErrorStatus('boom')).toBeNull();
    });
  });
});
