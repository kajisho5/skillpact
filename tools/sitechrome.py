#!/usr/bin/env python3
"""Site chrome for docs/ (stdlib only). Run from repo root: python3 tools/sitechrome.py
- unified header (Home / Schema / Checker / Badges / GitHub + EN/日本語 switch) on every page
- latest contract / policy schema cards on the top pages
- Japanese pages under docs/ja/ (top, schema intro, checker)"""
import pathlib, re, json
ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GH = "https://github.com/kajisho5/skillpact"
LINKS = [("home", "", "Home", "ホーム"), ("schema", "schema/", "Schema", "スキーマ"), ("check", "check/", "Checker", "チェッカー"), ("badges", "badges/", "Badges", "バッジ")]
HAS_JA = {"home", "schema", "check"}


def _v(p): return tuple(map(int, p.split(".")))
def latest(prefix):
    vs = [q.stem[len(prefix):] for q in (DOCS / "schema").glob(f"{prefix}*.json") if re.fullmatch(r"\d+\.\d+", q.stem[len(prefix):])]
    return max(vs, key=_v)
VER, PVER = latest("v"), latest("policy-v")


def header(rel: str, lang: str, active: str) -> str:
    """rel = path prefix from the page to the site root for this language ('' / '../' ...)."""
    root = rel if lang == "en" else rel + "../"   # site root (EN)
    base = rel                                   # language root
    def link(k, href):
        pre = base if (lang == "en" or k in HAS_JA) else root
        return (pre + href) or "./"
    nav = "".join(f'<a href="{link(k, href)}"' + (' aria-current="page"' if k == active else "") + f'>{en if lang == "en" else ja}</a>' for k, href, en, ja in LINKS)
    nav += f'<a href="{GH}">GitHub</a>'
    here = dict((k, h) for k, h, *_ in LINKS).get(active, "")
    if lang == "en":
        sw = f'<a class="lang" href="{root}ja/{here if active in HAS_JA else ""}" lang="ja" hreflang="ja">日本語</a>'
    else:
        sw = f'<a class="lang" href="{root}{here}" lang="en" hreflang="en">EN</a>'
    return (f'<header class="top"><div class="wrap nav"><a class="brand" href="{base or "./"}"><span class="logo">◆</span> SkillPact <small>by SEVENTHWELL</small></a>'
            f'<nav aria-label="Main">{nav}{sw}</nav></div></header>')


def page_kind(p: pathlib.Path):
    rel = p.relative_to(DOCS).parts
    lang = "ja" if rel[0] == "ja" else "en"
    parts = rel[1:] if lang == "ja" else rel
    active = {"schema": "schema", "check": "check", "badges": "badges"}.get(parts[0] if len(parts) > 1 else "", "home")
    return lang, "../" * (len(parts) - 1), active


REVIEW = {"start": "TBD", "end": "TBD"}  # set both (YYYY-MM-DD) on announcement day; see REVIEW.md


def banner(lang: str) -> str:
    if REVIEW["start"] == "TBD": return ""  # hidden until a start date exists
    url = f"{GH}/blob/main/REVIEW.md"
    if lang == "ja":
        t = f'<b>公開レビュー中（v0.7）</b> 期間：{REVIEW["start"]} 〜 {REVIEW["end"]}（30日間）。ご意見は <a href="{url}">REVIEW.md</a> の手順でお寄せください。'
    else:
        t = f'<b>Public review of v0.7</b> · {REVIEW["start"]} – {REVIEW["end"]} (30 days). Feedback welcome: see <a href="{url}">REVIEW.md</a>.'
    return f'<div class="review-banner"><div class="wrap">{t}</div></div>'


def apply_header(html: str, lang: str, rel: str, active: str) -> str:
    html = re.sub(r'\n?<div class="review-banner">.*?</div></div>', "", html, flags=re.S)
    return re.sub(r'<header class="top">.*?</header>', lambda m: header(rel, lang, active) + ("\n" + banner(lang) if banner(lang) else ""), html, count=1, flags=re.S)


CARDS_EN = f'''<a class="card" href="schema/"><h3>Schema reference</h3><span>Every field, type and allowed value, with real examples.</span></a>
<a class="card" href="schema/v{VER}.json"><h3>v{VER}.json</h3><span>Contract JSON Schema (latest)</span></a>
<a class="card" href="schema/policy-v{PVER}.json"><h3>policy-v{PVER}.json</h3><span>Harness policy JSON Schema (latest)</span></a>
<a class="card" href="check/"><h3>Checker</h3><span>Check a contract in your browser — nothing is uploaded.</span></a>
<a class="card" href="badges/"><h3>Badges</h3><span>L1 / L2 / L3 badges for your README.</span></a>'''


