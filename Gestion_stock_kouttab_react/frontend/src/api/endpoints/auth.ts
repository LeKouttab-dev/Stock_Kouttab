import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { useAuthStore } from '@/stores/auth';
import { useApiMutation } from '@/hooks/useApiMutation';
import type {
  AdminSetupRequest,
  LoginRequest,
  LoginResponse,
  ProfileUpdateRequest,
  SignupRequest,
  User,
} from '@/types/api';

export const authQueryKeys = {
  me: ['auth', 'me'] as const,
  profile: ['auth', 'profile'] as const,
};

async function login(payload: LoginRequest): Promise<LoginResponse> {
  // Le backend expose deux endpoints : /auth/login (form-urlencoded OAuth2) et
  // /auth/login/json (JSON). On utilise le JSON pour rester cohérent avec le reste.
  const { data } = await api.post<LoginResponse>('/auth/login/json', payload);
  return data;
}

async function signup(payload: SignupRequest): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>('/auth/signup', payload);
  return data;
}

async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

async function adminSetup(payload: AdminSetupRequest): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/admin-setup', payload);
  return data;
}

async function validateInvitation(params: {
  token: string;
  email: string;
}): Promise<{ valid: boolean; email: string }> {
  const { data } = await api.get<{ valid: boolean; email: string }>('/auth/validate-invitation', {
    params,
  });
  return data;
}

async function fetchProfile(): Promise<User> {
  const { data } = await api.get<User>('/users/me/profile');
  return data;
}

async function updateProfile(payload: ProfileUpdateRequest): Promise<User> {
  const { data } = await api.patch<User>('/users/me/profile', payload);
  return data;
}

async function logoutApi(): Promise<void> {
  try {
    await api.post('/auth/logout');
  } catch {
    /* ignore */
  }
}

/* ---------- Hooks ---------- */
// `silentToast: true` sur login/signup/admin-setup : les pages affichent déjà
// un <ErrorAlert/> en bas du formulaire, on n'ajoute pas de toast doublon.
export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  return useApiMutation({
    mutationFn: login,
    silentToast: true,
    onSuccess: (data) => {
      setSession({
        user: data.user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
    },
  });
}

export function useSignup() {
  return useApiMutation({ mutationFn: signup, silentToast: true });
}

export function useAdminSetup() {
  const setSession = useAuthStore((s) => s.setSession);
  return useApiMutation({
    mutationFn: adminSetup,
    silentToast: true,
    onSuccess: (data) => {
      setSession({
        user: data.user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
    },
  });
}

export function useValidateInvitation(token: string | null, email: string | null) {
  return useQuery({
    queryKey: ['auth', 'invitation', token, email],
    queryFn: () => validateInvitation({ token: token!, email: email! }),
    enabled: Boolean(token && email),
    retry: false,
  });
}

export function useMe() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: authQueryKeys.me,
    queryFn: fetchMe,
    enabled: Boolean(accessToken),
    staleTime: 5 * 60 * 1000,
  });
}

export function useProfile() {
  return useQuery({ queryKey: authQueryKeys.profile, queryFn: fetchProfile });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  return useApiMutation({
    mutationFn: updateProfile,
    onSuccess: (user) => {
      setUser(user);
      qc.invalidateQueries({ queryKey: authQueryKeys.profile });
      qc.invalidateQueries({ queryKey: authQueryKeys.me });
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: logoutApi,
    silentToast: true,
    onSettled: () => {
      logout();
      qc.clear();
    },
  });
}
