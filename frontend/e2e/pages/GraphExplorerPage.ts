import { Page, Locator } from '@playwright/test';

export class GraphExplorerPage {
  readonly page: Page;
  readonly container: Locator;
  readonly canvas: Locator;
  readonly nodes: Locator;
  readonly edges: Locator;
  readonly emptyState: Locator;
  readonly propertiesPanel: Locator;
  readonly quoteElement: Locator;
  readonly chunkIdElement: Locator;
  readonly searchInput: Locator;
  readonly clearSearchButton: Locator;
  readonly errorState: Locator;
  readonly retryButton: Locator;
  readonly truncatedBanner: Locator;
  readonly truncatedCounter: Locator;
  readonly expandingIndicator: Locator;
  readonly expandError: Locator;

  constructor(page: Page) {
    this.page = page;
    this.container = page.locator('[data-testid="graph-explorer"]');
    this.canvas = page.locator('.react-flow');
    this.nodes = page.locator('.react-flow__node');
    this.edges = page.locator('.react-flow__edge');
    this.emptyState = page.getByText(/No graph yet/i);
    this.propertiesPanel = page.getByText('Properties');
    this.quoteElement = page.locator('blockquote');
    this.chunkIdElement = page.locator('text=Chunk ID');
    this.searchInput = page.getByPlaceholder('Search entities...');
    this.clearSearchButton = page.getByRole('button', { name: 'Clear search' });
    this.errorState = page.getByText("Couldn't load the graph");
    this.retryButton = page.getByRole('button', { name: 'Retry' });
    this.truncatedBanner = page.getByText('Showing the first 200 entities. Narrow your search to see more.');
    this.truncatedCounter = page.getByText('Showing 200 entities');
    this.expandingIndicator = page.getByTestId('expanding-indicator');
    this.expandError = page.getByTestId('expand-error');
  }

  async goto() {
    await this.page.goto('/dashboard/explorer');
  }

  async selectFirstNode() {
    const node = this.nodes.first();
    await node.scrollIntoViewIfNeeded();
    await node.click({ force: true });
  }

  async selectFirstEdge() {
    const edgeElement = this.page.locator('.react-flow__edge-text, .react-flow__edge path, .react-flow__edge').first();
    await edgeElement.dispatchEvent('click');
  }

  async selectNode(name: string) {
    const node = this.page.locator('.react-flow__node', { hasText: name }).first();
    await node.scrollIntoViewIfNeeded();
    await node.click({ force: true });
  }

  async hoverNode(name: string) {
    const node = this.page.locator('.react-flow__node', { hasText: name }).first();
    await node.scrollIntoViewIfNeeded();
    await node.hover({ force: true });
  }

  async doubleClickNode(name: string) {
    const node = this.page.locator('.react-flow__node', { hasText: name }).first();
    await node.scrollIntoViewIfNeeded();
    await node.dblclick({ force: true });
  }

  typeFilterChip(type: string): Locator {
    return this.page.getByTestId(`type-chip-${type}`);
  }

  noMatchHeading(query: string): Locator {
    return this.page.getByText(new RegExp(`No entities match .${query}.`, 'i'));
  }

  /**
   * Asserts that each edge path's endpoints lie within maxDistancePx of its
   * source and target node bounding boxes (not just that the edge element exists).
   */
  async assertEdgeEndpointsNearNodes(maxDistancePx = 40) {
    const check = await this.page.evaluate((maxDist) => {
      const edges = Array.from(document.querySelectorAll('.react-flow__edge'));
      const nodes = Array.from(document.querySelectorAll('.react-flow__node')) as HTMLElement[];

      function distToBox(px: number, py: number, box: DOMRect) {
        const dx = Math.max(box.left - px, 0, px - box.right);
        const dy = Math.max(box.top - py, 0, py - box.bottom);
        return Math.sqrt(dx * dx + dy * dy);
      }

      if (edges.length === 0) {
        return { totalEdges: 0, results: [], allPassed: false, error: 'No edges found in DOM' };
      }

      const results = edges.map((edge, idx) => {
        const path = edge.querySelector('path.react-flow__edge-path') as SVGPathElement | null;
        if (!path) {
          return { index: idx, pass: false, error: 'No path.react-flow__edge-path element found' };
        }
        const totalLen = path.getTotalLength();
        if (totalLen <= 0) {
          return { index: idx, pass: false, error: `Edge path length is ${totalLen}` };
        }
        const p0 = path.getPointAtLength(0);
        const p1 = path.getPointAtLength(totalLen);
        const ctm = path.getScreenCTM();
        if (!ctm) {
          return { index: idx, pass: false, error: 'Could not obtain ScreenCTM matrix' };
        }
        const startScreen = p0.matrixTransform(ctm);
        const endScreen = p1.matrixTransform(ctm);

        let startDist = Infinity;
        let endDist = Infinity;
        for (const node of nodes) {
          const box = node.getBoundingClientRect();
          const ds = distToBox(startScreen.x, startScreen.y, box);
          const de = distToBox(endScreen.x, endScreen.y, box);
          if (ds < startDist) startDist = ds;
          if (de < endDist) endDist = de;
        }

        return {
          index: idx,
          startDist,
          endDist,
          pass: startDist <= maxDist && endDist <= maxDist,
        };
      });

      return {
        totalEdges: edges.length,
        results,
        allPassed: results.every((r) => r.pass),
      };
    }, maxDistancePx);

    return check;
  }
}

