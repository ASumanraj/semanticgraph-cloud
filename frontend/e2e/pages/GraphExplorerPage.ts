import { Page, Locator } from '@playwright/test';

export class GraphExplorerPage {
  readonly page: Page;
  readonly canvas: Locator;
  readonly nodes: Locator;
  readonly edges: Locator;
  readonly emptyState: Locator;
  readonly propertiesPanel: Locator;
  readonly quoteElement: Locator;
  readonly chunkIdElement: Locator;

  constructor(page: Page) {
    this.page = page;
    this.canvas = page.locator('.react-flow');
    this.nodes = page.locator('.react-flow__node');
    this.edges = page.locator('.react-flow__edge');
    this.emptyState = page.getByText('No graph data available');
    this.propertiesPanel = page.getByText('Properties');
    this.quoteElement = page.locator('blockquote');
    this.chunkIdElement = page.locator('text=Chunk ID');
  }

  async goto() {
    await this.page.goto('/dashboard/explorer');
  }

  async selectFirstNode() {
    await this.nodes.first().click();
  }

  async selectNode(name: string) {
    const node = this.page.locator('.react-flow__node', { hasText: name });
    await node.first().click();
  }
}
