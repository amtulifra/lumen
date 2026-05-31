"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

interface Notification {
  id: string;
  type: string;
  message: string;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const { data, mutate } = useSWR("notifications", () => api.getNotifications());
  const items = (data as Notification[]) ?? [];
  const unread = items.filter((n) => !n.read).length;

  async function handleReadAll() {
    await api.markAllRead();
    mutate();
  }

  async function handleRead(id: string) {
    await api.markRead(id);
    mutate();
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-lg font-semibold text-text">notifications</h1>
          <p className="text-xs text-muted">{unread} unread</p>
        </div>
        {unread > 0 && (
          <button
            onClick={handleReadAll}
            className="text-xs text-muted hover:text-text border border-border rounded px-3 py-1.5 transition-colors"
          >
            mark all read
          </button>
        )}
      </div>

      {items.length === 0 && (
        <p className="text-xs text-muted">no notifications yet.</p>
      )}

      <div className="space-y-2">
        {items.map((n) => (
          <div
            key={n.id}
            className={`border rounded p-4 space-y-1 transition-colors ${
              n.read ? "border-border" : "border-accent/30 bg-panel"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm text-text">{n.message}</p>
              {!n.read && (
                <button
                  onClick={() => handleRead(n.id)}
                  className="shrink-0 text-xs text-muted hover:text-text transition-colors"
                >
                  dismiss
                </button>
              )}
            </div>
            <p className="text-xs text-muted">
              {new Date(n.created_at).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
