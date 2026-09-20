# T-901 · Confirm Temporal Cloud cost at projected volume

**Stage** — · **Type** research · **Status** open · **Owner** — · **Branch** `t-901-temporal-cloud-cost`

**Scope**
- `docs/research/**`
- `docs/adr/0003-temporal-for-the-document-pipeline.md`

**Blocked by** — · **Blocks** —

## Question
ADR-0003 chose Temporal Cloud on published pricing of $50/M actions falling to
$25/M at volume, with self-hosting only competitive around 30–50M actions/month for
a team already running Kubernetes and Cassandra. What does the bill actually look
like at this product's document volume, once actions are counted through the full
pipeline?

## Resolution
_Open._ Model actions per document across parse, chunk, contextualize, extract,
resolve and materialize — a per-chunk fan-out multiplies them — then price it at 1k,
10k and 100k documents per month. Record the numbers in the ADR's consequences
section, since the decision rests on them.
