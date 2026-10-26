import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { BRAND } from "@/lib/brand";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export const metadata: Metadata = {
  title: `À propos d’${BRAND.product} — ${BRAND.company}`,
  description: `${BRAND.name}, un produit porté par ${BRAND.company} pour explorer les marchés vivriers à Madagascar.`,
};

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-6 md:px-10">
        <Link href="/" prefetch={false} aria-label={`${BRAND.product}, accueil`} className="rounded text-xl font-semibold tracking-tight focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring">{BRAND.product}<span className="ml-3 text-xs font-normal text-muted-foreground">{BRAND.descriptor}</span></Link>
        <div className="flex max-w-full flex-wrap items-center gap-3"><ThemeToggle /><Link href="/login" prefetch={false} className="inline-flex min-h-[44px] max-w-full items-center gap-[12px] rounded-lg border border-border px-[16px] py-2 text-sm text-foreground hover:bg-foreground/[0.05] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">Accéder à l’espace<ArrowUpRight aria-hidden="true" className="h-[16px] w-[16px] shrink-0" /></Link></div>
      </header>
      <article className="mx-auto max-w-6xl break-words px-6 md:px-10">
        <section className="grid grid-cols-1 gap-8 py-16 md:grid-cols-[1fr_2.5fr] md:py-24">
          <p className="pt-2 text-sm text-muted-foreground">À propos</p>
          <div>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.13] tracking-tight sm:text-5xl md:text-6xl">{BRAND.product}.<br />Comprendre les marchés vivriers.</h1>
            <p className="mt-8 max-w-2xl text-lg leading-8 text-muted-foreground">Des informations dispersées, des contextes différents, des données à examiner. {BRAND.product} réunit les éléments disponibles pour faciliter la lecture des marchés vivriers à Madagascar.</p>
            <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground">{BRAND.name} est un produit porté par {BRAND.company}. Son développement associe exploration des séries de prix, lecture du contexte et attention à la qualité des données.</p>
          </div>
        </section>
        <section aria-labelledby="approach-title" className="grid grid-cols-1 gap-8 border-t border-border py-12 md:grid-cols-[1fr_2.5fr] md:py-16">
          <h2 id="approach-title" className="text-sm font-medium text-muted-foreground">Une lecture attentive</h2>
          <div className="divide-y divide-border">
            {[
              ["01", "Situer les informations", "Un produit, un territoire, une période et une unité : le contexte est nécessaire pour comprendre une série de prix."],
              ["02", "Distinguer les valeurs", "Une observation, une estimation et une prévision ne racontent pas la même chose. Leur nature doit rester visible."],
              ["03", "Examiner les limites", "La disponibilité d’une série ne suffit pas à garantir sa couverture ou sa qualité. Les sources et leur qualification comptent."],
            ].map(([number, title, description]) => <div key={number} className="grid grid-cols-[2rem_1fr] gap-4 py-6 first:pt-0"><span className="pt-1 text-xs tabular-nums text-muted-foreground">{number}</span><div><h3 className="text-lg font-medium text-foreground">{title}</h3><p className="mt-2 max-w-xl text-sm leading-7 text-muted-foreground">{description}</p></div></div>)}
          </div>
        </section>
        <section aria-labelledby="company-title" className="grid grid-cols-1 gap-8 border-t border-border py-12 md:grid-cols-[1fr_2.5fr] md:py-16">
          <p className="text-sm text-muted-foreground">L’entreprise mère</p>
          <div>
            <h2 id="company-title" className="text-3xl font-semibold tracking-tight text-foreground">{BRAND.company}</h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-muted-foreground">{BRAND.company} conçoit des solutions numériques intelligentes pour aider les entreprises à mieux exploiter leurs données, structurer leurs opérations et faire évoluer leurs outils métier.</p>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">Collecte de données, ERP et logiciels augmentés par l’IA : chaque solution part d’un besoin concret et vise une utilité opérationnelle claire.</p>
            <dl className="mt-8 space-y-6 border-l border-border pl-5">
              <div><dt className="text-sm font-medium text-foreground">Données et collecte</dt><dd className="mt-1 text-sm leading-7 text-muted-foreground">Rassembler et structurer les informations utiles à l’activité de l’entreprise.</dd></div>
              <div><dt className="text-sm font-medium text-foreground">ERP et gestion</dt><dd className="mt-1 text-sm leading-7 text-muted-foreground">Relier les processus, les équipes et l’information dans des outils adaptés au métier.</dd></div>
              <div><dt className="text-sm font-medium text-foreground">Logiciels augmentés par l’IA</dt><dd className="mt-1 text-sm leading-7 text-muted-foreground">Intégrer des fonctions intelligentes pour accompagner les usages et les décisions du quotidien.</dd></div>
            </dl>
            <p className="mt-8 max-w-2xl text-sm leading-7 text-muted-foreground">Entreprise mère d’{BRAND.product}, {BRAND.company} en porte le développement. Le nom {BRAND.company} succède à {BRAND.previousCompany} ; {BRAND.product} conserve une identité propre, centrée sur l’intelligence de marché.</p>
          </div>
        </section>
        <section aria-labelledby="stage-title" className="grid grid-cols-1 gap-8 border-t border-border py-12 md:grid-cols-[1fr_2.5fr] md:py-16">
          <h2 id="stage-title" className="text-sm font-medium text-muted-foreground">Un produit en développement</h2>
          <div><p className="max-w-2xl text-base leading-8 text-muted-foreground">La disponibilité et la qualification des données varient selon les sources. Les séries présentées ne constituent pas, à elles seules, une recommandation d’achat ou une prévision validée.</p><Link href="/login" prefetch={false} className="mt-8 inline-flex min-h-11 items-center gap-3 rounded-lg bg-primary-action px-5 py-3 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring">Découvrir l’espace de travail<ArrowRight aria-hidden="true" className="h-4 w-4" /></Link></div>
        </section>
      </article>
      <footer className="mx-auto flex max-w-6xl flex-wrap justify-between gap-3 border-t border-border px-6 py-8 text-xs text-muted-foreground md:px-10"><span>{BRAND.name}</span><span>Un produit {BRAND.company}</span></footer>
    </div>
  );
}
