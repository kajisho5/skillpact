# Badges

Show your skill's SkillPact level. Static SVGs served from this site. Use the badge for the level your skill actually reaches with `skillpact conformance` (or the GitHub Action). A badge is a claim, not proof: readers can re-check with the [checker](../check/) or the Action. Rules: [TRADEMARKS.md](https://github.com/kajisho5/skillpact/blob/main/TRADEMARKS.md).

[![SkillPact L1](skillpact-L1.svg)](../) [![SkillPact L2](skillpact-L2.svg)](../) [![SkillPact L3](skillpact-L3.svg)](../)

## Markdown
```
[![SkillPact L3](https://kajisho5.github.io/skillpact/badges/skillpact-L3.svg)](https://kajisho5.github.io/skillpact/)
```
Replace `L3` with `L1` or `L2` as needed.

## Keep it honest in CI
```yaml
- uses: kajisho5/skillpact@<commit-sha>   # pin to a full commit SHA
  with: { path: ., min-level: L2 }
```

## Levels
- **L1**: the contract is valid.
- **L2**: plus the conformance tests pass in the sandbox (no network).
- **L3**: plus every file is covered by integrity and signed by an author you trust. L3 does not mean "safe".
