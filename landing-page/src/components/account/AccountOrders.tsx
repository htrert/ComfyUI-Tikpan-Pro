import { Ban, CheckCircle2, Loader2, Plus, ReceiptText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  cancelRemotePaymentOrder,
  confirmRemotePaymentOrder,
  createRemotePaymentOrder,
  listPublicPaymentProviders,
  listRemotePaymentOrders,
  type PaymentOrder,
  type PaymentProvider,
} from "../../apiClient";
import { formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

export function AccountOrders() {
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [providers, setProviders] = useState<PaymentProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState("mock");
  const [amount, setAmount] = useState("20");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadOrders() {
      try {
        setLoading(true);
        const [remoteProviders, remoteOrders] = await Promise.all([listPublicPaymentProviders(), listRemotePaymentOrders(30)]);
        if (cancelled) return;
        setProviders(remoteProviders);
        setOrders(remoteOrders);
        setSelectedProviderId((current) => current || remoteProviders[0]?.id || "mock");
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Payment order API is unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadOrders();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedProviderId) ?? providers[0] ?? null,
    [providers, selectedProviderId],
  );
  const selectedCurrency = selectedProvider?.currencies[0] ?? "TOKENS";

  async function createOrder() {
    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setMessage("Enter a valid top-up amount.");
      return;
    }

    try {
      setSaving(true);
      const order = await createRemotePaymentOrder(numericAmount, {
        provider: selectedProvider?.id ?? "mock",
        currency: selectedCurrency,
      });
      setOrders((current) => [order, ...current.filter((item) => item.id !== order.id)]);
      setMessage(`Created order ${order.id}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Payment order creation failed.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmOrder(orderId: string) {
    try {
      setSaving(true);
      const result = await confirmRemotePaymentOrder(orderId);
      setOrders((current) => current.map((order) => (order.id === result.order.id ? result.order : order)));
      setMessage(`Order ${result.order.id} paid. Wallet available: ${formatTokens(result.wallet.available)}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Payment confirmation failed.");
    } finally {
      setSaving(false);
    }
  }

  async function cancelOrder(orderId: string) {
    try {
      setSaving(true);
      const order = await cancelRemotePaymentOrder(orderId);
      setOrders((current) => current.map((item) => (item.id === order.id ? order : item)));
      setMessage(`Order ${order.id} cancelled.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Payment cancellation failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Top-up orders</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Payment records</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-500">
              Create, confirm, and cancel wallet top-up orders through the same payment APIs used by the backend billing flow.
            </p>
          </div>
          {loading && (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-black text-slate-500 shadow-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading
            </span>
          )}
        </div>

        <div className="mt-5 grid gap-3 rounded-2xl border border-slate-200/70 bg-white/78 p-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <label className="grid gap-2">
            <span className="text-xs font-black text-slate-500">Payment provider</span>
            <select
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={selectedProviderId}
              onChange={(event) => setSelectedProviderId(event.target.value)}
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} · {provider.checkout_mode}
                </option>
              ))}
              {providers.length === 0 && <option value="mock">Mock Pay</option>}
            </select>
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-black text-slate-500">Top-up amount ({selectedCurrency})</span>
            <input
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              min="0"
              step="0.01"
              type="number"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={saving}
            type="button"
            onClick={() => void createOrder()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create order
          </button>
        </div>

        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}
      </GlassCard>

      <GlassCard className="p-5">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
            <ReceiptText className="h-5 w-5" />
          </span>
          <div>
            <p className="text-lg font-black text-slate-950">Order history</p>
            <p className="mt-1 text-sm font-semibold text-slate-500">Paid orders credit the wallet ledger; pending orders can still be closed.</p>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
          <div className="hidden grid-cols-[1.2fr_0.7fr_0.7fr_0.8fr_1fr_auto] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
            <span>Order</span>
            <span>Amount</span>
            <span>Provider</span>
            <span>Status</span>
            <span>Created</span>
            <span>Action</span>
          </div>
          {orders.map((order) => (
            <div key={order.id} className="grid gap-2 border-t border-slate-100 px-4 py-4 text-sm md:grid-cols-[1.2fr_0.7fr_0.7fr_0.8fr_1fr_auto] md:items-center">
              <span className="font-black text-slate-950">{order.id}</span>
              <span className="font-bold text-slate-700">
                {formatTokens(order.amount)} {order.currency}
              </span>
              <span className="font-bold text-slate-500">{order.provider}</span>
              <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{order.status}</span>
              <span className="font-semibold text-slate-500">{formatDateTime(order.created_at)}</span>
              <span className="flex flex-wrap gap-2">
                {order.status === "pending" && (
                  <>
                    <button
                      className="inline-flex h-8 items-center gap-1.5 rounded-full bg-teal-600 px-3 text-xs font-black text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                      disabled={saving}
                      type="button"
                      onClick={() => void confirmOrder(order.id)}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Confirm
                    </button>
                    <button
                      className="inline-flex h-8 items-center gap-1.5 rounded-full bg-slate-100 px-3 text-xs font-black text-slate-600 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={saving}
                      type="button"
                      onClick={() => void cancelOrder(order.id)}
                    >
                      <Ban className="h-3.5 w-3.5" />
                      Cancel
                    </button>
                  </>
                )}
              </span>
            </div>
          ))}
          {!loading && orders.length === 0 && <p className="px-4 py-10 text-center text-sm font-bold text-slate-400">No payment orders yet</p>}
        </div>
      </GlassCard>
    </div>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
