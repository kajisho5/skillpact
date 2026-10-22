# Accessibility of the SkillPact site

Target: WCAG 2.2 level AA for kajisho5.github.io/skillpact (self-assessed, not audited).

What the pages do:
- `lang` set on every page (`en` / `ja`) and `hreflang` links between translations;
- one `h1` per page, ordered headings, a table of contents on long pages;
- tables with header cells; code in `pre`/`code`;
- navigation in a labelled `nav`, current page marked with `aria-current`;
- the checker works with the keyboard, labels its inputs and runs offline;
- colour is never the only signal (badges carry text such as "L3", "allow", "deny").

Known gaps: no formal audit yet; badge SVGs have text but no long description. Report problems as a GitHub issue or to kajiyama@seventh-well.com.
