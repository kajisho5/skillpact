# SkillPact site (React + shadcn/ui, static)

Vite 7 + React 18 + TypeScript + Tailwind 3 + shadcn/ui primitives (new-york, stone), prerendered per route with vite-react-ssg.

- Content is single-source: `content/{en,ja}/*.md` (every file becomes `/<slug>/` and `/ja/<slug>/`), schema reference is generated from `docs/schema/*.json`, the checker reuses `docs/check/skillpact-check.js` (the ts/ implementation bundle). Override the repo path with `SKILLPACT_REPO=/path/to/skillpact`.
- `npm run build` → `dist/` (copies schema JSON / badge SVG / checker bundle byte-for-byte, prerenders 18 pages, externalises inline scripts so the checker CSP has no `unsafe-inline` for scripts, writes 404.html, sitemap.xml, robots.txt, .nojekyll).
- `npm run preview` serves `dist/` at http://localhost:4173/skillpact/ ; `node scripts/shots.mjs` screenshots, `node scripts/audit.mjs` runs axe (WCAG 2 AA) + link check.
- Fonts are self-hosted (IBM Plex Sans / Plex Sans JP / Plex Mono via @fontsource). Dark mode: `prefers-color-scheme`, toggle stored in localStorage (`/skillpact/theme.js`).

Deployed by `.github/workflows/pages.yml` (GitHub Actions Pages source). `docs/` holds only the canonical static artifacts (schema JSON, badge SVG, checker bundle + example) that the build copies byte-for-byte.
