# SpecKit feature specs

PlotPilot uses [GitHub Spec Kit](https://github.com/github/spec-kit) for
spec-driven development.

## Layout

Each feature has a directory:

```text
specs/NNN-short-name/
  spec.md
  plan.md
  tasks.md
  ...
```

Branch names follow the git extension convention: `NNN-short-name`.

## Workflow

1. `/speckit-specify` — create or update `spec.md` for the slice
2. `/speckit-plan` — technical plan
3. `/speckit-tasks` — actionable tasks
4. `/speckit-implement` — code changes
5. `/speckit-converge` — gap check until converged

Project principles live in [.specify/memory/constitution.md](../.specify/memory/constitution.md).

## Upcoming

- **001-svg-open** — open an SVG file (first product slice; not yet created)
