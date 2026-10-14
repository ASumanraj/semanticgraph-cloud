import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { StatusBannerPage } from './pages/StatusBannerPage';
import { DocumentUploadPage } from './pages/DocumentUploadPage';
import { GraphExplorerPage } from './pages/GraphExplorerPage';

test.describe('Capture T-228 Screenshots with Status Banner', () => {
  const screenshotsDir = path.resolve(__dirname, '../../docs/design/screenshots');

  test.beforeAll(() => {
    if (!fs.existsSync(screenshotsDir)) {
      fs.mkdirSync(screenshotsDir, { recursive: true });
    }
  });

  test('capture 1440px and 390px screenshots with status banner', async ({ page }) => {
    const banner = new StatusBannerPage(page);
    const uploadPage = new DocumentUploadPage(page);
    const explorerPage = new GraphExplorerPage(page);

    // --- 1440px Viewport ---
    await page.setViewportSize({ width: 1440, height: 900 });
    const targetBase = process.env.PLAYWRIGHT_BASE_URL;
    if (targetBase) {
      await page.goto(`${targetBase}/dashboard/explorer`);
    } else {
      await banner.goto();
    }

    await expect(banner.banner).toBeVisible({ timeout: 10_000 });
    await expect(banner.placeholderBadge).toBeVisible();
    if (targetBase) {
      await expect(banner.banner.getByText('Storage: Postgres durable')).toBeVisible();
    }

    // 1440px Upload page / explorer top bar
    if (targetBase) {
      await page.screenshot({
        path: path.join(screenshotsDir, '1440-upload-page.png'),
        fullPage: false,
      });
    }

    // Ingest a document if nodes aren't already visible
    const nodeCount = await explorerPage.nodes.count();
    if (nodeCount === 0) {
      await Promise.all([
        page.waitForResponse(
          (res) =>
            res.url().includes('/api/v1/documents/ingest') && res.request().method() === 'POST',
          { timeout: 15_000 }
        ),
        uploadPage.uploadFile(
          'demo_contract_1440.txt',
          'Alpha Corp entered a partnership with Beta Systems in 2026.'
        ),
      ]);
      await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 15_000 });
    }

    // Select first node to show detail drawer and provenance
    await explorerPage.nodes.first().click();
    await expect(page.getByText('Grounded Provenance')).toBeVisible({ timeout: 5_000 });

    // 1440px Selected node screenshot
    if (targetBase) {
      await page.screenshot({
        path: path.join(screenshotsDir, '1440-selected-node.png'),
        fullPage: false,
      });
    }

    // --- 390px Viewport (Mobile) ---
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await page.waitForLoadState('networkidle');

    await expect(banner.banner).toBeVisible({ timeout: 10_000 });
    await expect(banner.placeholderBadge).toBeVisible();
    if (targetBase) {
      await expect(banner.banner.getByText('Storage: Postgres durable')).toBeVisible();
    }

    // 390px Upload page screenshot
    if (targetBase) {
      await page.screenshot({
        path: path.join(screenshotsDir, '390-upload-page.png'),
        fullPage: false,
      });
    }

    // Select node on mobile
    await expect(explorerPage.nodes.first()).toBeVisible({ timeout: 10_000 });
    await explorerPage.nodes.first().click();
    await expect(page.getByText('Grounded Provenance')).toBeVisible({ timeout: 5_000 });

    // 390px Selected node screenshot
    if (targetBase) {
      await page.screenshot({
        path: path.join(screenshotsDir, '390-selected-node.png'),
        fullPage: false,
      });
    }
  });
});
