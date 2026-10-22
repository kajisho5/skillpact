# Contributing to SkillPact
Thanks for helping. SkillPact is maintained by SEVENTHWELL (shogo kajiyama).

- **Spec changes** (`spec/`, schemas): open an issue first describing the problem, then a PR. Spec text is CC BY 4.0.
- **Code** (`ref/`): Apache-2.0. Run `cd ref && pip install -e .[test,sigstore] && pytest -q tests` before opening a PR; all tests must pass.
- **New harness targets / converters**: add the target's official schema under `ref/skillpact/harness_schemas/` and a test that validates the output against it.
- **Security issues**: do not open a public issue; e-mail kajiyama@seventh-well.com or use GitHub private vulnerability reporting (SECURITY.md).
- **Conduct**: CODE_OF_CONDUCT.md applies. Spec changes follow GOVERNANCE.md; tests: `cd ts && npm test` and `python3 conformance/run.py` on both implementations.
- Keep the 6 effect classes stable (read, write, network, exec, spend, send); vendor data goes under `x.<vendor>`.
- By contributing you agree your contribution is licensed under the file's license (DCO sign-off `git commit -s` appreciated).
