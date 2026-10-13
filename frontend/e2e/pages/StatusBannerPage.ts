import { Locator, Page } from '@playwright/test';

export class StatusBannerPage {
  readonly page: Page;
  readonly banner: Locator;
  readonly placeholderBadge: Locator;
  readonly placeholderNotice: Locator;
  readonly modelBadge: Locator;
  readonly statusUnavailableText: Locator;

  constructor(page: Page) {
    this.page = page;
    this.banner = page.locator('[data-testid="status-banner"]');
    this.placeholderBadge = this.banner.getByText('Placeholder extractor', { exact: true });
    this.placeholderNotice = this.banner.getByText(
      'Placeholder extractor: entity names are not extracted from your document.'
    );
    this.modelBadge = this.banner.getByText('Model extractor', { exact: true });
    this.statusUnavailableText = this.banner.getByText('Status unavailable', { exact: false });
  }

  async goto() {
    await this.page.goto('/dashboard/explorer');
  }

  modelText(modelId: string): Locator {
    return this.banner.getByText(modelId);
  }

  termsText(terms: string): Locator {
    return this.banner.getByText(new RegExp(`Evaluation endpoint:\\s*${terms}`, 'i'));
  }
}