def top_en():
    p = DOCS / "index.html"; h = p.read_text()
    h = re.sub(r'draft v[\d.]+</p>', f'draft v{VER}</p>', h)
    h = re.sub(r'(<section><h2>Specs &amp; schemas</h2><div class="grid3">).*?(</div></section>)', lambda m: m.group(1) + "\n" + CARDS_EN + m.group(2), h, flags=re.S)
    p.write_text(h)


HEAD = lambda title, desc, rel, canon: f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="https://kajisho5.github.io/skillpact/{canon}"><link rel="alternate" hreflang="en" href="https://kajisho5.github.io/skillpact/{canon.replace("ja/", "", 1)}">
<link rel="stylesheet" href="{rel}../assets/site.css"></head><body>
<header class="top"></header>'''
FOOT = '<footer class="wrap foot">仕様 CC BY 4.0 · コード Apache-2.0 · © 2026 SEVENTHWELL</footer></body></html>\n'


def ja_pages():
    (DOCS / "ja" / "schema").mkdir(parents=True, exist_ok=True); (DOCS / "ja" / "check").mkdir(parents=True, exist_ok=True)
    top = HEAD("SkillPact — Agent Skills のための契約 · SEVENTHWELL", "Agent Skill が何をするかを宣言・テスト・署名し、インストール前に確かめる。", "", "ja/") + f'''
<main class="wrap">
<section class="hero"><p class="eyebrow">オープンな規格 · ドラフト v{VER}</p><h1>Agent Skills のための<br>機械が読める契約</h1>
<p class="lead">変更しない <code>SKILL.md</code> の隣に <code>skill.contract.json</code> を置きます。作者はすべての副作用を<b>宣言</b>し、ネットを切って動く<b>テスト</b>を付け、<b>署名</b>します。ハーネスはそれを<em>インストール前に</em>確かめます。</p>
<p><a class="btn" href="schema/">スキーマの説明 →</a> <a class="btn ghost" href="check/">ブラウザで確認</a></p></section>
<section><h2>6 種類の副作用</h2><div class="effs">
<div class="eff e-read"><b>read</b><span>ファイルやデータを読む</span></div><div class="eff e-write"><b>write</b><span>ファイルを作る・変える</span></div>
<div class="eff e-network"><b>network</b><span>外部と通信する（<code>@local</code> は手元・社内網だけ）</span></div><div class="eff e-exec"><b>exec</b><span>他のプログラムを動かす</span></div>
<div class="eff e-spend"><b>spend</b><span>お金を使う</span></div><div class="eff e-send"><b>send</b><span>人にメッセージを送る</span></div></div></section>
<section><h2>3 つのレベル</h2><div class="levels">
<div class="lv"><span class="badge l1">L1</span><b>宣言済み</b><p>契約が正しい形をしている。</p></div>
<div class="lv"><span class="badge l2">L2</span><b>テスト済み</b><p>適合テストがネットを切った状態で通る。</p></div>
<div class="lv"><span class="badge l3">L3</span><b>署名済み</b><p>ハッシュと、信頼できる作者の署名（ed25519 か Sigstore）。</p></div></div></section>
<section><h2>1 つのルールを、すべてのハーネスに</h2><p>ハーネスのポリシーが副作用ごとに <span class="badge allow">許可</span><span class="badge ask">確認</span><span class="badge deny">拒否</span> を決め、Claude Code・Cursor・Codex・Gemini CLI の設定に変換します。実行中の強制は APS・ACS・HushSpec に任せます（書き出しに対応）。</p>
<pre><code>skillpact conformance ./my-skill
skillpact policy-compile ./my-skill policy.json --target claude-code
skillpact convert ./my-skill --to mda</code></pre></section>
<section><h2>仕様とスキーマ</h2><div class="grid3">
<a class="card" href="schema/"><h3>スキーマの説明</h3><span>契約ファイルの構成と読み方。</span></a>
<a class="card" href="../schema/v{VER}.json"><h3>v{VER}.json</h3><span>契約の JSON Schema（最新）</span></a>
<a class="card" href="../schema/policy-v{PVER}.json"><h3>policy-v{PVER}.json</h3><span>ハーネスポリシーの JSON Schema（最新）</span></a>
<a class="card" href="check/"><h3>チェッカー</h3><span>ブラウザの中だけで契約を確認（送信なし）</span></a>
<a class="card" href="../badges/"><h3>バッジ</h3><span>README 用の L1 / L2 / L3 バッジ</span></a></div></section>
</main>''' + FOOT
    (DOCS / "ja" / "index.html").write_text(top)
    sch = HEAD(f"スキーマの説明 v{VER} — SkillPact", "skill.contract.json とハーネスポリシーの構成。", "../", "ja/schema/") + f'''
