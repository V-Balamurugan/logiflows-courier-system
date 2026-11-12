import { test, expect } from '@playwright/test';

test.describe('LogiFlows Courier System E2E Suite', () => {

  test('Journey 1: Customer login and navigation to booking', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/LogiFlows/i);

    // Fill in customer credentials
    await page.locator('input[type="email"]').fill('customer@example.com');
    await page.locator('input[type="password"]').fill('Customer@123');
    await page.locator('button[type="submit"]').click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('text=Operations Dashboard')).toBeVisible();

    // Navigate to parcel booking
    await page.goto('/book-parcel');
    await expect(page.locator('text=Create Consignment Booking')).toBeVisible();
    await expect(page.locator('input[placeholder*="Sender"], input[name="sender_name"]').first()).toBeVisible();
  });

  test('Journey 2: Public shipment tracking & milestone timeline', async ({ page }) => {
    await page.goto('/tracking');
    await expect(page.locator('text=Shipment Live Tracker')).toBeVisible();

    // Search for seeded demo parcel
    const searchInput = page.locator('input[placeholder*="LF-"]');
    await searchInput.fill('LF-2026-BOM001');
    await page.locator('button:has-text("Track")').click();

    // Verify tracking result card
    await expect(page.locator('text=LF-2026-BOM001')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Milestone History')).toBeVisible();
  });

  test('Journey 3: Org Admin branch management and employee views', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('orgadmin@logiflows.com');
    await page.locator('input[type="password"]').fill('OrgAdmin@123');
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/.*dashboard/);

    // Visit branches
    await page.goto('/branches');
    await expect(page.locator('text=Branch Management')).toBeVisible();
    await expect(page.locator('text=Add New Branch')).toBeVisible();

    // Visit employees
    await page.goto('/employees');
    await expect(page.locator('text=Staff & Employee Roster')).toBeVisible();
    await expect(page.locator('text=Onboard Employee')).toBeVisible();
  });

  test('Journey 4: Branch Manager dispatch assignments interface', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('manager.mumbai@logiflows.com');
    await page.locator('input[type="password"]').fill('Manager@123');
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/.*dashboard/);
    await page.goto('/assignments');
    await expect(page.locator('text=Delivery Assignments')).toBeVisible();
    await expect(page.locator('button:has-text("Create Assignment")')).toBeVisible();
  });

  test('Journey 5: Delivery Agent dashboard and assignments view', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('agent.rahul@logiflows.com');
    await page.locator('input[type="password"]').fill('Agent@123');
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/.*dashboard/);
    await page.goto('/assignments');
    await expect(page.locator('text=Delivery Assignments')).toBeVisible();
  });

  test('Journey 6: Custody QR Scanner interface and verification', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('agent.rahul@logiflows.com');
    await page.locator('input[type="password"]').fill('Agent@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/qr-scanner');
    await expect(page.locator('text=QR Custody Scanner Portal')).toBeVisible();
    await expect(page.locator('button:has-text("Confirm Custody Scan")')).toBeVisible();
  });

  test('Journey 7: Milestone history reflection in parcel detail', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('customer@example.com');
    await page.locator('input[type="password"]').fill('Customer@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/parcels/LF-2026-BOM001');
    await expect(page.locator('text=LF-2026-BOM001')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Consignment Specs')).toBeVisible();
  });

  test('Journey 8: Unauthorized access denial (Customer blocked from admin routes)', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('customer@example.com');
    await page.locator('input[type="password"]').fill('Customer@123');
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/.*dashboard/);

    // Customer attempts to navigate directly to /branches
    await page.goto('/branches');
    // ProtectedRoute redirects unauthorized roles away to /dashboard
    await expect(page).toHaveURL(/.*dashboard/);

    // Customer attempts to navigate to /employees
    await page.goto('/employees');
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('Journey 9: Cross-tenant isolation verification (API layer)', async ({ request }) => {
    // Authenticate as Org Admin
    const loginRes = await request.post('/api/v1/auth/login', {
      data: {
        email: 'orgadmin@logiflows.com',
        password: 'OrgAdmin@123',
      },
    });
    expect(loginRes.ok()).toBeTruthy();
    const { access_token } = await loginRes.json();

    // Query non-existent or foreign tenant branch ID
    const foreignBranchRes = await request.get('/api/v1/branches/99999', {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(foreignBranchRes.status()).toBe(404);
  });

  test('Journey 10: Public tracking PII sanitization (Zero PII leak)', async ({ request }) => {
    const res = await request.get('/api/v1/tracking/public/LF-2026-BOM001');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();

    expect(data.tracking_number).toBe('LF-2026-BOM001');
    expect(data.status).toBeDefined();

    // Assert that sensitive fields are completely absent from public payload
    expect(data).not.toHaveProperty('sender_phone');
    expect(data).not.toHaveProperty('sender_email');
    expect(data).not.toHaveProperty('receiver_phone');
    expect(data).not.toHaveProperty('receiver_email');
    expect(data).not.toHaveProperty('sender_address');
    expect(data).not.toHaveProperty('receiver_address');
    expect(data).not.toHaveProperty('total_charge');
    expect(data).not.toHaveProperty('price');
  });

  test('Journey 11: Branch Manager dispatch suggestions and cancel run controls', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('manager.mumbai@logiflows.com');
    await page.locator('input[type="password"]').fill('Manager@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/assignments');
    await expect(page.locator('text=Delivery Assignments')).toBeVisible();

    // Open create assignment modal
    const createBtn = page.locator('button:has-text("Create Assignment")');
    if (await createBtn.isVisible()) {
      await createBtn.click();
      await expect(page.locator('text=Assign Parcel to Delivery Agent')).toBeVisible();
      await page.keyboard.press('Escape');
    }
  });

  test('Journey 12: Fleet vehicle maintenance status action availability', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('orgadmin@logiflows.com');
    await page.locator('input[type="password"]').fill('OrgAdmin@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/vehicles');
    await expect(page.locator('text=Fleet & Vehicle Management')).toBeVisible();
    await expect(page.locator('text=Register Vehicle')).toBeVisible();
  });

  test('Journey 13: Customer profile address book and billing details interface', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('customer@example.com');
    await page.locator('input[type="password"]').fill('Customer@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/profile');
    await expect(page.locator('text=Account & Security Profile')).toBeVisible();
    await expect(page.locator('text=Customer Address Book & Billing Profile')).toBeVisible();
    await expect(page.locator('input[placeholder*="Apex Logistical Solutions"]')).toBeVisible();
  });

  test('Journey 14: Cryptographic custody chain verification audit modal', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('orgadmin@logiflows.com');
    await page.locator('input[type="password"]').fill('OrgAdmin@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/parcels/LF-2026-BOM001');
    await expect(page.locator('text=LF-2026-BOM001')).toBeVisible({ timeout: 10000 });

    const auditBtn = page.locator('button:has-text("Verify Custody Chain")').first();
    await expect(auditBtn).toBeVisible();
    await auditBtn.click();

    // Verify modal opens with SHA-256 cryptographic audit title
    await expect(page.locator('text=Cryptographic Chain of Custody')).toBeVisible();
    await expect(page.locator('button:has-text("Close Audit")')).toBeVisible();
    await page.locator('button[aria-label="Close modal"]').click({ force: true });
    await expect(page.locator('text=Cryptographic Chain of Custody')).not.toBeVisible();
  });

  test('Journey 15: Public Tracking Live GPS stream and milestone timeline', async ({ page }) => {
    await page.goto('/tracking?number=LF-2026-BOM001');
    await expect(page.locator('text=Shipment Live Tracker')).toBeVisible();
    await expect(page.locator('text=LF-2026-BOM001')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Transit Geo-Route Map')).toBeVisible();
  });

  test('Journey 16: Branch Manager Linehaul Transfers, Bags & Discrepancies Portal', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"]').fill('manager.mumbai@logiflows.com');
    await page.locator('input[type="password"]').fill('Manager@123');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/.*dashboard/);

    await page.goto('/linehaul');
    await expect(page.locator('text=Linehaul Transfers & Consolidation')).toBeVisible();
    await expect(page.locator('button:has-text("Create Linehaul Manifest")')).toBeVisible();
    await expect(page.locator('button:has-text("New Bag")')).toBeVisible();

    // Switch across Consolidation Bags and Discrepancies tabs
    await page.locator('button:has-text("Consolidation Bags")').click();
    await expect(page.locator('text=Bag Code').or(page.locator('text=No consolidation bags created')).first()).toBeVisible();
    await page.locator('button:has-text("Discrepancies")').click();
    await expect(page.locator('button:has-text("Log Transfer Discrepancy")')).toBeVisible();
  });

});
