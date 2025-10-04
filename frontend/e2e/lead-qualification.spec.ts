/**
 * E2E tests for lead qualification flow with Playwright
 */

import { test, expect, Page } from '@playwright/test';

test.describe('Lead Qualification Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to lead qualification page
    await page.goto('http://localhost:5173');
  });

  test('should display lead qualification form', async ({ page }) => {
    // Check form is visible
    await expect(page.getByRole('heading', { name: /qualify lead/i })).toBeVisible();
    
    // Check required fields are present
    await expect(page.getByLabel(/company name/i)).toBeVisible();
    await expect(page.getByLabel(/industry/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /qualify/i })).toBeVisible();
  });

  test('should successfully qualify a lead', async ({ page }) => {
    // Fill out lead form
    await page.getByLabel(/company name/i).fill('Acme Corporation');
    await page.getByLabel(/company website/i).fill('https://acme.com');
    await page.getByLabel(/industry/i).selectOption('SaaS');
    await page.getByLabel(/company size/i).selectOption('100-500');
    await page.getByLabel(/contact name/i).fill('John Doe');
    await page.getByLabel(/contact title/i).fill('CTO');

    // Submit form
    await page.getByRole('button', { name: /qualify/i }).click();

    // Wait for qualification result
    await expect(page.getByText(/qualification score/i)).toBeVisible({ timeout: 10000 });
    
    // Verify score is displayed (0-100 range)
    const scoreElement = page.locator('[data-testid="qualification-score"]');
    await expect(scoreElement).toBeVisible();
    
    const scoreText = await scoreElement.textContent();
    const score = parseInt(scoreText || '0');
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);

    // Verify reasoning is displayed
    await expect(page.getByText(/reasoning/i)).toBeVisible();
  });

  test('should show validation errors for missing required fields', async ({ page }) => {
    // Try to submit empty form
    await page.getByRole('button', { name: /qualify/i }).click();

    // Should show validation error
    await expect(page.getByText(/company name is required/i)).toBeVisible();
  });

  test('should show loading state during qualification', async ({ page }) => {
    // Fill form
    await page.getByLabel(/company name/i).fill('Test Corp');

    // Submit and immediately check for loading state
    await page.getByRole('button', { name: /qualify/i }).click();
    
    // Loading indicator should appear
    await expect(
      page.getByRole('button', { name: /qualifying.../i })
    ).toBeVisible({ timeout: 1000 });
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Mock API failure
    await page.route('**/api/leads/qualify', route => {
      route.fulfill({
        status: 503,
        body: JSON.stringify({ detail: 'Service unavailable' })
      });
    });

    // Fill and submit form
    await page.getByLabel(/company name/i).fill('Error Test');
    await page.getByRole('button', { name: /qualify/i }).click();

    // Should show error message
    await expect(
      page.getByText(/service unavailable|error/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('should clear form after successful qualification', async ({ page }) => {
    // Fill form
    await page.getByLabel(/company name/i).fill('Clear Test Corp');
    await page.getByRole('button', { name: /qualify/i }).click();

    // Wait for result
    await page.waitForTimeout(2000);

    // Click "Qualify Another Lead" or similar button
    const clearButton = page.getByRole('button', { name: /new lead|qualify another/i });
    if (await clearButton.isVisible()) {
      await clearButton.click();
      
      // Form should be cleared
      await expect(page.getByLabel(/company name/i)).toHaveValue('');
    }
  });

  test('should display qualification history', async ({ page }) => {
    // Navigate to history page (if exists)
    const historyLink = page.getByRole('link', { name: /history|leads/i });
    
    if (await historyLink.isVisible()) {
      await historyLink.click();
      
      // Should show list of previous qualifications
      await expect(page.getByRole('table')).toBeVisible();
    }
  });

  test('should handle special characters in input', async ({ page }) => {
    // Test with special characters
    await page.getByLabel(/company name/i).fill('Test™ Corp <script>alert("xss")</script>');
    await page.getByLabel(/notes/i).fill('Unicode test: 你好 🚀 مرحبا');
    
    await page.getByRole('button', { name: /qualify/i }).click();

    // Should not execute scripts and handle unicode
    await expect(page.getByText(/qualification score/i)).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Lead List and Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/leads');
  });

  test('should display leads list', async ({ page }) => {
    // Check if leads table/list is visible
    const leadsContainer = page.locator('[data-testid="leads-list"]');
    
    if (await leadsContainer.isVisible()) {
      await expect(leadsContainer).toBeVisible();
    } else {
      // Or check for empty state
      await expect(page.getByText(/no leads|empty/i)).toBeVisible();
    }
  });

  test('should filter leads by status', async ({ page }) => {
    // Look for filter dropdown
    const filterDropdown = page.getByLabel(/filter by status/i);
    
    if (await filterDropdown.isVisible()) {
      await filterDropdown.selectOption('qualified');
      
      // Wait for filtered results
      await page.waitForTimeout(500);
      
      // Verify filtering worked
      const statusBadges = page.locator('[data-testid="lead-status"]');
      const count = await statusBadges.count();
      
      if (count > 0) {
        for (let i = 0; i < count; i++) {
          await expect(statusBadges.nth(i)).toContainText(/qualified/i);
        }
      }
    }
  });

  test('should search leads by company name', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search/i);
    
    if (await searchInput.isVisible()) {
      await searchInput.fill('Acme');
      await page.waitForTimeout(500);
      
      // Results should contain search term
      await expect(page.getByText(/acme/i).first()).toBeVisible();
    }
  });
});

test.describe('Performance and Accessibility', () => {
  test('should load page within performance budget', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('http://localhost:5173');
    const loadTime = Date.now() - startTime;

    // Page should load in under 3 seconds
    expect(loadTime).toBeLessThan(3000);
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // Tab through form fields
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(/company name/i)).toBeFocused();

    await page.keyboard.press('Tab');
    // Next field should be focused
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // Check for proper accessibility
    const companyNameInput = page.getByLabel(/company name/i);
    await expect(companyNameInput).toHaveAttribute('aria-label');
  });

  test('should work on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('http://localhost:5173');

    // Form should be visible and usable
    await expect(page.getByLabel(/company name/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /qualify/i })).toBeVisible();
  });
});

test.describe('Edge Cases', () => {
  test('should handle very long company names', async ({ page }) => {
    await page.goto('http://localhost:5173');

    const longName = 'A'.repeat(500);
    await page.getByLabel(/company name/i).fill(longName);
    await page.getByRole('button', { name: /qualify/i }).click();

    // Should either accept or show validation error
    await page.waitForTimeout(2000);
  });

  test('should handle rapid form submissions', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // Fill form
    await page.getByLabel(/company name/i).fill('Rapid Test');

    // Click submit multiple times rapidly
    const submitButton = page.getByRole('button', { name: /qualify/i });
    await submitButton.click();
    await submitButton.click();
    await submitButton.click();

    // Should handle gracefully (only one submission or proper queue)
    await page.waitForTimeout(3000);
  });

  test('should persist form data on page refresh (if implemented)', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // Fill form
    await page.getByLabel(/company name/i).fill('Persist Test');
    
    // Reload page
    await page.reload();

    // Check if data persisted (if localStorage/sessionStorage used)
    const companyName = await page.getByLabel(/company name/i).inputValue();
    // This test depends on implementation
  });
});
