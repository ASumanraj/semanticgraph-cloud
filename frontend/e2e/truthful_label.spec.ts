import { test, expect } from '@playwright/test';
import { StatusBannerPage } from './pages/StatusBannerPage';
import { DocumentUploadPage } from './pages/DocumentUploadPage';
import { GraphExplorerPage } from './pages/GraphExplorerPage';

test.describe('Status Banner & Truthful Labeling (T-228)', () => {
  test('banner reads Placeholder extractor and no entity name is shown without banner present', async ({
    page,
  }) => {
    const banner = new StatusBannerPage(page);
    const uploadPage = new DocumentUploadPage(page);
    const explorerPage = new GraphExplorerPage(page);

    await banner.goto();

    // 1. Assert banner reads Placeholder extractor
    await expect(banner.banner).toBeVisible({ timeout: 10_000 });
    await expect(banner.placeholderBadge).toBeVisible();
    await expect(banner.placeholderNotice).toBeVisible();

    // 2. Upload document through real UI
    const [uploadResponse] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes('/api/v1/documents/ingest') && res.request().method() === 'POST',
        { timeout: 15_000 }
      ),
      uploadPage.uploadFile(
        'truthful_label_contract.txt',
        'Consortium agreement between Alpha Corp and Beta Systems in 2026.'
      ),
    ]);
    expect(uploadResponse.status()).toBe(200);

    // 3. Wait for nodes to appear
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 15_000 });

    // 4. Assert that whenever an entity name is present on the page, the banner is also visible
    const nodeCount = await explorerPage.nodes.count();
    expect(nodeCount).toBeGreaterThan(0);
    for (let i = 0; i < nodeCount; i++) {
      const nodeText = await explorerPage.nodes.nth(i).innerText();
      if (nodeText && /Entity from chunk/i.test(nodeText)) {
        await expect(banner.banner).toBeVisible();
        await expect(banner.placeholderNotice).toBeVisible();
      }
    }
  });

  test('stubbing /system as model asserts model id and evaluation-terms line', async ({
    page,
  }) => {
    await page.route('**/api/v1/system', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          profile: 'postgres',
          persistent: true,
          extractor: {
            kind: 'model',
            model_id: 'meta-llama/llama-3.1-8b-instruct',
            terms: 'evaluation-only',
          },
        }),
      });
    });

    const banner = new StatusBannerPage(page);
    await banner.goto();

    await expect(banner.banner).toBeVisible({ timeout: 10_000 });
    await expect(banner.modelBadge).toBeVisible();
    await expect(banner.modelText('meta-llama/llama-3.1-8b-instruct')).toBeVisible();
    await expect(banner.termsText('evaluation-only')).toBeVisible();
    await expect(banner.placeholderBadge).not.toBeVisible();
  });

  test('status fails safe: /system returning 500 shows status unavailable', async ({
    page,
  }) => {
    await page.route('**/api/v1/system', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    const banner = new StatusBannerPage(page);
    await banner.goto();

    await expect(banner.banner).toBeVisible({ timeout: 10_000 });
    await expect(banner.statusUnavailableText).toBeVisible();
    await expect(banner.placeholderBadge).not.toBeVisible();
    await expect(banner.modelBadge).not.toBeVisible();
  });
});
