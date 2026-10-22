# Composition: risks of skills used together

Each contract describes one skill. But you rarely install just one. All your skills run inside the same agent, and the agent can carry what one skill read into another skill. Sandboxing each skill does not stop that.

## Example
- Skill A reads `~/.aws/credentials` to deploy.
- Skill B posts to `api.example.com`.

Each looks reasonable alone. Together they form an **exfiltration path**: the agent can read with A and send with B.

## What SkillPact checks (spec §13.3)
| Path | When | Severity |
|---|---|---|
| exfiltration | sensitive or broad read + network other than `@local`, or send | high |
| persistence | write outside `$WORKDIR`/`$OUTPUT` + exec | medium |
| spend_untrusted | spend + any skill without a trusted author signature | high |

```sh
skillpact compose skills/a skills/b skills/c
```
The output lists the union of effects, every path found, which skills play which role, whether the path crosses skills, and a fix hint.

## Policy
```json
{ "policy_version": "0.8", "defaults": { "...": "..." },
  "compositions": { "exfiltration": "deny", "persistence": "ask", "spend_untrusted": "ask" } }
```
`policy-check a b c policy.json` keeps each skill's own decision and adds one decision per path. Without `compositions`, results are the same as before.

`policy-compile a b c policy.json --target claude-code` cannot write "deny only when installed together" in harness settings. It compiles the contributing effects as **ask** and lists the path under `lossy`.

## Limits
- This is a check over declarations. It cannot see what a skill really does.
- Lists of sensitive paths are incomplete by nature. Narrow scopes are the real fix.
- Skills you add later change the set. Run the check again whenever the set changes.
