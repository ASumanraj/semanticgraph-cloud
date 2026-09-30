import { test, expect } from '@playwright/test';
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

    // 3. Reload explorer page so GraphExplorer fetches the extracted graph
    const [graphResponse] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes('/api/v1/graph') && res.request().method() === 'GET',
        { timeout: 15_000 }
      ),
      page.reload(),
    ]);

    expect(graphResponse.status()).toBe(200);
    const graphData = await graphResponse.json();
    expect(graphData.nodes.length).toBeGreaterThan(0);

    // 4. Assert nodes are rendered on the canvas
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 10_000 });

    // 5. Click a node to inspect provenance
    // When previous tests or multiple documents populated nodes, find the Acme Corporation node
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

    // 6. Capture screenshot for visual proof
    await page.screenshot({ path: 'e2e/screenshots/graph-explorer-provenance.png', fullPage: true });
  });

  test('search that matches nothing shows no-match state and never "No graph yet"', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);
    await explorerPage.goto();

    // Intercept graph search query that returns empty nodes
    await page.route('**/api/v1/graph?*query=NonExistentEntityXYZ*', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ nodes: [], edges: [], truncated: false }),
      });
    });

    await explorerPage.searchInput.fill('NonExistentEntityXYZ');

    // Assert no-match heading with query and clear search button are visible
    await expect(explorerPage.noMatchHeading('NonExistentEntityXYZ')).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.clearSearchButton).toBeVisible();

    // Assert "No graph yet" text is NEVER shown
    await expect(page.getByText('No graph yet')).not.toBeVisible();

    // Click "Clear search" and verify search input is reset
    await explorerPage.clearSearchButton.click();
    await expect(explorerPage.searchInput).toHaveValue('');
  });

  test('failed request shows error state with Retry and keeps previous graph visible behind it', async ({
    page,
  }) => {
    const explorerPage = new GraphExplorerPage(page);

    // Provide initial graph with 2 nodes
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

    // Subsequent search request fails with HTTP 500
    await page.route('**/api/v1/graph?*query=FailSearch*', (route) => {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    await explorerPage.searchInput.fill('FailSearch');

    // Assert error state overlay is visible with Retry button
    await expect(explorerPage.errorState).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.retryButton).toBeVisible();

    // Assert previous graph is STILL visible behind the error overlay
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

    // Click Retry and verify recovery
    await explorerPage.retryButton.click();
    await expect(explorerPage.errorState).not.toBeVisible({ timeout: 5000 });
    await expect(explorerPage.nodes.first()).toBeVisible();
  });

  test('truncated banner appears only when API says truncated', async ({ page }) => {
    const explorerPage = new GraphExplorerPage(page);

    // 1. Mock response with truncated: true
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
          truncated: true,
        }),
      });
    });

    await explorerPage.goto();
    await expect(explorerPage.truncatedBanner).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.truncatedCounter).toBeVisible();

    // 2. Mock response with truncated: false
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

    await page.reload();
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 5000 });
    await expect(explorerPage.truncatedBanner).not.toBeVisible();
    await expect(explorerPage.truncatedCounter).not.toBeVisible();
    await expect(page.getByText('2 nodes active · 0 edges')).toBeVisible();
  });
});
