import React, { useState, useEffect } from 'react';
import {
  Zap, Lock, ArrowRight, Eye, EyeOff, AlertCircle, CheckCircle2, RefreshCw
} from 'lucide-react';
import { verifyResetToken, resetPassword } from '../services/api';

interface ResetPasswordPageProps {
  token?: string;
  onNavigateToLogin: () => void;
}

export const ResetPasswordPage: React.FC<ResetPasswordPageProps> = ({
  token: propToken,
  onNavigateToLogin,
}) => {
  // Robust token extraction from prop, search query, or hash
  const token = (() => {
    if (propToken) return propToken.trim().replace(/\/$/, '');
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const sToken = searchParams.get('token');
      if (sToken) return sToken.trim().replace(/\/$/, '');

      if (window.location.hash) {
        const hash = window.location.hash;
        const qIdx = hash.indexOf('?');
        if (qIdx !== -1) {
          const hashParams = new URLSearchParams(hash.substring(qIdx));
          const hToken = hashParams.get('token');
          if (hToken) return hToken.trim().replace(/\/$/, '');
        }
      }
    } catch {
      // ignore
    }
    return '';
  })();

  const [isVerifying, setIsVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setIsVerifying(false);
      setTokenValid(false);
      setTokenError('No password reset token was provided in the link.');
      return;
    }

    verifyResetToken(token)
      .then(() => {
        setTokenValid(true);
        setTokenError(null);
      })
      .catch((err: any) => {
        setTokenValid(false);
        setTokenError(err.message || 'This password reset link is invalid or has expired.');
      })
      .finally(() => {
        setIsVerifying(false);
      });
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (newPassword.length < 6) {
      setSubmitError('Password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setSubmitError('Passwords do not match. Please re-enter.');
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPassword(token, newPassword);
      setIsSuccess(true);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to reset password. Please request a new link.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-slate-50 text-slate-800 font-sans flex items-center justify-center p-4 sm:p-6 lg:p-8 selection:bg-indigo-500 selection:text-white overflow-hidden">
      {/* Background Ambient Glowing Orbs & Dot Grid */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-32 -left-32 w-[32rem] h-[32rem] bg-indigo-300/40 rounded-full blur-3xl animate-orb-1" />
        <div className="absolute top-1/4 -right-32 w-[30rem] h-[30rem] bg-cyan-300/35 rounded-full blur-3xl animate-orb-2" />
        <div className="absolute -bottom-32 left-1/3 w-[36rem] h-[36rem] bg-violet-300/30 rounded-full blur-3xl animate-orb-3" />
        <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:28px_28px] opacity-40" />
      </div>

      <div className="relative z-10 w-full max-w-md mx-auto">
        <div className="bg-white/90 backdrop-blur-xl border border-slate-200/90 shadow-xl shadow-slate-200/60 rounded-3xl p-6 sm:p-8 space-y-6">
          
          {/* Header & Branding */}
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-500 shadow-md shadow-indigo-500/25">
              <Zap className="w-6 h-6 text-white fill-current" />
            </div>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
                LAWGIC
              </h1>
              <p className="text-[11px] font-bold text-indigo-600 tracking-wider uppercase">
                Secure Account Recovery
              </p>
            </div>
          </div>

          {/* Verifying Token Spinner */}
          {isVerifying && (
            <div className="py-8 text-center space-y-3">
              <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mx-auto" />
              <p className="text-xs text-slate-500 font-medium">
                Verifying password reset security token...
              </p>
            </div>
          )}

          {/* Invalid or Expired Token State */}
          {!isVerifying && !tokenValid && (
            <div className="space-y-4 text-center py-2">
              <div className="w-12 h-12 rounded-2xl bg-rose-100 border border-rose-200 text-rose-600 flex items-center justify-center mx-auto">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h2 className="text-sm font-bold text-slate-900">Invalid or Expired Link</h2>
                <p className="text-xs text-slate-500 max-w-xs mx-auto">
                  {tokenError || 'This reset link has either expired or already been used. Please request a new link.'}
                </p>
              </div>
              <button
                type="button"
                onClick={onNavigateToLogin}
                className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-sm cursor-pointer"
              >
                Back to Sign In
              </button>
            </div>
          )}

          {/* Successful Password Reset State */}
          {!isVerifying && isSuccess && (
            <div className="space-y-4 text-center py-2">
              <div className="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-200 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h2 className="text-sm font-bold text-slate-900">Password Reset Complete</h2>
                <p className="text-xs text-slate-500 max-w-xs mx-auto">
                  Your password has been securely updated. You can now sign in with your new credentials.
                </p>
              </div>
              <button
                type="button"
                onClick={onNavigateToLogin}
                className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2"
              >
                <span>Sign In to LAWGIC</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Valid Token Form State */}
          {!isVerifying && tokenValid && !isSuccess && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="text-center space-y-0.5">
                <h2 className="text-sm font-bold text-slate-900">Create New Password</h2>
                <p className="text-xs text-slate-500">
                  Enter and confirm your new account password below.
                </p>
              </div>

              {submitError && (
                <div className="flex items-center gap-2.5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  New Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 6 characters"
                    className="w-full bg-slate-50/80 border border-slate-200 rounded-xl pl-10 pr-10 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Confirm New Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your new password"
                    className="w-full bg-slate-50/80 border border-slate-200 rounded-xl pl-10 pr-10 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                  >
                    {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full mt-2 py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white text-xs font-bold shadow-md shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Update Password</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={onNavigateToLogin}
                  className="text-xs text-slate-500 hover:text-slate-800 font-medium cursor-pointer transition-colors"
                >
                  Return to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Footer Note */}
          <div className="pt-2 border-t border-slate-100 text-center">
            <p className="text-[11px] text-slate-400">
              Contract → Legal IR → Validation → Deterministic Math
            </p>
          </div>

        </div>
      </div>
    </div>
  );
};
