import type { Lang } from "@/content";
import { Layout, PageHeader } from "@/components/Layout";
import { SITE } from "@/i18n";

const levels = ["L1", "L2", "L3", "none"] as const;
export default function Badges({ lang }: { lang: Lang }) {
  const ja = lang === "ja";
  const title = ja ? "バッジ" : "Badges";
  const lead = ja ? "README に SkillPact のレベルを表示するための静的な SVG です。skillpact conformance（または GitHub Action）で実際に到達したレベルのものを使ってください。バッジは主張であって証明ではありません。読む人はいつでも確認し直せます。"
    : "Static SVGs for showing a skill's SkillPact level in a README. Use the badge for the level the skill actually reaches with skillpact conformance (or the GitHub Action). A badge is a claim, not proof; readers can always re-check.";
  const label: Record<string, [string, string]> = { L1: ["Declared", "宣言済み"], L2: ["Tested", "テスト済み"], L3: ["Signed", "署名済み"], none: ["No contract / failed", "契約なし・不合格"] };
  return (
    <Layout lang={lang} slug="badges" title={title} description={lead}>
      <PageHeader eyebrow="SVG" title={title} lead={lead} />
      <ul className="max-w-[52rem] divide-y border-y">
        {levels.map((l) => {
          const url = `${SITE}badges/skillpact-${l}.svg`;
          const md = `[![SkillPact ${l}](${url})](${SITE})`;
          return (
            <li key={l} className="grid gap-3 py-6 sm:grid-cols-[10rem_1fr] sm:gap-8">
              <div>
                <img src={`/skillpact/badges/skillpact-${l}.svg`} alt={`SkillPact ${l}`} height={20} className="h-5 w-auto" />
                <p className="mt-2 text-[0.8125rem] text-muted-foreground">{label[l][ja ? 1 : 0]}</p>
              </div>
              <pre tabIndex={0} className="min-w-0 overflow-x-auto rounded-md border bg-muted/50 px-3 py-2.5 font-mono text-[0.75rem] leading-relaxed"><code>{md}</code></pre>
            </li>
          );
        })}
      </ul>
    </Layout>
  );
}
