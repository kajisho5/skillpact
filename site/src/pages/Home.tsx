import example from "@repo/docs/check/example.json";
import { latest, latestPolicy, type Lang } from "@/content";
import { Layout } from "@/components/Layout";
import { href, nav, REPO } from "@/i18n";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const C = {
  en: {
    title: "Contracts for Agent Skills",
    lead: <>SkillPact is a small open standard for a <code className="kbd">skill.contract.json</code> that sits next to an unchanged <code className="kbd">SKILL.md</code>. The author declares every side effect, ships tests that run without network, and signs the files. Harnesses read it <em className="not-italic font-medium text-foreground">before install</em>.</>,
    desc: "SkillPact: an open standard for machine-checkable contracts next to SKILL.md. Declare effects, test offline, sign, and check before install.",
    read: "Read the specification", why: "Why it exists",
    status: [["Status", `Working draft ${latest}. Not yet 1.0; breaking changes are possible.`], ["Contract schema", `v${latest}.json`], ["Policy schema", `policy-v${latestPolicy}.json`], ["Editor", "Shogo Kajiyama (SEVENTHWELL)"], ["License", "Text CC BY 4.0 · code Apache-2.0"]],
    exCap: "Excerpt of a real contract (thumbnail-skill, L3); “why” fields omitted. The six effect classes are always present; “none” is a statement, not an omission.",
    effects: "Six effect classes", effectsLead: "Every tool in a skill declares what it may do, in these six classes, each with a level (none, scoped, any) and a scope.",
    eff: [["read", "Read files or data", "path glob"], ["write", "Create, change, delete", "path glob, remote:<host>/<path>"], ["network", "Talk to other hosts", "host glob, @local"], ["exec", "Run other programs", "command name"], ["spend", "Cost money", "service name"], ["send", "Reach a person (message, post, mail)", "recipient kind / service name"]],
    effHead: ["Class", "Meaning", "Scope syntax"],
    levels: "Three levels", levelsLead: "A level is a statement about evidence, not about safety. L3 means the files are the ones the author signed; it does not mean the skill is harmless.",
    lvHead: ["Level", "Requires", "Tells you"],
    lv: [["L1", "Declared", "A schema-valid contract", "What the author says it does"], ["L2", "Tested", "L1 + conformance tests pass with network isolated", "The declaration was exercised"], ["L3", "Signed", "L2 + file hashes and a trusted ed25519 or Sigstore signature", "Who vouches, and that nothing changed since"]],
    where: "Where it sits", whereText: "SkillPact covers the moment before install: a harness reads the contract, compares it with your policy and decides allow, ask or deny. The same policy compiles to Claude Code, Cursor, Codex and Gemini CLI permission settings. Enforcement while the skill runs is left to runtime systems such as APS, ACS and HushSpec; an export to HushSpec and Rego is provided.",
    cli: "From the command line",
    docs: "Documents",
  },
  ja: {
    title: "エージェントスキルのための契約",
    lead: <>SkillPact は、変更しない <code className="kbd">SKILL.md</code> の横に置く <code className="kbd">skill.contract.json</code> の小さなオープン規格です。作者は副作用をすべて宣言し、ネットを切って動くテストを付け、ファイルに署名します。ハーネスは<em className="not-italic font-medium text-foreground">インストールの前に</em>それを読みます。</>,
    desc: "SkillPact：SKILL.md の横に置く、機械で確かめられる契約のオープン規格。副作用の宣言、オフラインのテスト、署名を、インストール前に確認します。",
    read: "仕様を読む", why: "なぜ必要か",
    status: [["状態", `草案 ${latest}。1.0 前のため、互換性のない変更があり得ます。`], ["契約スキーマ", `v${latest}.json`], ["ポリシースキーマ", `policy-v${latestPolicy}.json`], ["編集者", "Shogo Kajiyama（SEVENTHWELL）"], ["ライセンス", "本文 CC BY 4.0 · コード Apache-2.0"]],
    exCap: "実際の契約の抜粋（thumbnail-skill、L3。why は省略）。6種類の副作用は必ずすべて書きます。「none」は書き忘れではなく「しない」という宣言です。",
    effects: "6種類の副作用", effectsLead: "スキルの各ツールが何をし得るかを、この6種類で、レベル（none・scoped・any）と範囲を付けて宣言します。",
    eff: [["read", "ファイルやデータを読む", "パスの glob"], ["write", "作る・変える・消す", "パスの glob、remote:<host>/<path>"], ["network", "他のホストと通信する", "ホストの glob、@local"], ["exec", "他のプログラムを動かす", "コマンド名"], ["spend", "お金を使う", "サービス名"], ["send", "人に届く（メッセージ、投稿、メール）", "宛先の種類・サービス名"]],
    effHead: ["種類", "意味", "scope の書き方"],
    levels: "3つのレベル", levelsLead: "レベルは「どこまで確かめたか」を表すもので、安全の保証ではありません。L3 は作者が署名したファイルのままだという意味で、無害だという意味ではありません。",
    lvHead: ["レベル", "条件", "分かること"],
    lv: [["L1", "宣言済み", "スキーマに合った契約がある", "作者が何をすると言っているか"], ["L2", "テスト済み", "L1 に加え、ネットを切った適合テストに合格", "宣言が実際に試されたこと"], ["L3", "署名済み", "L2 に加え、ファイルのハッシュと、信頼できる ed25519 または Sigstore の署名", "誰が保証し、その後変わっていないこと"]],
    where: "受け持つ範囲", whereText: "SkillPact が受け持つのはインストールの前です。ハーネスが契約を読み、利用者のポリシーと照らし合わせて、許可・確認・拒否を決めます。同じポリシーから Claude Code、Cursor、Codex、Gemini CLI の権限設定を生成できます。実行中の強制は APS、ACS、HushSpec などの仕組みに任せ、HushSpec と Rego への書き出しを用意しています。",
    cli: "コマンドラインから",
    docs: "文書",
  },
};
const docDesc: Record<string, { en: string; ja: string }> = {
  spec: { en: "The normative text: MUST, SHOULD, MAY.", ja: "規定の本文。MUST・SHOULD・MAY で書かれています。" },
  why: { en: "The problem, who benefits, what it does not guarantee.", ja: "解決する問題、得をする人、保証しないこと。" },
  guides: { en: "Adopting SkillPact as an author, harness or organisation.", ja: "作者・ハーネス・組織それぞれの導入手順。" },
  schema: { en: "Every field, type and allowed value; JSON Schema files.", ja: "すべての項目・型・値と、JSON Schema のファイル。" },
  check: { en: "Check a contract in your browser. Nothing is uploaded.", ja: "ブラウザの中で契約を確認。何も送信しません。" },
  badges: { en: "L1, L2 and L3 badges for a README.", ja: "README に貼る L1・L2・L3 のバッジ。" },
  rationale: { en: "Why each design decision was made.", ja: "一つひとつの設計判断の理由。" },
  about: { en: "Governance, licensing, citation and contact.", ja: "運営、ライセンス、引用、連絡先。" },
};

