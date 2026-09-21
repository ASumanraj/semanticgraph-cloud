# T-213 · Make the CI isolation step fail when its tests fail

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-213-ci-isolation-step`

**Scope**
- `.github/workflows/ci.yml`

**Blocked by** — · **Blocks** —

## Goal

T-107 correctly made skipped isolation proofs fail. Reading the workflow turned up two
smaller problems, and one thing nobody has been able to check.

**The step can swallow a pytest failure.** It runs
`pytest … 2>&1 | tee /tmp/isolation_output.txt` and then greps for `SKIPPED`. As I understand
GitHub's default shell for a `run` step (`bash -e {0}`, with no `pipefail`), the step's exit
status is `tee`'s, not pytest's, so a *failing* isolation test would not fail the step. The
earlier `pytest -q` step runs the same tests and would catch it, which is why nothing is
broken today, but this step then guards nothing but skips. I have not been able to run it to
confirm.

**The Postgres service is probably unused.** The job defines a `postgres` service and sets
`DATABASE_URL`, but the shared fixture only reads `DATABASE_URL` when
`SEMANTICGRAPH_USE_COMPOSE_DB=1`; by default it starts its own container. So the service
container is idle.

**Nobody has seen CI run.** The repository's Actions page returns 404 to an unauthenticated
request, so its status could not be read, and `gh` is not installed. Every claim that CI is
green is currently unchecked.

## Acceptance

- [ ] The isolation step fails when any test in it fails — set `pipefail`, or write the output to a file without a pipe — shown by a run, not by argument
- [ ] The Postgres service is either used (`SEMANTICGRAPH_USE_COMPOSE_DB=1`) or removed, and the workflow says which and why
- [ ] The ticket links a **green run on `main`** that includes the isolation step, and a run where a deliberately skipped or failing isolation test turned the step red
- [ ] `ruff check .` clean

## Notes

Needs someone who can see the Actions tab. If the repository stays private, paste the run
URL into the ticket rather than leaving the acceptance boxes unchecked.
