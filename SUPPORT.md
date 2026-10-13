# Support and governance

## Getting help

- **Questions and bug reports:** open a
  [GitHub issue](https://github.com/badass-data-science/omen-agentic-time-series-forecasting/issues).
  See [CONTRIBUTING.md](CONTRIBUTING.md) for what to include.
- **Learning to use Omen:** start with the README's Quick Start. Each
  layer's `SKILL.md` in `src/omen/skills/` describes its tools and how an
  agent should sequence them, and the companion book in `book/` works
  through complete examples.
- **Security issues:** please don't file these as public issues. Email
  the maintainer at the address listed in `pyproject.toml` instead.

## What to expect

Omen is maintained by one person on a best-effort basis, with no paid
support. The aim is to:

- acknowledge new issues and pull requests within about two weeks,
- prioritize bugs that produce wrong statistical results or break a tool
  for an MCP client over feature requests,
- fix bugs in the latest release only. Older versions are not patched.

Omen is in **alpha** (version 0.x). Tool names, parameters, and output
fields may still change between minor versions. Every change that affects
users is recorded in [CHANGELOG.md](CHANGELOG.md), and renamed or
reshaped output fields are called out explicitly.

## Governance

Omen is currently run under a single-maintainer model. The maintainer,
Emily Marie Williams ([@badass-data-science](https://github.com/badass-data-science)),
reviews and merges pull requests, decides on the project's direction, and
publishes releases to PyPI.

Design decisions are made in the open: substantial changes are discussed
in GitHub issues and pull requests before they are merged, and the
project's conventions, with the reasoning behind each, are recorded in
`AGENTS.md`. Some principles are treated as fixed unless there is a strong
argument to revisit them:

- decision tools (retraining recommendations, candidate-vs-deployed
  comparisons) stay deterministic and rule-based,
- redeploying a model always requires explicit confirmation, and
  autonomous mode requires a stored authorization record checked in code.

Regular contributors may be invited to become co-maintainers. If that
happens, this document will be updated to describe how decisions are
shared.
