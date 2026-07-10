import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { DocumentCheckIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import { authApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { useDemoStore } from '../stores/demoStore';

interface LoginForm {
  username: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Demo credentials are shown ONLY when the server reports demo mode is on.
  // They must never ship in a real deployment's login screen.
  const { status: demoStatus, credentials, fetchDemoStatus, fetchCredentials } = useDemoStore();
  useEffect(() => {
    void (async () => {
      await fetchDemoStatus();
      await fetchCredentials();
    })();
  }, [fetchDemoStatus, fetchCredentials]);
  const showDemoCredentials = demoStatus?.enabled ?? false;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    try {
      // Login - returns access token in body, refresh token set as httpOnly cookie
      const response = await authApi.login(data.username, data.password);

      // Build user object from response
      const user = {
        id: response.user.id,
        username: response.user.username,
        email: response.user.email,
        full_name: response.user.full_name,
        is_active: response.user.is_active ?? true,
        is_superuser: response.user.is_superuser,
        roles: response.user.roles.map((name: string) => ({ name })),
        permissions: response.user.permissions,
      };

      // Store auth state (access token in memory only, refresh token in httpOnly cookie)
      setAuth(user, response.access_token);

      toast.success('Login successful');
      navigate('/dashboard');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Login failed';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-bank-navy to-bank-blue py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {/* Logo and Title */}
          <div className="text-center mb-8">
            <div className="flex justify-center">
              <div className="bg-bank-navy p-3 rounded-xl">
                <DocumentCheckIcon className="h-10 w-10 text-bank-gold" />
              </div>
            </div>
            <h2 className="mt-4 text-2xl font-bold text-gray-900">Check Review Console</h2>
            <p className="mt-2 text-sm text-gray-600">
              Sign in to access the review queue
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                {...register('username', { required: 'Username is required' })}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <div className="relative mt-1">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  {...register('password', { required: 'Password is required' })}
                  className="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded-r-lg"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeSlashIcon className="h-5 w-5" />
                  ) : (
                    <EyeIcon className="h-5 w-5" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-bank-navy hover:bg-bank-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          {/* Demo credentials hint - rendered only when the server confirms
              demo mode is enabled, and populated from the server response so no
              credentials are baked into the production bundle. */}
          {showDemoCredentials && credentials.length > 0 && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 text-center">Demo accounts</p>
              <ul className="mt-1 space-y-0.5">
                {credentials.map((cred) => (
                  <li key={cred.username} className="text-center text-[11px] text-gray-500">
                    <span className="font-mono text-gray-700">{cred.username}</span>
                    {' / '}
                    <span className="font-mono text-gray-700">{cred.password}</span>
                    {cred.role ? <span className="text-gray-400"> ({cred.role})</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="mt-8 text-center text-sm text-gray-300">
          Bank-grade Check Review System v1.0.0
        </p>
      </div>
    </div>
  );
}