function Section({ id, title, lead, children }: { id: string; title: string; lead?: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-x-16 gap-y-5 border-t py-12 sm:py-14 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <div><h2 id={id} className="text-lg font-semibold tracking-tight">{title}</h2>{lead && <p className="mt-2 text-[0.9rem] leading-relaxed text-muted-foreground">{lead}</p>}</div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

export default function Home({ lang }: { lang: Lang }) {
  const c = C[lang]; const e = example as any;
  const perms = Object.entries<any>(e.permissions);
  const w = Math.max(...perms.map(([k]) => k.length));
  const line = ([k, v]: [string, any]) => `    ${JSON.stringify(k)}:${" ".repeat(w - k.length + 1)}{ "level": ${JSON.stringify(v.level)}${v.scope ? `, "scope": ${JSON.stringify(v.scope).replace(/,/g, ", ")}` : ""} }`;
  const json = `{
  "contract_version": ${JSON.stringify(e.contract_version)},
  "skill": { "name": ${JSON.stringify(e.skill.name)}, "version": ${JSON.stringify(e.skill.version)} },
  "permissions": {
${perms.map(line).join(",\n")}
  },
  "capabilities": [ … ${e.capabilities.length} tools … ],
  "tests": { … },
  "integrity": { … }
}`;
  return (
    <Layout lang={lang} slug="" title={c.title} description={c.desc}>
      <div className="grid gap-x-16 gap-y-10 pb-14 pt-12 sm:pt-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]">
        <div className="max-w-[40rem]">
          <h1 className="text-[2rem] font-semibold leading-[1.15] tracking-[-0.02em] sm:text-[2.75rem]">{c.title}</h1>
          <p className="mt-5 text-[1.0625rem] leading-[1.75] text-foreground/75">{c.lead}</p>
          <p className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-[0.9375rem] font-medium">
            <a className="border-b-2 border-foreground pb-0.5 hover:border-ink hover:text-ink" href={href(lang, "spec")}>{c.read} →</a>
            <a className="border-b border-border pb-0.5 text-muted-foreground hover:text-foreground" href={href(lang, "why")}>{c.why}</a>
            <a className="border-b border-border pb-0.5 text-muted-foreground hover:text-foreground" href={href(lang, "check")}>{nav.find((n) => n.slug === "check")![lang]}</a>
          </p>
          <dl className="mt-10 grid grid-cols-[7.5rem_1fr] gap-x-4 gap-y-2 border-t pt-5 text-[0.84rem] sm:grid-cols-[9rem_1fr]">
            {c.status.map(([k, v]) => (
              <div key={k} className="contents"><dt className="text-muted-foreground">{k}</dt>
                <dd>{v.endsWith(".json") ? <a className="kbd text-ink underline-offset-4 hover:underline" href={`/skillpact/schema/${v}`}>{v}</a> : v}</dd></div>
            ))}
          </dl>
        </div>
        <figure className="min-w-0 self-start">
          <div className="overflow-hidden rounded-md border bg-muted/50">
            <div className="flex items-center justify-between border-b px-4 py-2"><span className="kbd text-muted-foreground">skill.contract.json</span><span className="kbd text-muted-foreground">L3</span></div>
            <pre tabIndex={0} className="overflow-x-auto px-4 py-3 font-mono text-[0.75rem] leading-[1.65] sm:text-[0.78rem]"><code>{json}</code></pre>
          </div>
          <figcaption className="mt-3 text-[0.8125rem] leading-relaxed text-muted-foreground">{c.exCap}</figcaption>
        </figure>
      </div>

      <Section id="effects" title={c.effects} lead={c.effectsLead}>
        <Table><TableHeader><TableRow>{c.effHead.map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>{c.eff.map(([k, m, s]) => <TableRow key={k}><TableCell className="kbd font-medium text-ink">{k}</TableCell><TableCell>{m}</TableCell><TableCell className="kbd text-muted-foreground">{s}</TableCell></TableRow>)}</TableBody></Table>
      </Section>

      <Section id="levels" title={c.levels} lead={c.levelsLead}>
        <div aria-hidden className="hidden grid-cols-[3rem_9rem_1fr_1fr] gap-x-4 pb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground sm:grid"><span /><span /><span>{c.lvHead[1]}</span><span>{c.lvHead[2]}</span></div>
        <ol className="divide-y border-y">
          {c.lv.map(([l, n, r, t]) => (
            <li key={l} className="grid grid-cols-[3rem_1fr] gap-x-4 py-4 sm:grid-cols-[3rem_9rem_1fr_1fr]">
              <span className="kbd pt-0.5 font-medium">{l}</span>
              <span className="font-medium">{n}</span>
              <span className="col-start-2 text-[0.9rem] text-foreground/80 sm:col-start-auto">{r}</span>
              <span className="col-start-2 text-[0.9rem] text-muted-foreground sm:col-start-auto">{t}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="where" title={c.where}>
        <p className="max-w-[44rem] leading-[1.8] text-foreground/85">{c.whereText}</p>
        <figure className="mt-6 max-w-[44rem]">
          <figcaption className="kbd mb-2 text-muted-foreground">{c.cli}</figcaption>
          <pre tabIndex={0} className="overflow-x-auto rounded-md border bg-muted/50 px-4 py-3 font-mono text-[0.78rem] leading-[1.8]"><code>{`$ skillpact conformance ./my-skill
$ skillpact policy-compile ./my-skill policy.json --target claude-code
$ skillpact convert ./my-skill --to mda`}</code></pre>
        </figure>
      </Section>

      <Section id="documents" title={c.docs}>
        <ul className="divide-y border-y">
          {nav.map((n) => (
            <li key={n.slug}>
              <a href={href(lang, n.slug)} className="group grid gap-1 py-3.5 sm:grid-cols-[11rem_1fr] sm:gap-6">
                <span className="font-medium group-hover:text-ink">{n[lang]}</span>
                <span className="text-[0.9rem] text-muted-foreground">{docDesc[n.slug]?.[lang]}</span>
              </a>
            </li>
          ))}
          <li><a href={REPO} className="group grid gap-1 py-3.5 sm:grid-cols-[11rem_1fr] sm:gap-6"><span className="font-medium group-hover:text-ink">GitHub</span><span className="text-[0.9rem] text-muted-foreground">kajisho5/skillpact</span></a></li>
        </ul>
      </Section>
    </Layout>
  );
}
