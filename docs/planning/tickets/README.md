# Tickets

A ticket is one slice of work an agent can finish alone, on its own branch, without
touching anything another agent is holding.

`INDEX.md` is the board. `ENTERPRISE_PLAN.md` is still the architecture and the
stage ordering; tickets are how a stage gets split so several agents can run at once.

## Scope is the lock

Every ticket declares a **Scope**: the paths it may write. That is the whole
concurrency mechanism.

> **Two tickets may run in parallel exactly when their Scopes are disjoint.**

Stay inside your Scope. A change you believe belongs elsewhere is a new ticket, not
a quiet edit — the other agent holding that path is mid-slice and will lose it in a
merge.

Some work cannot be split. Anything that adds an Alembic revision shares one
migration chain, so those tickets run **one at a time**, in the order `Blocked by`
gives. Two agents generating revisions concurrently produce two heads and a chain
that has to be rebuilt by hand.

## Claiming

Claiming is a commit, so git arbitrates the race:

1. `git pull`
2. Edit the ticket header: `Status: claimed`, `Owner: <your name>`
3. Commit **only that file**: `git commit -m "claim: T-101"` and push

If the push is rejected, someone claimed first. Pull, pick another ticket.

Then branch and work:

```bash
git switch -c t-101-compose-runs-real-services
```

## Finishing

1. Tests pass, `ruff check .` clean, and the ticket's Acceptance boxes are all ticked
2. Open a PR to `main` — that is where review happens, and review is the gate that
   catches a test which passes without testing anything
3. On merge: `Status: done`, and tick the matching line in the plan's progress tracker

## Writing a ticket

Keep Acceptance checkable by someone who was not in the conversation. "Works
correctly" is not checkable; "a query with no tenant context returns zero rows from
every table" is.

```markdown
# T-000 · Short imperative title

**Stage** 1 · **Type** work · **Status** open · **Owner** — · **Branch** `t-000-slug`

**Scope**
- `path/that/this/ticket/owns/**`

**Blocked by** — · **Blocks** —

## Goal
One or two sentences: what changes and why it matters.

## Acceptance
- [ ] Something a reviewer can verify
- [ ] Something a reviewer can verify

## Notes
Links into ENTERPRISE_PLAN.md, an ADR, or a file:line worth reading first.
```

`Type: research` tickets answer a question instead of changing code. They carry a
`## Question` and a `## Resolution` rather than Acceptance, and their Scope is
`docs/**`. That is the older wayfinder form, kept because a decision needs a written
reason more than it needs a diff.