<main class="wrap"><section class="hero sm"><p class="eyebrow">スキーマ · ドラフト v{VER}</p><h1>skill.contract.json とハーネスポリシー</h1>
<p class="lead">契約ファイルは <code>SKILL.md</code> と同じフォルダに置く JSON です。全項目の型・必須・取りうる値は<a href="../../schema/">英語版の項目別リファレンス</a>にあります。ここでは全体の形だけを説明します。</p>
<div class="pills"><a class="pill" href="../../schema/v{VER}.json">v{VER}.json <small>契約</small></a><a class="pill" href="../../schema/policy-v{PVER}.json">policy-v{PVER}.json <small>ポリシー</small></a></div></section>
<section><h2>契約の主な項目</h2><table class="ft"><thead><tr><th>項目</th><th>内容</th></tr></thead><tbody>
<tr><td><code class="f">contract_version</code></td><td>仕様の版（最新は <code>"{VER}"</code>）。知らない版は拒否されます。</td></tr>
<tr><td><code class="f">skill</code></td><td>スキルの名前と版。名前は <code>SKILL.md</code> の name、およびフォルダ名と同じにします。</td></tr>
<tr><td><code class="f">permissions</code></td><td>6 種類の副作用それぞれの上限（none / scoped / any）と範囲。</td></tr>
<tr><td><code class="f">capabilities</code></td><td>ツール・コマンドごとの副作用、入口、入出力のスキーマ。</td></tr>
<tr><td><code class="f">requirements</code></td><td>必要なプログラム、ランタイム、パッケージ、他のスキル、環境変数（値は書かない）。</td></tr>
<tr><td><code class="f">tests</code></td><td>ネットを切って動く適合テスト。全部通れば L2。</td></tr>
<tr><td><code class="f">integrity</code></td><td>ファイルのハッシュと署名。信頼できる作者（author）の署名があれば L3。レビュアーの署名は証明として別に報告されます。</td></tr>
<tr><td><code class="f">x</code></td><td>拡張用（<code>x.&lt;ベンダー名&gt;</code>）。検証者は中身を無視して進めます。</td></tr>
</tbody></table></section>
<section><h2>署名の対象</h2><p>v0.4 以降は、<code>integrity.signatures</code> を除いた契約全体を RFC 8785（JCS）で正規化したバイト列に署名します。</p></section>
</main>''' + FOOT
    (DOCS / "ja" / "schema" / "index.html").write_text(sch)
    en = (DOCS / "check" / "index.html").read_text()
    body = en[en.index("<main"):]
    rep = [("Checker · runs in your browser", "チェッカー · ブラウザの中だけで動きます"), ("Check a skill.contract.json", "skill.contract.json を確認する"),
           (re.search(r'<p class="lead">.*?</p>', body, re.S).group(0), '<p class="lead">契約を貼り付けてください。スキーマの検証、相互チェック、注意が要る副作用、ed25519 署名を<b>このページの中だけ</b>で確かめます（TypeScript 実装をブラウザ用にしたもの）。入力はどこにも送られません。ページの設定で、このサイトのファイル（見本など）を読む以外の通信を禁じています。</p>'),
           ("Contract JSON", "契約の JSON"), ("Trusted keys (one per line, optional)", "信頼する鍵（1 行に 1 つ、任意）"),
           (">Check</button>", ">確認する</button>"), (re.search(r'>Load example[^<]*</button>', body).group(0), ">見本を読み込む（thumbnail-skill、署名あり）</button>"),
           (re.search(r'<p><small>Not checked here.*?</small></p>', body, re.S).group(0), '<p><small>ここでは確認しないもの：<code>integrity.files</code> の各ファイル（ページには契約しか渡らないため）、適合テスト（L2）、Sigstore の署名。正式なレベルは <code>skillpact conformance &lt;dir&gt;</code> か GitHub Action で確かめてください。</small></p>'),
           ('src="skillpact-check.js"', 'src="../../check/skillpact-check.js"'), ('src="check-ui.js"', 'src="../../check/check-ui.js"')]
    for a, b in rep: body = body.replace(a, b)
    head = en[:en.index("<body>")].replace('<html lang="en">', '<html lang="ja">').replace('href="../assets/site.css"', 'href="../../assets/site.css"').replace("<title>Checker — SkillPact", "<title>チェッカー — SkillPact")
    (DOCS / "ja" / "check" / "index.html").write_text(head + '<body>\n<header class="top"></header>\n' + body)


def main():
    top_en(); ja_pages()
    for p in sorted(DOCS.rglob("*.html")):
        lang, rel, active = page_kind(p); h = p.read_text()
        p.write_text(apply_header(h, lang, rel, active))
    print(f"site: header applied, latest v{VER} / policy-v{PVER}")


if __name__ == "__main__": main()
