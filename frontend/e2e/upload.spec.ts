import { test, expect } from '@playwright/test';
import { DocumentUploadPage } from './pages/DocumentUploadPage';

test.describe('Document Upload', () => {
  test('user can upload a file against the real running API and sees confirmation', async ({ page }) => {
    const uploadPage = new DocumentUploadPage(page);
    await uploadPage.goto();

    // Wait for the real API response with NO page.route stubbing
    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes('/api/v1/documents/ingest') && res.request().method() === 'POST',
        { timeout: 15_000 }
      ),
      uploadPage.uploadFile('enterprise_agreement.txt', 'This is an enterprise service agreement between Acme and Beta.'),
    ]);

    // Verify the HTTP request that reached the real API
    const request = response.request();
    expect(request.method()).toBe('POST');
    const tenantHeader = request.headers()['x-tenant-id'];
    expect(tenantHeader).toBeDefined();

    // Verify the real API response
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.document_id).toBeDefined();
    expect(body.status).toBe('extracting');

    // Verify the UI feedback
    await expect(page.getByText('Upload Complete!')).toBeVisible({ timeout: 10_000 });
  });
});
