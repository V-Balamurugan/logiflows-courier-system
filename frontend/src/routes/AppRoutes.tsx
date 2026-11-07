import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { PublicLayout } from '../layouts/PublicLayout';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { ProtectedRoute } from './ProtectedRoute';

import { LandingPage } from '../pages/LandingPage';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { PublicTrackingPage } from '../pages/PublicTrackingPage';
import { DashboardPage } from '../pages/DashboardPage';
import { BookParcelPage } from '../pages/BookParcelPage';
import { ParcelsPage } from '../pages/ParcelsPage';
import { ParcelDetailPage } from '../pages/ParcelDetailPage';
import { AssignmentsPage } from '../pages/AssignmentsPage';
import { QRScannerPage } from '../pages/QRScannerPage';
import { BranchesPage } from '../pages/BranchesPage';
import { EmployeesPage } from '../pages/EmployeesPage';
import { CustomersPage } from '../pages/CustomersPage';
import { VehiclesPage } from '../pages/VehiclesPage';
import { ReportsPage } from '../pages/ReportsPage';
import { ProfilePage } from '../pages/ProfilePage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Pages */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/tracking" element={<PublicTrackingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Authenticated Dashboard Pages */}
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          {/* Universal authenticated routes */}
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/parcels" element={<ParcelsPage />} />
          <Route path="/parcels/:trackingNumber" element={<ParcelDetailPage />} />

          {/* Booking routes: Admins, Branch Managers, Customers */}
          <Route
            element={<ProtectedRoute allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'CUSTOMER']} />}
          >
            <Route path="/book-parcel" element={<BookParcelPage />} />
          </Route>

          {/* Operational routes: Admins, Branch Managers, Delivery Agents */}
          <Route
            element={
              <ProtectedRoute
                allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER', 'DELIVERY_AGENT']}
              />
            }
          >
            <Route path="/assignments" element={<AssignmentsPage />} />
            <Route path="/qr-scanner" element={<QRScannerPage />} />
          </Route>

          {/* Management routes: Super Admin, Org Admin, Branch Manager */}
          <Route
            element={<ProtectedRoute allowedRoles={['SUPER_ADMIN', 'ORG_ADMIN', 'BRANCH_MANAGER']} />}
          >
            <Route path="/branches" element={<BranchesPage />} />
            <Route path="/employees" element={<EmployeesPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/vehicles" element={<VehiclesPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
