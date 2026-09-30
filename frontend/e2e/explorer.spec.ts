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

    // 7. Capture screenshot for visual proof
    await page.screenshot({ path: 'e2e/screenshots/graph-explorer-provenance.png', fullPage: true });
  });
});
