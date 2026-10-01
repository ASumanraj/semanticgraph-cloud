import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { DocumentUploadPage } from './pages/DocumentUploadPage';
import { GraphExplorerPage } from './pages/GraphExplorerPage';

test.describe('Graph Explorer', () => {
  test('user uploads document, inspects node provenance in explorer, and verifies exact quote', async ({
    page,
  }) => {
    const uploadPage = new DocumentUploadPage(page);
    const explorerPage = new GraphExplorerPage(page);

    await uploadPage.goto();

    // 1. Upload document through the real UI against the real running backend
    const [uploadResponse] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes('/api/v1/documents/ingest') && res.request().method() === 'POST',
        { timeout: 15_000 }
      ),
      uploadPage.uploadFile(
        'partnership.txt',
        'Acme Corporation entered a joint partnership with Cyberdyne Systems in 2029.'
      ),
    ]);
    expect(uploadResponse.status()).toBe(200);

    // 2. Wait for upload confirmation
    await expect(page.getByText('Upload Complete!')).toBeVisible({ timeout: 10_000 });

    // 3. The upload completion dispatches document-uploaded event which auto-fetches graph
    // Wait for nodes to appear on canvas
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 15_000 });

    // 4. Click a node to inspect provenance
    const nodeCount = await explorerPage.nodes.count();
    let found = false;
    for (let i = 0; i < nodeCount; i++) {
      await explorerPage.nodes.nth(i).click();
      await expect(page.getByText('Grounded Provenance')).toBeVisible({ timeout: 5_000 });
      await expect(page.getByText('Chunk ID')).toBeVisible();
      await expect(explorerPage.quoteElement).toBeVisible();
      const quoteText = await explorerPage.quoteElement.textContent();
      if (quoteText && quoteText.includes('Acme Corporation')) {
        found = true;
        break;
      }
    }
    expect(found).toBe(true);

    // 5. Capture screenshot for visual proof
    fs.mkdirSync('e2e/screenshots', { recursive: true });
    await page.screenshot({ path: 'e2e/screenshots/graph-explorer-provenance.png', fullPage: true });
  });

  test('hover highlights the node and its neighbours and dims the rest', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);

    // Mock graph with 3 nodes: Alpha connected to Beta; Gamma is isolated
    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: 'node-alpha', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: 'node-beta', name: 'Beta LLC', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: 'node-gamma', name: 'Gamma Inc', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [
            {
              id: 'edge-alpha-beta',
              source: 'node-alpha',
              target: 'node-beta',
              edge_type: 'PARTNERS_WITH',
              weight: 0.9,
            },
          ],
          truncated: false,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
    expect(await explorerPage.nodes.count()).toBe(3);

    // Hover over Alpha Corp
    await explorerPage.hoverNode('Alpha Corp');

    const nodeAlpha = page.locator('.react-flow__node', { hasText: 'Alpha Corp' });
    const nodeBeta = page.locator('.react-flow__node', { hasText: 'Beta LLC' });
    const nodeGamma = page.locator('.react-flow__node', { hasText: 'Gamma Inc' });

    // Alpha (hovered) and Beta (neighbour) maintain opacity 1
    await expect(nodeAlpha).toHaveCSS('opacity', '1');
    await expect(nodeBeta).toHaveCSS('opacity', '1');

    // Gamma (isolated) is dimmed to opacity 0.25
    await expect(nodeGamma).toHaveCSS('opacity', '0.25');

    // Edge between Alpha and Beta is highlighted (opacity 1)
    const edge = explorerPage.edges.first();
    await expect(edge).toHaveCSS('opacity', '1');

    // Move mouse away to canvas pane
    await page.mouse.move(10, 10);
    await expect(nodeGamma).toHaveCSS('opacity', '1');
  });

  test('keyboard navigation (/ focuses search, arrows move between connected nodes, Esc clears)', async ({
    page,
  }) => {
    const explorerPage = new GraphExplorerPage(page);

    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            {
              id: 'node-1',
              name: 'Alpha Corp',
              entity_type: 'ORGANIZATION',
              kind: 'raw_entity',
              provenance: { chunk_id: 'chk-1', start_offset: 0, end_offset: 10, quote: 'Alpha Corp quote' },
            },
            {
              id: 'node-2',
              name: 'Beta LLC',
              entity_type: 'ORGANIZATION',
              kind: 'raw_entity',
              provenance: { chunk_id: 'chk-2', start_offset: 15, end_offset: 23, quote: 'Beta LLC quote' },
            },
          ],
          edges: [
            {
              id: 'edge-1-2',
              source: 'node-1',
              target: 'node-2',
              edge_type: 'COLLABORATES_WITH',
            },
          ],
          truncated: false,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });

    // 1. Pressing '/' focuses search input
    await page.keyboard.press('/');
    await expect(explorerPage.searchInput).toBeFocused();

    // 2. Pressing Escape blurs search
    await page.keyboard.press('Escape');
    await expect(explorerPage.searchInput).not.toBeFocused();

    // 3. Click first node to select Alpha Corp
    await explorerPage.selectNode('Alpha Corp');
    await expect(page.getByText('Alpha Corp quote')).toBeVisible();

    // 4. Pressing Arrow key navigates to connected node Beta LLC
    await page.keyboard.press('ArrowRight');
    await expect(page.getByText('Beta LLC quote')).toBeVisible();

    // 5. Pressing Escape clears selection
    await page.keyboard.press('Escape');
    await expect(page.getByText('Selection Details')).toBeVisible();
  });

  test('entity-type filter chips with counts operate client-side', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);

    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: '1', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: '2', name: 'Beta LLC', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: '3', name: 'Jane Doe', entity_type: 'PERSON', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: false,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });

    // Assert filter chips with counts are displayed
    const orgChip = explorerPage.typeFilterChip('ORGANIZATION');
    const personChip = explorerPage.typeFilterChip('PERSON');
    await expect(orgChip).toBeVisible();
    await expect(personChip).toBeVisible();
    await expect(orgChip).toContainText('2');
    await expect(personChip).toContainText('1');

    // Initially all 3 nodes visible
    expect(await explorerPage.nodes.count()).toBe(3);

    // Toggle PERSON chip off
    await personChip.click();

    // Only 2 nodes remain visible on canvas
    await expect(page.locator('.react-flow__node', { hasText: 'Jane Doe' })).not.toBeVisible();
    expect(await explorerPage.nodes.count()).toBe(2);
    await expect(page.getByText('2 nodes active · 0 edges')).toBeVisible();

    // Toggle PERSON chip back on
    await personChip.click();
    await expect(page.locator('.react-flow__node', { hasText: 'Jane Doe' })).toBeVisible();
    expect(await explorerPage.nodes.count()).toBe(3);
  });

  test('double-click expands node neighbourhood using query route with loading and error states', async ({
    page,
  }) => {
    const explorerPage = new GraphExplorerPage(page);

    // Initial graph with 1 node
    await page.route('**/api/v1/graph?*depth=2*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: 'node-seed', name: 'Alpha Seed', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: false,
        }),
      });
    });

    // Expand response when double clicking Alpha Seed
    await page.route('**/api/v1/graph?*query=Alpha+Seed*depth=1*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: 'node-seed', name: 'Alpha Seed', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: 'node-expanded-1', name: 'Expanded Partner', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [
            {
              id: 'edge-expanded',
              source: 'node-seed',
              target: 'node-expanded-1',
              edge_type: 'AFFILIATED_WITH',
            },
          ],
          truncated: false,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
    expect(await explorerPage.nodes.count()).toBe(1);

    // Double click to expand
    await explorerPage.doubleClickNode('Alpha Seed');

    // New node appeared on canvas
    await expect(page.locator('.react-flow__node', { hasText: 'Expanded Partner' })).toBeVisible({
      timeout: 5000,
    });
    expect(await explorerPage.nodes.count()).toBe(2);

    // Test expand error state on second expansion
    await page.route('**/api/v1/graph?*query=Expanded+Partner*depth=1*', (route) => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Expansion failed' }),
      });
    });

    await explorerPage.doubleClickNode('Expanded Partner');
    await expect(explorerPage.expandError).toBeVisible({ timeout: 5000 });
  });

  test('search that matches nothing shows no-match state and never "No graph yet"', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);
    await explorerPage.goto();

    await page.route('**/api/v1/graph?*query=NonExistentEntityXYZ*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ nodes: [], edges: [], truncated: false }),
      });
    });

    await explorerPage.searchInput.fill('NonExistentEntityXYZ');
    await expect(explorerPage.noMatchHeading('NonExistentEntityXYZ')).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.clearSearchButton).toBeVisible();
    await expect(page.getByText('No graph yet')).not.toBeVisible();

    await explorerPage.clearSearchButton.click();
    await expect(explorerPage.searchInput).toHaveValue('');
  });

  test('failed request shows error state with Retry and keeps previous graph visible behind it', async ({
    page,
  }) => {
    const explorerPage = new GraphExplorerPage(page);

    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: '11111111-1111-1111-1111-111111111111', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
            { id: '22222222-2222-2222-2222-222222222222', name: 'Beta LLC', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: false,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
    expect(await explorerPage.nodes.count()).toBe(2);

    await page.route('**/api/v1/graph?*query=FailSearch*', (route) => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    await explorerPage.searchInput.fill('FailSearch');
    await expect(explorerPage.errorState).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.retryButton).toBeVisible();

    // Previous graph is still visible behind error overlay
    await expect(explorerPage.canvas).toBeVisible();
    expect(await explorerPage.nodes.count()).toBe(2);

    // Restore working route
    await page.route('**/api/v1/graph?*query=FailSearch*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: '11111111-1111-1111-1111-111111111111', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: false,
        }),
      });
    });

    await explorerPage.retryButton.click();
    await expect(explorerPage.errorState).not.toBeVisible({ timeout: 5000 });
    await expect(explorerPage.nodes.first()).toBeVisible();
  });

  test('truncated banner appears only when API says truncated', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);

    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: '11111111-1111-1111-1111-111111111111', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: true,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.truncatedBanner).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.truncatedCounter).toBeVisible();

    await page.route('**/api/v1/graph*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: '11111111-1111-1111-1111-111111111111', name: 'Alpha Corp', entity_type: 'ORGANIZATION', kind: 'raw_entity' },
          ],
          edges: [],
          truncated: false,
        }),
      });
    });

    await page.reload();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.truncatedBanner).not.toBeVisible();
    await expect(explorerPage.truncatedCounter).not.toBeVisible();
  });

  test('captures responsive screenshots at 1440, 1280, and 390 for all 6 required states', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const explorerPage = new GraphExplorerPage(page);
    const screenshotDir = path.resolve(__dirname, 'screenshots');
    const docsScreenshotDir = path.resolve(__dirname, '..', '..', 'docs', 'design', 'screenshots');
    fs.mkdirSync(screenshotDir, { recursive: true });
    fs.mkdirSync(docsScreenshotDir, { recursive: true });

    const viewports = [
      { name: '1440', width: 1440, height: 900 },
      { name: '1280', width: 1280, height: 800 },
      { name: '390', width: 390, height: 844 },
    ];

    const standardGraphData = {
      nodes: [
        {
          id: 'node-alpha',
          name: 'Acme Corporation',
          entity_type: 'ORGANIZATION',
          kind: 'raw_entity',
          provenance: {
            chunk_id: '9f8b4a2e-5c1d-4e3a-b7f6-8c2d1e0a9b8c',
            start_offset: 0,
            end_offset: 16,
            quote: 'Acme Corporation entered a joint partnership with Cyberdyne Systems in 2029.',
          },
        },
        {
          id: 'node-beta',
          name: 'Cyberdyne Systems',
          entity_type: 'ORGANIZATION',
          kind: 'raw_entity',
          provenance: {
            chunk_id: '9f8b4a2e-5c1d-4e3a-b7f6-8c2d1e0a9b8c',
            start_offset: 50,
            end_offset: 67,
            quote: 'joint partnership with Cyberdyne Systems in 2029.',
          },
        },
      ],
      edges: [
        {
          id: 'edge-partnership',
          source: 'node-alpha',
          target: 'node-beta',
          edge_type: 'PARTNERSHIP_WITH',
          weight: 0.95,
          valid_from: '2029-01-01T00:00:00Z',
          valid_to: null,
          provenance: {
            chunk_id: '9f8b4a2e-5c1d-4e3a-b7f6-8c2d1e0a9b8c',
            start_offset: 27,
            end_offset: 44,
            quote: 'entered a joint partnership with',
          },
        },
      ],
      truncated: false,
    };

    const saveScreenshots = async (filename: string, targetLocator?: any) => {
      const p1 = path.join(screenshotDir, filename);
      const p2 = path.join(docsScreenshotDir, filename);
      if (targetLocator) {
        await targetLocator.scrollIntoViewIfNeeded();
      } else {
        await explorerPage.container.scrollIntoViewIfNeeded();
      }
      await explorerPage.container.screenshot({ path: p1 });
      fs.copyFileSync(p1, p2);
    };

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      // State 1: selected-node
      await page.route('**/api/v1/graph*', (route) => {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(standardGraphData),
        });
      });
      await explorerPage.goto();
      await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
      await explorerPage.selectNode('Acme Corporation');
      await expect(page.getByText('Grounded Provenance').first()).toBeVisible();
      await expect(page.locator('.react-flow__node', { hasText: 'Acme Corporation' })).toBeVisible();
      await expect(page.getByText('Chunk ID').first()).toBeVisible();
      await page.waitForTimeout(300); // allow framer-motion slide-in to settle
      await saveScreenshots(`${vp.name}-selected-node.png`, page.locator('.react-flow__node', { hasText: 'Acme Corporation' }));

      // State 2: selected-edge
      await explorerPage.selectFirstEdge();
      await expect(page.getByText('PARTNERSHIP_WITH').first()).toBeVisible();
      await expect(page.getByText('Edge Type')).toBeVisible();
      await page.waitForTimeout(300);
      await saveScreenshots(`${vp.name}-selected-edge.png`, page.getByText('PARTNERSHIP_WITH').first());

      // State 3: empty-state (no query and no nodes)
      await page.route('**/api/v1/graph*', (route) => {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ nodes: [], edges: [], truncated: false }),
        });
      });
      await explorerPage.goto();
      await expect(page.getByRole('heading', { name: 'No graph yet' })).toBeVisible({ timeout: 5000 });
      await expect(page.getByText('Upload a contract. Entities and relationships extracted from it appear here')).toBeVisible();
      await saveScreenshots(`${vp.name}-empty-state.png`, page.getByRole('heading', { name: 'No graph yet' }));

      // State 4: no-match-state (query matches nothing)
      await page.route('**/api/v1/graph?*query=MissingQuery*', (route) => {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ nodes: [], edges: [], truncated: false }),
        });
      });
      await explorerPage.searchInput.fill('MissingQuery');
      await expect(explorerPage.noMatchHeading('MissingQuery')).toBeVisible({ timeout: 5000 });
      await expect(page.getByText('Try searching for a different keyword')).toBeVisible();
      await saveScreenshots(`${vp.name}-no-match-state.png`, explorerPage.noMatchHeading('MissingQuery'));

      // State 5: error-state
      await page.route('**/api/v1/graph?*query=ErrorQuery*', (route) => {
        return route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Server Error' }),
        });
      });
      await explorerPage.searchInput.fill('ErrorQuery');
      await expect(explorerPage.errorState).toBeVisible({ timeout: 5000 });
      await expect(page.getByRole('heading', { name: "Couldn't load the graph" })).toBeVisible();
      await expect(explorerPage.retryButton).toBeVisible();
      await saveScreenshots(`${vp.name}-error-state.png`, explorerPage.errorState);

      // State 6: truncated-notice
      await page.route('**/api/v1/graph*', (route) => {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...standardGraphData,
            truncated: true,
          }),
        });
      });
      await explorerPage.goto();
      await expect(explorerPage.truncatedBanner).toBeVisible({ timeout: 5000 });
      await expect(page.getByText('Showing the first 200 entities. Narrow your search to see more.')).toBeVisible();
      await saveScreenshots(`${vp.name}-truncated-notice.png`, explorerPage.truncatedBanner);

      // Full viewport screenshot at 1440x900 showing no scroll needed
      if (vp.name === '1440') {
        const vpPath1 = path.join(screenshotDir, '1440-viewport-no-scroll.png');
        const vpPath2 = path.join(docsScreenshotDir, '1440-viewport-no-scroll.png');
        await page.screenshot({ path: vpPath1, fullPage: false });
        fs.copyFileSync(vpPath1, vpPath2);
      }
    }
  });

  test('live API end-to-end: upload document, hover highlighting, and double-click expansion without page.route mocks', async ({
    page,
  }) => {
    const uploadPage = new DocumentUploadPage(page);
    const explorerPage = new GraphExplorerPage(page);

    await uploadPage.goto();

    // 1. Upload document through the real UI against the real running backend
    const [uploadResponse] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes('/api/v1/documents/ingest') && res.request().method() === 'POST',
        { timeout: 15_000 }
      ),
      uploadPage.uploadFile(
        'e2e-live-contract.txt',
        'Acme Corporation entered a joint partnership with Cyberdyne Systems in 2029.'
      ),
    ]);
    expect(uploadResponse.status()).toBe(200);

    // 2. Wait for upload confirmation and graph to render
    await expect(page.getByText('Upload Complete!')).toBeVisible({ timeout: 10_000 });
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 15_000 });

    // 3. Live hover highlighting
    const firstNode = explorerPage.nodes.first();
    await expect(firstNode).toBeVisible();
    await firstNode.hover({ force: true });
    await expect(firstNode).toHaveCSS('opacity', '1');

    // 4. Live double-click expansion without page.route mocks
    const [expandResponse] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes('/api/v1/graph') && res.url().includes('query=') && res.status() === 200,
        { timeout: 10_000 }
      ),
      firstNode.dblclick({ force: true }),
    ]);
    expect(expandResponse.status()).toBe(200);
    await expect(page.getByTestId('expand-error')).not.toBeVisible();
  });

  test('API contract: real /api/v1/graph response keys match mock payloads and ApiNode/ApiEdge domain schemas', async ({
    page,
  }) => {
    const response = await page.request.get('/api/v1/graph', {
      headers: {
        'X-Tenant-ID': '00000000-0000-0000-0000-000000000001',
      },
    });
    expect(response.status()).toBe(200);
    const data = await response.json();

    expect(data).toHaveProperty('nodes');
    expect(data).toHaveProperty('edges');
    expect(data).toHaveProperty('truncated');
    expect(Array.isArray(data.nodes)).toBe(true);
    expect(Array.isArray(data.edges)).toBe(true);
    expect(typeof data.truncated).toBe('boolean');

    for (const node of data.nodes) {
      expect(node).toHaveProperty('id');
      expect(node).toHaveProperty('name');
      expect(node).toHaveProperty('entity_type');
      expect(node).toHaveProperty('kind');
      expect(typeof node.id).toBe('string');
      expect(typeof node.name).toBe('string');
      expect(typeof node.entity_type).toBe('string');
      expect(typeof node.kind).toBe('string');

      if (node.provenance) {
        expect(node.provenance).toHaveProperty('chunk_id');
        expect(node.provenance).toHaveProperty('start_offset');
        expect(node.provenance).toHaveProperty('end_offset');
        expect(node.provenance).toHaveProperty('quote');
      }
    }

    for (const edge of data.edges) {
      expect(edge).toHaveProperty('id');
      expect(edge).toHaveProperty('source');
      expect(edge).toHaveProperty('target');
      expect(edge).toHaveProperty('edge_type');
      expect(typeof edge.id).toBe('string');
      expect(typeof edge.source).toBe('string');
      expect(typeof edge.target).toBe('string');
      expect(typeof edge.edge_type).toBe('string');

      if (edge.provenance) {
        expect(edge.provenance).toHaveProperty('chunk_id');
        expect(edge.provenance).toHaveProperty('start_offset');
        expect(edge.provenance).toHaveProperty('end_offset');
        expect(edge.provenance).toHaveProperty('quote');
      }
    }
  });
});
