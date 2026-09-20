import { Page, Locator } from '@playwright/test'

export class DocumentUploadPage {
  readonly page: Page
  readonly dropZone: Locator
  readonly fileInput: Locator
  readonly uploadButton: Locator
  readonly successText: Locator

  constructor(page: Page) {
    this.page = page
    this.dropZone = page.getByText('Click or drag document here')
    this.fileInput = page.locator('input[type="file"]')
    this.uploadButton = page.getByRole('button', { name: 'Extract Knowledge' })
    this.successText = page.getByText('Upload Complete!')
  }

  async goto() {
    await this.page.goto('/dashboard/explorer')
    await this.dropZone.waitFor({ state: 'visible' })
  }

  async uploadFile(filename: string, content: string) {
    // Set file on the hidden input
    await this.fileInput.setInputFiles({
      name: filename,
      mimeType: 'text/plain',
      buffer: Buffer.from(content),
    })
    await this.uploadButton.click()
  }
}
