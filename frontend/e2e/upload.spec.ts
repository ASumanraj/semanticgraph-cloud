import { test, expect } from '@playwright/test'
import { DocumentUploadPage } from './pages/DocumentUploadPage'

test.describe('Document Upload', () => {
  test('user can upload a file and sees confirmation', async ({ page }) => {
    // Intercept the upload request (API may not be running in CI)
    await page.route('**/upload', route => {
      return route.fulfill({ status: 200, body: JSON.stringify({ ok: true }) })
    })

    const uploadPage = new DocumentUploadPage(page)
    await uploadPage.goto()

    // Assert request was made with correct method
    const [request] = await Promise.all([
      page.waitForRequest(req => req.url().includes('/upload') && req.method() === 'POST'),
      uploadPage.uploadFile('test-document.txt', 'Hello knowledge graph'),
    ])

    expect(request.method()).toBe('POST')
    expect(request.headers()['tenant_id']).toBe('tenant-123')

    await expect(page.getByText('Upload Complete!')).toBeVisible({ timeout: 5000 })
  })
})
