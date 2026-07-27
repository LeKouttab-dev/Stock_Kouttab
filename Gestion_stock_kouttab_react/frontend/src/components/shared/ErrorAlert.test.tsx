import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { render, screen } from '@testing-library/react';
import { ErrorAlert } from './ErrorAlert';
import { ERROR_MESSAGES } from '@/lib/errors';

function makeAxiosError(code: string, status = 401): AxiosError {
  const err = new AxiosError('Failed');
  err.response = {
    status,
    statusText: 'Unauthorized',
    data: { code, message: 'raw backend message' },
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe('components/shared/ErrorAlert', () => {
  it('renders the FR message and the code by default', () => {
    const err = makeAxiosError('AUTH_1001', 401);
    render(<ErrorAlert error={err} />);

    expect(screen.getByText(ERROR_MESSAGES.AUTH_1001)).toBeInTheDocument();
    expect(screen.getByText('AUTH_1001')).toBeInTheDocument();
    expect(screen.getByText(/HTTP 401/)).toBeInTheDocument();
  });

  it('hides the code line when hideCode is true', () => {
    const err = makeAxiosError('AUTH_1001', 401);
    render(<ErrorAlert error={err} hideCode />);

    expect(screen.getByText(ERROR_MESSAGES.AUTH_1001)).toBeInTheDocument();
    expect(screen.queryByText('AUTH_1001')).not.toBeInTheDocument();
    expect(screen.queryByText(/HTTP 401/)).not.toBeInTheDocument();
  });

  it('uses the fallback message when no error is provided', () => {
    render(<ErrorAlert fallback="Tout est cassé" title="Boom" />);

    expect(screen.getByText('Tout est cassé')).toBeInTheDocument();
    expect(screen.getByText('Boom')).toBeInTheDocument();
  });
});
