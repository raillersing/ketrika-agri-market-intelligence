"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Search, X } from "lucide-react";
import { searchNavigationPages, type NavigationPage } from "@/lib/navigation";
import { NAVIGATION_ICONS } from "./navigation-icons";

export function CommandPalette({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const id = useId();
  const items = searchNavigationPages(query);
  const select = (page: NavigationPage) => { onClose(); router.push(page.href); };

  useEffect(() => {
    if (!isOpen) return;
    setQuery("");
    setSelectedIndex(0);
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    inputRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) document.getElementById(`${id}-option-${selectedIndex}`)?.scrollIntoView({ block: "nearest" });
  }, [id, selectedIndex, isOpen]);

  if (!isOpen) return null;
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setSelectedIndex(index => (index + step + items.length) % (items.length || 1));
    }
    if (event.key === "Enter" && document.activeElement === inputRef.current && items[selectedIndex]) {
      event.preventDefault(); select(items[selectedIndex]);
    }
    if (event.key === "Tab") {
      const controls = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('input, button:not([tabindex="-1"])') || []);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/65 px-4 pb-8 pt-[10vh]" onClick={onClose}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} onKeyDown={onKeyDown} onClick={event => event.stopPropagation()}
        className="max-h-[80dvh] w-full max-w-xl overflow-hidden rounded-xl border border-border bg-popover shadow-2xl">
        <h2 id={`${id}-title`} className="sr-only">Aller à une page</h2>
        <div className="flex items-center gap-3 border-b border-border px-4 py-2">
          <Search aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
          <input ref={inputRef} type="text" role="combobox" aria-label="Rechercher une page" aria-expanded="true" aria-controls={`${id}-results`} aria-autocomplete="list"
            aria-activedescendant={items[selectedIndex] ? `${id}-option-${selectedIndex}` : undefined}
            value={query} onChange={event => { setQuery(event.target.value); setSelectedIndex(0); }} placeholder="Quelle page cherchez-vous ?"
            className="min-h-11 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground" />
          <button type="button" aria-label="Fermer la recherche" onClick={onClose} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-foreground/[0.05] hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><X aria-hidden="true" className="h-4 w-4" /></button>
        </div>
        <ul id={`${id}-results`} role="listbox" aria-label="Pages" className="max-h-[55dvh] overflow-y-auto p-2">
          {items.map((page, index) => {
            const Icon = NAVIGATION_ICONS[page.icon];
            return <li key={page.href} role="presentation"><button type="button" role="option" id={`${id}-option-${index}`} aria-selected={index === selectedIndex} tabIndex={-1} onClick={() => select(page)} onMouseEnter={() => setSelectedIndex(index)}
              className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm ${index === selectedIndex ? "bg-foreground/[0.08] text-foreground" : "text-muted-foreground hover:bg-foreground/[0.04]"}`}>
              <Icon aria-hidden="true" strokeWidth={1.7} className="h-4 w-4 shrink-0 text-muted-foreground" /><span className="min-w-0 flex-1">{page.label}</span><span className="hidden text-xs text-muted-foreground sm:inline">{page.group}</span>{index === selectedIndex && <ArrowRight aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
            </button></li>;
          })}
        </ul>
        {!items.length && <p role="status" className="px-6 py-8 text-sm text-muted-foreground">Aucune page pour « {query} ».</p>}
        <p className="border-t border-border px-4 py-3 text-xs text-muted-foreground">↑ ↓ pour parcourir · Entrée pour ouvrir · Échap pour fermer</p>
      </div>
    </div>
  );
}
