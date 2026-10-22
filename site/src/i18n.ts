import type { Lang } from "./content";
export const SITE = "https://kajisho5.github.io/skillpact/";
export const REPO = "https://github.com/kajisho5/skillpact";
export const prefix = (l: Lang) => (l === "ja" ? "ja/" : "");
export const href = (l: Lang, slug = "") => `/skillpact/${prefix(l)}${slug ? slug + "/" : ""}`;

export const nav: { slug: string; en: string; ja: string }[] = [
  { slug: "spec", en: "Specification", ja: "仕様" },
  { slug: "why", en: "Why", ja: "なぜ必要か" },
  { slug: "guides", en: "Guides", ja: "導入ガイド" },
  { slug: "composition", en: "Composition", ja: "組み合わせ" },
  { slug: "schema", en: "Schema", ja: "スキーマ" },
  { slug: "check", en: "Checker", ja: "チェッカー" },
  { slug: "badges", en: "Badges", ja: "バッジ" },
  { slug: "rationale", en: "Rationale", ja: "設計判断" },
  { slug: "about", en: "About", ja: "概要・運営" },
];
export const ui = {
  en: { skip: "Skip to content", draft: "Working draft", onThisPage: "On this page", source: "Edit source", theme: "Toggle color theme", menu: "Menu", lang: "日本語", langLabel: "Japanese version", footer: "Specification text CC BY 4.0 · Code Apache-2.0", docs: "Documents" },
  ja: { skip: "本文へ移動", draft: "草案", onThisPage: "このページの内容", source: "原稿を編集", theme: "表示テーマを切り替え", menu: "メニュー", lang: "English", langLabel: "English version", footer: "仕様本文 CC BY 4.0 · コード Apache-2.0", docs: "文書" },
} as const;
