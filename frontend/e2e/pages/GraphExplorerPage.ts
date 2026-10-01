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
}
