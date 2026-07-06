import { Bell, KeyRound, Loader2, Mail, Plus, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createRemoteApiKey,
  getRemoteMe,
  listRemoteApiKeys,
  revokeRemoteApiKey,
  upsertRemoteUser,
  type PlatformApiKey,
  type UserConsoleProfile,
} from "../../apiClient";
import type { UserProfile } from "../../types";
import { formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

const demoUserId = "demo_user";

export function AccountSettings({ user }: { user: UserProfile }) {
  const [profile, setProfile] = useState<UserConsoleProfile | null>(null);
  const [apiKeys, setApiKeys] = useState<PlatformApiKey[]>([]);
  const [displayName, setDisplayName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [keyName, setKeyName] = useState("Workspace automation key");
  const [newSecret, setNewSecret] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        setLoading(true);
        const [remoteProfile, keys] = await Promise.all([getRemoteMe(), listRemoteApiKeys(demoUserId)]);
        if (cancelled) return;
        setProfile(remoteProfile);
        setApiKeys(keys);
        setDisplayName(remoteProfile.user.display_name || user.name);
        setEmail(remoteProfile.user.email || user.email);
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Account API is unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadSettings();
    return () => {
      cancelled = true;
    };
  }, [user.email, user.name]);

  const activeKeys = useMemo(() => apiKeys.filter((key) => key.status === "active"), [apiKeys]);

  async function saveProfile() {
    try {
      setSaving(true);
      const saved = await upsertRemoteUser(
        {
          display_name: displayName,
          email,
          status: "active",
        },
        profile?.user.id ?? demoUserId,
      );
      setProfile((current) => (current ? { ...current, user: saved } : current));
      setMessage("Profile saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Profile save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function createApiKey() {
    if (!keyName.trim()) {
      setMessage("API key name is required.");
      return;
    }

    try {
      setSaving(true);
      const key = await createRemoteApiKey(keyName.trim(), profile?.user.id ?? demoUserId);
      setApiKeys((current) => [key, ...current.filter((item) => item.id !== key.id)]);
      setNewSecret(key.secret ?? "");
      setMessage(`Created API key ${key.name}. The secret is shown once.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "API key creation failed.");
    } finally {
      setSaving(false);
    }
  }

  async function revokeApiKey(keyId: string) {
    try {
      setSaving(true);
      const key = await revokeRemoteApiKey(keyId);
      setApiKeys((current) => current.map((item) => (item.id === key.id ? key : item)));
      setMessage(`Revoked API key ${key.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "API key revoke failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Account settings</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Profile and API access</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-500">
              Manage the user profile, subscription snapshot, notification preference, and API keys used by automation clients.
            </p>
          </div>
          {loading && (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-black text-slate-500 shadow-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading
            </span>
          )}
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <label className="grid gap-2">
            <span className="flex items-center gap-2 text-xs font-black text-slate-500">
              <UserRound className="h-4 w-4" />
              Display name
            </span>
            <input
              className="h-12 rounded-xl border border-slate-200 bg-white/80 px-4 text-sm font-bold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label className="grid gap-2">
            <span className="flex items-center gap-2 text-xs font-black text-slate-500">
              <Mail className="h-4 w-4" />
              Email
            </span>
            <input
              className="h-12 rounded-xl border border-slate-200 bg-white/80 px-4 text-sm font-bold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
        </div>

        <button
          className="mt-4 inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={saving}
          type="button"
          onClick={() => void saveProfile()}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Save profile
        </button>

        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
        <GlassCard className="p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <Bell className="h-4 w-4" />
            </span>
            <div>
              <p className="font-black text-slate-950">Account snapshot</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">Live values from the user console profile.</p>
            </div>
          </div>

          <div className="mt-4 grid gap-3">
            <Info label="User ID" value={profile?.user.id ?? demoUserId} />
            <Info label="Plan" value={profile?.plan?.name ?? user.plan} />
            <Info label="Subscription" value={String(profile?.subscription?.status ?? "active")} />
            <Info label="Wallet available" value={profile?.wallet ? formatTokens(profile.wallet.available) : formatTokens(user.tokens)} />
            <Info label="Active API keys" value={String(activeKeys.length)} />
          </div>

          <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-sm font-black text-slate-600">
            <input defaultChecked className="accent-teal-600" type="checkbox" />
            Task and wallet notifications
          </label>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-50 text-violet-700">
              <KeyRound className="h-5 w-5" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">API keys</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">Create keys for automation. Newly generated secrets are only shown once.</p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200/70 bg-white/78 p-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <label className="grid gap-2">
              <span className="text-xs font-black text-slate-500">New key name</span>
              <input
                className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                value={keyName}
                onChange={(event) => setKeyName(event.target.value)}
              />
            </label>
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={saving}
              type="button"
              onClick={() => void createApiKey()}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Create key
            </button>
          </div>

          {newSecret && (
            <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50/80 p-4">
              <p className="text-xs font-black text-amber-900">New secret</p>
              <p className="mt-2 break-all font-mono text-xs font-bold leading-5 text-amber-800">{newSecret}</p>
            </div>
          )}

          <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
            <div className="hidden grid-cols-[1fr_0.8fr_0.8fr_1fr_auto] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
              <span>Name</span>
              <span>Prefix</span>
              <span>Status</span>
              <span>Created</span>
              <span>Action</span>
            </div>
            {apiKeys.map((key) => (
              <div key={key.id} className="grid gap-2 border-t border-slate-100 px-4 py-4 text-sm md:grid-cols-[1fr_0.8fr_0.8fr_1fr_auto] md:items-center">
                <span className="font-black text-slate-950">{key.name}</span>
                <span className="font-mono text-xs font-bold text-slate-500">{key.masked || key.prefix}</span>
                <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{key.status}</span>
                <span className="font-semibold text-slate-500">{formatDateTime(key.created_at)}</span>
                <span>
                  {key.status === "active" && (
                    <button
                      className="inline-flex h-8 items-center gap-1.5 rounded-full bg-rose-50 px-3 text-xs font-black text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={saving}
                      type="button"
                      onClick={() => void revokeApiKey(key.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Revoke
                    </button>
                  )}
                </span>
              </div>
            ))}
            {!loading && apiKeys.length === 0 && <p className="px-4 py-10 text-center text-sm font-bold text-slate-400">No API keys yet</p>}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200/70 bg-white/78 p-3">
      <p className="text-xs font-black text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-black leading-5 text-slate-800">{value}</p>
    </div>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
