import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LeafletMap } from '../components/LeafletMap';
import { ProtectedRoute } from '../routes/ProtectedRoute';
import * as AuthContext from '../contexts/AuthContext';
import { User } from '../types';

describe('LeafletMap Graceful Degradation', () => {
  it('renders informative placeholder when no coordinates are provided', () => {
    render(<LeafletMap />);
    expect(screen.getByText(/GPS location coordinates are not available/i)).toBeInTheDocument();
  });

  it('renders informative placeholder when coordinates are NaN', () => {
    render(<LeafletMap originLat={NaN} originLng={NaN} />);
    expect(screen.getByText(/GPS location coordinates are not available/i)).toBeInTheDocument();
  });

  it('renders informative placeholder when coordinates are out of bounds', () => {
    render(<LeafletMap originLat={150} originLng={250} />);
    expect(screen.getByText(/GPS location coordinates are not available/i)).toBeInTheDocument();
  });
});

describe('ProtectedRoute Role-Based Access Control', () => {
  const mockUser: User = {
    id: 1,
    email: 'customer@test.com',
    full_name: 'Test Customer',
    role: 'CUSTOMER',
    is_active: true,
  };

  it('redirects to dashboard when user role is not allowed', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/branches']}>
        <Routes>
          <Route path="/dashboard" element={<div>Customer Dashboard Fallback</div>} />
          <Route element={<ProtectedRoute allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER']} />}>
            <Route path="/branches" element={<div>Staff Only Branches</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Customer Dashboard Fallback')).toBeInTheDocument();
    expect(screen.queryByText('Staff Only Branches')).not.toBeInTheDocument();
  });

  it('renders protected child component when user role is allowed', () => {
    const adminUser: User = {
      ...mockUser,
      role: 'ORG_ADMIN',
    };

    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: adminUser,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/branches']}>
        <Routes>
          <Route path="/dashboard" element={<div>Customer Dashboard Fallback</div>} />
          <Route element={<ProtectedRoute allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER']} />}>
            <Route path="/branches" element={<div>Staff Only Branches</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Staff Only Branches')).toBeInTheDocument();
  });

  it('redirects CUSTOMER away from /routes route optimizer page', () => {
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/routes']}>
        <Routes>
          <Route path="/dashboard" element={<div>Redirected From Routes</div>} />
          <Route
            element={
              <ProtectedRoute
                allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT']}
              />
            }
          >
            <Route path="/routes" element={<div>Staff Only Route Optimizer</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Redirected From Routes')).toBeInTheDocument();
    expect(screen.queryByText('Staff Only Route Optimizer')).not.toBeInTheDocument();
  });
});

describe('LeafletMap Multi-Stop Route Mode (Phase 15)', () => {
  it('renders numbered stop markers and polyline when stops and depot are provided', () => {
    const { container } = render(
      <LeafletMap
        depotLat={19.076}
        depotLng={72.8777}
        depotName="Mumbai Central Hub"
        stops={[
          {
            sequenceOrder: 1,
            label: 'Receiver One',
            latitude: 19.11,
            longitude: 72.89,
            status: 'COMPLETED',
            stopType: 'DELIVERY',
          },
          {
            sequenceOrder: 2,
            label: 'Receiver Two',
            latitude: 19.14,
            longitude: 72.91,
            status: 'PENDING',
            stopType: 'DELIVERY',
          },
        ]}
        routePolyline={[
          [19.076, 72.8777],
          [19.11, 72.89],
          [19.14, 72.91],
          [19.076, 72.8777],
        ]}
      />
    );

    expect(screen.queryByText(/GPS location coordinates are not available/i)).not.toBeInTheDocument();
    expect(container.querySelectorAll('.custom-leaflet-marker').length).toBeGreaterThanOrEqual(3);
  });

  it('degrades gracefully when stops contain only invalid coordinates', () => {
    render(
      <LeafletMap
        stops={[
          {
            sequenceOrder: 1,
            label: 'Invalid Stop',
            latitude: 250,
            longitude: NaN,
          },
        ]}
      />
    );
    expect(screen.getByText(/GPS location coordinates are not available/i)).toBeInTheDocument();
  });
});
