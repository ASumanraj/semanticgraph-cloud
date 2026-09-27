# Reviewer reproduction, 2026-09-27. Not part of the product; kept as evidence for
# docs/research/evidence-first-temporal-contract-graph-prior-art.md.
#
# Question: does Graphiti.remove_episode delete an edge that another episode still asserts?
# Pinned: github.com/getzep/graphiti commit 47f648213da99aa96ec190c61dbb3e0d163e1250 (v0.30.2).
# Setup:  python 3.12 venv; pip install <graphiti checkout> "kuzu>=0.11.3" httpx
#         (embedded Kuzu, no LLM calls).
# Limits: the graph is built directly through Graphiti's own node/edge save methods, with
#         edge.episodes = [doc1, doc2]. It does not go through add_episode (which needs an
#         LLM), so it shows what remove_episode does to such an edge, not how often
#         add_episode produces one.
# Result: removing doc1 (first asserter) deleted the fact (1 -> 0) although doc2 still
#         asserts it; removing doc2 (second asserter) kept the fact (1 -> 1) and left the
#         deleted doc2's uuid in edge.episodes.
"""Reproduce: does Graphiti.remove_episode delete an edge that another episode still asserts?
Pinned: getzep/graphiti commit 47f648213da99aa96ec190c61dbb3e0d163e1250 (v0.30.2).
Embedded Kuzu, no LLM calls.
"""

import asyncio
import os
import tempfile
from datetime import UTC, datetime

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.driver.kuzu_driver import KuzuDriver
from graphiti_core.edges import EntityEdge, EpisodicEdge
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.llm_client import LLMClient, LLMConfig
from graphiti_core.nodes import EntityNode, EpisodeType, EpisodicNode


class Stub:
    pass


class E(EmbedderClient):
    async def create(self, input_data):
        return [0.0] * 1024

    async def create_batch(self, input_data_list):
        return [[0.0] * 1024 for _ in input_data_list]


class L(LLMClient):
    def __init__(self):
        super().__init__(LLMConfig(api_key="x", model="x"))

    async def _generate_response(self, *a, **k):
        raise RuntimeError("no LLM in repro")


class X(CrossEncoderClient):
    async def rank(self, query, passages):
        return [(p, 1.0) for p in passages]


async def count(drv, label):
    r, _, _ = await drv.execute_query("MATCH (e:RelatesToNode_) RETURN count(e) AS c")
    print(f"  {label}: facts (edge nodes) = {r[0]['c']}")


async def scenario(name, remove_first):
    path = os.path.join(tempfile.mkdtemp(prefix=f"kuzu_{name}_"), "graph.db")
    drv = KuzuDriver(db=path)
    g = Graphiti(graph_driver=drv, llm_client=L(), embedder=E(), cross_encoder=X())
    await g.build_indices_and_constraints()
    now = datetime.now(UTC)
    a = EntityNode(
        name="Acme", group_id="t1", summary="s", name_embedding=[0.0] * 1024, created_at=now
    )
    b = EntityNode(
        name="Beta", group_id="t1", summary="s", name_embedding=[0.0] * 1024, created_at=now
    )
    edge = EntityEdge(
        group_id="t1",
        source_node_uuid=a.uuid,
        target_node_uuid=b.uuid,
        created_at=now,
        name="ACQUIRED",
        fact="Acme acquired Beta",
        fact_embedding=[0.0] * 1024,
        episodes=[],
        valid_at=now,
    )
    eps = []
    for i in (1, 2):
        ep = EpisodicNode(
            name=f"doc{i}",
            group_id="t1",
            source=EpisodeType.text,
            source_description="doc",
            content="Acme acquired Beta",
            created_at=now,
            valid_at=now,
            entity_edges=[edge.uuid],
        )
        eps.append(ep)
    edge.episodes = [eps[0].uuid, eps[1].uuid]  # BOTH documents assert the same fact
    for n in (a, b):
        await n.save(drv)
    for ep in eps:
        await ep.save(drv)
    await edge.save(drv)
    for ep in eps:
        for n in (a, b):
            await EpisodicEdge(
                source_node_uuid=ep.uuid, target_node_uuid=n.uuid, group_id="t1", created_at=now
            ).save(drv)
    print(f"[{name}] fact asserted by doc1 AND doc2 (edge.episodes = [doc1, doc2])")
    await count(drv, "before")
    victim = eps[0] if remove_first else eps[1]
    print(
        f"  removing {victim.name} ({'first' if remove_first else 'second'} asserter); "
        "the other document still asserts the fact"
    )
    await g.remove_episode(victim.uuid)
    await count(drv, "after ")
    r, _, _ = await drv.execute_query("MATCH (e:RelatesToNode_) RETURN e.episodes AS eps")
    if r:
        print(f"  surviving edge.episodes = {r[0]['eps']}")
    await g.close()


async def main():
    await scenario("first", True)
    await scenario("second", False)


asyncio.run(main())
