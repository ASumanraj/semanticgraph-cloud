# T-600 · Split infra into Network, Database and Compute stacks

**Stage** 6 · **Type** work · **Status** open · **Owner** — · **Branch** `t-600-split-infra-stacks`

**Scope**
- `infra/**`

**Blocked by** — · **Blocks** —

## Goal
`infra/` is an unedited CDK template: one default-named `InfraStack`, one
`db.t3.micro`, `RemovalPolicy.DESTROY`, `deletion_protection=False`, and `env=`
commented out. `docs/planning/ticket-infra-design.md` already specifies the
three-stack split and how to avoid the deadly embrace — it is the one pre-research
ticket that survived the architecture change.

Rename off `InfraStack` **before anything is deployed for real**: construct-id
changes are replacements.

Runs in parallel with everything else — `infra/**` is disjoint from every other scope.

## Acceptance
- [ ] `NetworkStack`, `DatabaseStack` and `ComputeStack`, with a one-way dependency flow
- [ ] `env=` set explicitly in `app.py`
- [ ] Per-environment config: `RETAIN` and `deletion_protection=True` outside dev, Multi-AZ, PITR
- [ ] Secrets Manager for database and model-provider credentials
- [ ] S3 with per-tenant key prefixes
- [ ] `cdk synth` emits the three stacks; `cdk diff` against dev is clean
- [ ] The app deploys as a whole unit into a fresh account, depending on no resource in ours

## Notes
That last criterion is nearly free now and is the difference between six months and
eighteen when a regulated buyer demands BYOC. Use the `aws-cdk` skill.
