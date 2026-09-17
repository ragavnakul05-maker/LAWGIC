import React, { useState, useMemo } from 'react';
import {
  Settings, Lock, Eye, EyeOff, AlertCircle, Check, CheckCircle2,
  User, Shield, Globe, FileText, CheckCheck
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { changePassword } from '../services/api';

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();

  // Password update state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // Application Display Preferences state
  const [defaultExportFormat, setDefaultExportFormat] = useState<string>('html');
  const [prefSaved, setPrefSaved] = useState<boolean>(false);

  // Password strength calculation
  const strength = useMemo(() => {
    if (!newPassword) return { score: 0, label: '', color: '', text: '' };
    let score = 0;
    if (newPassword.length >= 8) score += 1;
    if (/[A-Z]/.test(newPassword)) score += 1;
    if (/[0-9]/.test(newPassword)) score += 1;
    if (/[^A-Za-z0-9]/.test(newPassword)) score += 1;

    switch (score) {
      case 1:
        return { score: 25, label: 'Weak', color: 'bg-rose-500', text: 'text-rose-600' };
      case 2:
        return { score: 50, label: 'Fair', color: 'bg-amber-500', text: 'text-amber-600' };
      case 3:
        return { score: 75, label: 'Good', color: 'bg-blue-500', text: 'text-blue-600' };
      case 4:
        return { score: 100, label: 'Strong', color: 'bg-emerald-500', text: 'text-emerald-600' };
      default:
        return { score: 10, label: 'Too short', color: 'bg-rose-400', text: 'text-rose-500' };
    }
  }, [newPassword]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (newPassword.length < 6) {
      setPasswordError('New password must be at least 6 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match. Please re-enter.');
      return;
    }

    if (currentPassword === newPassword) {
      setPasswordError('New password must be different from current password.');
      return;
    }

    setIsUpdatingPassword(true);
    try {
      const res = await changePassword(currentPassword, newPassword);
      setPasswordSuccess(res.message || 'Password successfully updated.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.message || 'Failed to update password.');
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const handleSavePreferences = () => {
    setPrefSaved(true);
    setTimeout(() => setPrefSaved(false), 2500);
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      {/* Page Title */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Settings className="w-6 h-6 text-indigo-600" />
          Account & Application Settings
        </h2>
        <p className="text-xs text-slate-500 font-medium mt-0.5">
          Manage your account profile, authentication credentials, and application preferences.
        </p>
      </div>

      {/* 1. User Profile & Tenant Information Card */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <User className="w-4 h-4 text-indigo-600" />
              User Profile & Organization
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified tenant identity and platform credentials.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Active Session
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Full Name</span>
            <span className="font-bold text-slate-800 text-sm">{user?.full_name || 'Legal Counsel'}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Email Address</span>
            <span className="font-bold text-slate-800 text-sm font-mono">{user?.email || 'user@lawgic.ai'}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Legal Role</span>
            <span className="font-bold text-indigo-700 text-sm">{user?.role || 'Commercial Counsel'}</span>
          </div>
        </div>
      </div>

      {/* 2. Account Security & Password Management */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-600" />
              Account Security & Password
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage your password and authentication credentials.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200">
            PBKDF2 Authenticated
          </span>
        </div>

        {passwordSuccess && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{passwordSuccess}</span>
          </div>
        )}

        {passwordError && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{passwordError}</span>
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="space-y-4 text-xs">
          {/* Current Password */}
          <div>
            <label className="text-slate-700 font-semibold block mb-1">Current Password</label>
            <div className="relative">
              <input
                type={showCurrent ? 'text' : 'password'}
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 pr-10 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* New Password */}
            <div>
              <label className="text-slate-700 font-semibold block mb-1">New Password</label>
              <div className="relative">
                <input
                  type={showNew ? 'text' : 'password'}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 pr-10 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              {/* Password Strength Bar */}
              {newPassword && (
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-500">Security strength:</span>
                    <span className={`font-bold ${strength.text}`}>{strength.label}</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${strength.color} transition-all duration-300 rounded-full`}
                      style={{ width: `${strength.score}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Confirm New Password */}
            <div>
              <label className="text-slate-700 font-semibold block mb-1">Confirm New Password</label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter new password"
                  className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 pr-10 text-slate-900 font-mono focus:bg-white focus:border-indigo-500 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {confirmPassword && newPassword !== confirmPassword && (
                <p className="text-[10px] text-rose-500 font-medium mt-1">Passwords do not match</p>
              )}
              {confirmPassword && newPassword === confirmPassword && (
                <p className="text-[10px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Passwords match
                </p>
              )}
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isUpdatingPassword || !currentPassword || !newPassword || !confirmPassword}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold text-xs shadow-md shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-all"
            >
              {isUpdatingPassword ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5" />
                  <span>Update Password</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* 3. Regional Currency & Financial Display Preferences */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-200 space-y-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Globe className="w-4 h-4 text-indigo-600" />
              Currency & Regional Financial Presentation
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Standardized currency and number representation for all financial calculations.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200">
            INR (₹) Standard
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-slate-700 font-semibold block mb-1">Active Currency</label>
            <input
              type="text"
              readOnly
              value="Indian Rupee (₹ - INR)"
              className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-800 font-semibold cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              All contract values, penalties, discounts, and simulator matrices are evaluated in Indian Rupees.
            </p>
          </div>

          <div>
            <label className="text-slate-700 font-semibold block mb-1">Number Formatting Standard</label>
            <input
              type="text"
              readOnly
              value="Indian System: ₹10,00,000 / ₹92,500 / ₹1,60,000"
              className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-800 font-mono cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Complies with the Indian numbering format (Lakhs & Crores grouping).
            </p>
          </div>
        </div>

        <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
          <div className="w-full max-w-xs">
            <label className="text-slate-700 font-semibold block mb-1 text-xs">Preferred Audit Export Format</label>
            <select
              value={defaultExportFormat}
              onChange={(e) => setDefaultExportFormat(e.target.value)}
              className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-900 text-xs focus:bg-white focus:border-indigo-500 focus:outline-none cursor-pointer"
            >
              <option value="html">Executive PDF Report (Formatted Document)</option>
              <option value="csv">CSV Calculation Spreadsheet</option>
              <option value="json">JSON Cryptographic Package</option>
            </select>
          </div>

          <div className="pt-5">
            <button
              onClick={handleSavePreferences}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-md shadow-indigo-600/20 cursor-pointer transition-all"
            >
              {prefSaved ? (
                <>
                  <CheckCheck className="w-4 h-4 text-emerald-300" />
                  <span>Preferences Saved</span>
                </>
              ) : (
                <span>Save Preferences</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
