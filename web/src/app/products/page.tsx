"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Layers,
  Package,
  Plus,
  Search,
  Tag,
  TrendingUp,
  UploadCloud,
  X,
} from "lucide-react";
import { formatPrice } from "@/lib/formatters";

interface ProductItem {
  product_id: string;
  product_code: string;
  canonical_name_fr: string;
  category: string;
  base_unit: string;
  hs6_codes: string[];
  faostat_item_codes: string[];
  aliases: string[];
}

const CATEGORY_LABELS: Record<string, string> = {
  cereal: "Céréale",
  root_tuber: "Tubercule & Racine",
  pulse: "Légumineuse",
  pulse_oilseed: "Oléagineux",
  oil: "Huile alimentaire",
  sugar: "Sucre",
  flour: "Farine",
  spice: "Épice",
  vegetable: "Maraîchage / Légume",
  fruit: "Fruit",
  cash_crop: "Culture de rente",
  other: "Autre denrée",
};

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  // Modals state
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isObsModalOpen, setIsObsModalOpen] = useState(false);
  const [selectedProductForObs, setSelectedProductForObs] = useState<string>("");

  // New product form
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("other");
  const [newUnit, setNewUnit] = useState("kg");
  const [newHsCode, setNewHsCode] = useState("");
  const [newAliases, setNewAliases] = useState("");
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  // New observations form
  const [obsDate, setObsDate] = useState("2026-10-01");
  const [obsLocation, setObsLocation] = useState("MDG");
  const [obsActor, setObsActor] = useState("retail");
  const [obsPrice, setObsPrice] = useState("");
  const [obsSource, setObsSource] = useState("Relevé de marché direct");
  const [obsSubmitting, setObsSubmitting] = useState(false);
  const [obsError, setObsError] = useState<string | null>(null);
  const [obsSuccess, setObsSuccess] = useState<string | null>(null);

  const fetchProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/products");
      if (!res.ok) throw new Error(`Erreur HTTP ${res.status} lors du chargement des produits`);
      const data: ProductItem[] = await res.json();
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchProducts();
  }, []);

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setFormError(null);
    setFormSuccess(null);

    const cleanCode = newCode.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
    if (!cleanCode || cleanCode.length < 3) {
      setFormError("Le code produit doit comporter au moins 3 caractères alphanumériques.");
      setFormSubmitting(false);
      return;
    }
    if (!newName.trim()) {
      setFormError("Le nom officiel français est obligatoire.");
      setFormSubmitting(false);
      return;
    }

    const aliasesList = newAliases
      .split(",")
      .map((a) => a.trim())
      .filter(Boolean);

    const hsList = newHsCode
      .split(",")
      .map((h) => h.trim())
      .filter((h) => h.length === 6 && /^\d+$/.test(h));

    try {
      const res = await fetch("/api/v1/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          product_code: cleanCode,
          canonical_name_fr: newName.trim(),
          category: newCategory,
          base_unit: newUnit.trim().toLowerCase(),
          hs6_codes: hsList,
          aliases: aliasesList,
          notes: "Créé via l'application Irooa Market Intelligence",
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Échec de création (HTTP ${res.status})`);
      }

      setFormSuccess(`Le produit "${newName}" (${cleanCode}) a été ajouté avec succès !`);
      setNewCode("");
      setNewName("");
      setNewAliases("");
      setNewHsCode("");
      await fetchProducts();
      setTimeout(() => {
        setIsNewModalOpen(false);
        setFormSuccess(null);
      }, 1500);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Erreur lors de la création");
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleAddObservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProductForObs) return;
    setObsSubmitting(true);
    setObsError(null);
    setObsSuccess(null);

    const numPrice = parseFloat(obsPrice);
    if (isNaN(numPrice) || numPrice <= 0) {
      setObsError("Veuillez saisir un prix valide supérieur à 0.");
      setObsSubmitting(false);
      return;
    }

    try {
      const res = await fetch(`/api/v1/products/${encodeURIComponent(selectedProductForObs)}/observations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          observations: [
            {
              date: obsDate.trim(),
              location_pcode: obsLocation.trim().toUpperCase(),
              actor_level: obsActor,
              price: numPrice,
              currency: "MGA",
              unit: "kg",
              source_name: obsSource.trim(),
            },
          ],
          notes: "Saisie directe via l'interface de gestion des produits",
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Erreur d'importation (HTTP ${res.status})`);
      }

      const receipt = await res.json();
      setObsSuccess(`Observation enregistrée avec succès (Empreinte Bronze : ${receipt.bronze_content_hash.slice(0, 10)}…) !`);
      setObsPrice("");
      setTimeout(() => {
        setIsObsModalOpen(false);
        setObsSuccess(null);
      }, 1800);
    } catch (err) {
      setObsError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement de l'observation");
    } finally {
      setObsSubmitting(false);
    }
  };

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      !search ||
      p.product_code.toLowerCase().includes(search.toLowerCase()) ||
      p.canonical_name_fr.toLowerCase().includes(search.toLowerCase()) ||
      p.aliases.some((a) => a.toLowerCase().includes(search.toLowerCase()));
    const matchesCat = !categoryFilter || p.category === categoryFilter;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold">
            <Package aria-hidden="true" className="h-6 w-6 text-primary-readable" />
            Catalogue & Gestion des Produits
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Référentiel des commodités agricoles et vivrières suivies à Madagascar. Ajoutez de nouveaux produits avec leurs synonymes et importez des séries de prix réels avec provenance vérifiable à 100 %.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => {
              setIsNewModalOpen(true);
              setFormError(null);
              setFormSuccess(null);
            }}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            + Nouveau Produit
          </button>

          <button
            type="button"
            onClick={() => {
              if (products.length > 0 && !selectedProductForObs) {
                setSelectedProductForObs(products[0].product_code);
              }
              setIsObsModalOpen(true);
              setObsError(null);
              setObsSuccess(null);
            }}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-semibold hover:bg-muted transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            <UploadCloud aria-hidden="true" className="h-4 w-4 text-orange-500" />
            Importer des relevés
          </button>
        </div>
      </header>

      {/* Summary KPI Cards */}
      <section aria-label="Statistiques du catalogue" className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Total Commodités</span>
          <div className="text-2xl font-bold font-mono text-foreground">{products.length}</div>
          <p className="text-[11px] text-muted-foreground">Vivriers de base, épices, et cultures suivies</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Catégories Actives</span>
          <div className="text-2xl font-bold font-mono text-orange-600 dark:text-orange-400">
            {new Set(products.map((p) => p.category)).size}
          </div>
          <p className="text-[11px] text-muted-foreground">Céréales, légumineuses, huiles, épices, etc.</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Provenance & Traçabilité</span>
          <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">100 %</div>
          <p className="text-[11px] text-muted-foreground">Bronze immuable (SHA-256) & Rejouabilité</p>
        </div>
      </section>

      {/* Filter and Search Bar */}
      <section aria-label="Filtres du catalogue" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
        <div className="relative flex-1 min-w-[260px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher par nom, code ou synonyme…"
            className="w-full rounded-lg border border-border bg-background pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium">Catégorie :</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Toutes les catégories</option>
            {Object.entries(CATEGORY_LABELS).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Products Table */}
      {loading ? (
        <p role="status" className="text-sm text-muted-foreground py-8 text-center">
          Chargement du catalogue des produits…
        </p>
      ) : error ? (
        <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </p>
      ) : filteredProducts.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center space-y-3">
          <Package className="h-8 w-8 text-muted-foreground mx-auto" />
          <h2 className="text-base font-semibold">Aucun produit ne correspond à votre recherche</h2>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Vous pouvez ajouter une nouvelle commodité vivrière ou agricole en cliquant sur le bouton « + Nouveau Produit ».
          </p>
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Liste des produits référencés et leurs caractéristiques</caption>
              <thead className="bg-muted/50 text-muted-foreground border-b border-border">
                <tr>
                  <th scope="col" className="p-3 font-medium">Code produit</th>
                  <th scope="col" className="p-3 font-medium">Nom officiel</th>
                  <th scope="col" className="p-3 font-medium">Catégorie</th>
                  <th scope="col" className="p-3 font-medium">Unité de base</th>
                  <th scope="col" className="p-3 font-medium">Synonymes & Alias détectés</th>
                  <th scope="col" className="p-3 font-medium">Code SH6</th>
                  <th scope="col" className="p-3 font-medium text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredProducts.map((p) => (
                  <tr key={p.product_code} className="hover:bg-muted/30 transition-colors">
                    <td className="p-3 font-mono font-bold text-xs text-foreground whitespace-nowrap">
                      {p.product_code}
                    </td>
                    <th scope="row" className="p-3 font-semibold text-foreground whitespace-nowrap">
                      {p.canonical_name_fr}
                    </th>
                    <td className="p-3 text-xs whitespace-nowrap">
                      <span className="inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground border border-border">
                        {CATEGORY_LABELS[p.category] || p.category}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                      {p.base_unit}
                    </td>
                    <td className="p-3 text-xs max-w-xs">
                      <div className="flex flex-wrap gap-1">
                        {p.aliases.slice(0, 4).map((alias) => (
                          <span
                            key={alias}
                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-800 dark:text-orange-300 text-[10px] font-mono border border-orange-500/20"
                          >
                            <Tag className="h-2.5 w-2.5" /> {alias}
                          </span>
                        ))}
                        {p.aliases.length > 4 && (
                          <span className="text-[10px] text-muted-foreground font-mono self-center">
                            +{p.aliases.length - 4}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-3 font-mono text-xs text-muted-foreground whitespace-nowrap">
                      {p.hs6_codes?.length ? p.hs6_codes.join(", ") : "—"}
                    </td>
                    <td className="p-3 text-center whitespace-nowrap">
                      <div className="inline-flex items-center gap-2">
                        <Link
                          href={`/prices?product=${encodeURIComponent(p.product_code)}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-orange-500/10 text-orange-700 dark:text-orange-400 hover:bg-orange-500/20 transition-colors"
                          title="Consulter les prix et prédictions pour ce produit"
                        >
                          <TrendingUp className="h-3.5 w-3.5" />
                          Prix
                        </Link>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedProductForObs(p.product_code);
                            setIsObsModalOpen(true);
                            setObsError(null);
                            setObsSuccess(null);
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border border-border hover:bg-muted transition-colors"
                          title="Ajouter un relevé de prix pour ce produit"
                        >
                          <UploadCloud className="h-3.5 w-3.5 text-muted-foreground" />
                          + Relevé
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* MODAL 1: NOUVEAU PRODUIT */}
      {isNewModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground">
                <Plus className="h-5 w-5 text-orange-500" />
                Ajouter une nouvelle commodité
              </h2>
              <button
                type="button"
                onClick={() => setIsNewModalOpen(false)}
                className="text-muted-foreground hover:text-foreground rounded-lg p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateProduct} className="space-y-4 text-sm">
              {formError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}
              {formSuccess && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{formSuccess}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Code Produit (Majuscule) *
                  </label>
                  <input
                    type="text"
                    required
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                    placeholder="ex: VANILLA, ONION_RED"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring uppercase"
                  />
                  <p className="text-[10px] text-muted-foreground">Identifiant unique machine</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Nom officiel en français *
                  </label>
                  <input
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="ex: Vanille naturelle"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="text-[10px] text-muted-foreground">Affiché dans les menus et rapports</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Catégorie
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {Object.entries(CATEGORY_LABELS).map(([code, label]) => (
                      <option key={code} value={code}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Unité de base
                  </label>
                  <select
                    value={newUnit}
                    onChange={(e) => setNewUnit(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="kg">kg (Kilogramme)</option>
                    <option value="l">l (Litre)</option>
                    <option value="t">t (Tonne)</option>
                    <option value="botte">botte (Botte)</option>
                    <option value="piece">piece (Pièce)</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">
                  Synonymes / Alias de détection (séparés par des virgules)
                </label>
                <input
                  type="text"
                  value={newAliases}
                  onChange={(e) => setNewAliases(e.target.value)}
                  placeholder="ex: vanille, gousse de vanille, vanilla"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="text-[10px] text-muted-foreground">
                  Les collectes et fichiers contenant ces mots-clés seront automatiquement associés à ce produit.
                </p>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">
                  Code douanier SH6 (Optionnel)
                </label>
                <input
                  type="text"
                  value={newHsCode}
                  onChange={(e) => setNewHsCode(e.target.value)}
                  placeholder="ex: 090500"
                  maxLength={6}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="text-[10px] text-muted-foreground">Code à 6 chiffres pour l'analyse des imports/exports</p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setIsNewModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted font-medium transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-5 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-semibold text-sm shadow-sm transition-colors disabled:opacity-50"
                >
                  {formSubmitting ? "Enregistrement…" : "Créer le produit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: IMPORTER DES OBSERVATIONS */}
      {isObsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground">
                <UploadCloud className="h-5 w-5 text-orange-500" />
                Importer un relevé de prix (Provenance 100 %)
              </h2>
              <button
                type="button"
                onClick={() => setIsObsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground rounded-lg p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleAddObservation} className="space-y-4 text-sm">
              {obsError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{obsError}</span>
                </div>
              )}
              {obsSuccess && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{obsSuccess}</span>
                </div>
              )}

              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">
                  Produit cible *
                </label>
                <select
                  value={selectedProductForObs}
                  onChange={(e) => setSelectedProductForObs(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {products.map((p) => (
                    <option key={p.product_code} value={p.product_code}>
                      {p.canonical_name_fr} ({p.product_code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Date du relevé (YYYY-MM-DD ou YYYY-MM) *
                  </label>
                  <input
                    type="text"
                    required
                    value={obsDate}
                    onChange={(e) => setObsDate(e.target.value)}
                    placeholder="2026-10-01"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Zone géographique (P-code)
                  </label>
                  <select
                    value={obsLocation}
                    onChange={(e) => setObsLocation(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="MDG">MDG (National)</option>
                    <option value="MDG11">MDG11 (Analamanga / Antananarivo)</option>
                    <option value="MDG12">MDG12 (Vakinankaratra / Antsirabe)</option>
                    <option value="MDG21">MDG21 (Diana / Antsiranana)</option>
                    <option value="MDG22">MDG22 (Sava / Sambava)</option>
                    <option value="MDG31">MDG31 (Itasy / Miarinarivo)</option>
                    <option value="MDG41">MDG41 (Mahajanga)</option>
                    <option value="MDG51">MDG51 (Atsinanana / Toamasina)</option>
                    <option value="MDG61">MDG61 (Atsimo-Andrefana / Toliara)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Stade de vente
                  </label>
                  <select
                    value={obsActor}
                    onChange={(e) => setObsActor(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="retail">Détail (Consommateur)</option>
                    <option value="wholesale">Gros (Grossiste)</option>
                    <option value="producer">Producteur</option>
                    <option value="farmgate">Bord champ</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">
                    Prix observé (Ariary / kg) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={obsPrice}
                    onChange={(e) => setObsPrice(e.target.value)}
                    placeholder="ex: 2800"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">
                  Source ou Enquête de collecte
                </label>
                <input
                  type="text"
                  value={obsSource}
                  onChange={(e) => setObsSource(e.target.value)}
                  placeholder="ex: Relevé marché Analakely"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div className="p-3 rounded-lg bg-muted/40 border border-border text-[11px] text-muted-foreground space-y-1">
                <div className="font-semibold text-foreground flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  Règle de traçabilité absolue (AGENTS.md §4) :
                </div>
                <p>
                  Ce relevé sera déposé dans le magasin Bronze MinIO avec empreinte immuable SHA-256 avant d'être injecté dans la couche Silver et agrégé dans les vues Gold.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setIsObsModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-muted font-medium transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={obsSubmitting}
                  className="px-5 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-semibold text-sm shadow-sm transition-colors disabled:opacity-50"
                >
                  {obsSubmitting ? "Enregistrement…" : "Enregistrer l'observation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
