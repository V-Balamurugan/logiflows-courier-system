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
});
