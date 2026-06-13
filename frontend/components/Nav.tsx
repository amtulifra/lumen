"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

type Role = "viewer" | "editor" | "admin" | "owner";

const navLinks: Array<{ href: string; label: string; minRole: Role }> = [
  { href: "/", label: "ingest", minRole: "editor" },
  { href: "/hypotheses", label: "hypotheses", minRole: "editor" },
  { href: "/conflicts", label: "conflicts", minRole: "viewer" },
];

const ROLE_RANK: Record<Role, number> = {
  viewer: 1,
  editor: 2,
  admin: 3,
  owner: 4,
};

export default function Nav() {
  const [workspaceId, setWorkspaceId] = useState("");
  const [role, setRole] = useState<Role>("owner");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const ws = window.localStorage.getItem("lumen.workspaceId") ?? "";
    const storedRole = (window.localStorage.getItem("lumen.role") as Role | null) ?? "owner";
    setWorkspaceId(ws);
    setRole(storedRole);
  }, []);

  const { data } = useSWR("notifications-unread", () => api.getNotifications(true), {
    refreshInterval: 30000,
  });
  const unreadCount = (data as unknown[])?.length ?? 0;

  const visibleLinks = navLinks.filter((link) => ROLE_RANK[role] >= ROLE_RANK[link.minRole]);

  return (
    <header className="border-b border-border px-6 py-3 flex items-center gap-6">
      <Link href="/" className="text-accent font-semibold tracking-widest text-sm">
        lumen
      </Link>
      <nav className="flex gap-6 flex-1">
        {visibleLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="text-muted hover:text-text text-xs transition-colors"
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <input
        value={workspaceId}
        onChange={(e) => {
          const value = e.target.value;
          setWorkspaceId(value);
          if (typeof window !== "undefined") window.localStorage.setItem("lumen.workspaceId", value);
        }}
        placeholder="workspace-id"
        className="w-52 bg-panel border border-border rounded px-2 py-1 text-[10px] text-muted focus:text-text outline-none focus:border-accent"
      />
      <Link href="/notifications" className="relative text-muted hover:text-text text-xs transition-colors">
        notifications
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-3 bg-accent text-surface text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </Link>
    </header>
  );
}
