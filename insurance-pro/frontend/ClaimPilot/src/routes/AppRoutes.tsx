import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from '../pages/Login';
import { useAuth } from '../store/authStore';

import { CustomerLayout } from '../components/layout/CustomerLayout';
import { AgentLayout } from '../components/layout/AgentLayout';

import { CustomerDashboard } from '../pages/customer/CustomerDashboard';
import { NewClaim } from '../pages/customer/NewClaim';
import { ClaimAnalysis } from '../pages/customer/ClaimAnalysis';
import { MyClaims } from '../pages/customer/MyClaims';
import { MeshViewerPage } from '../pages/customer/MeshViewerPage';

import { AgentDashboard } from '../pages/agent/AgentDashboard';
import { AgentClaims } from '../pages/agent/AgentClaims';
import { AgentClaimDetails } from '../pages/agent/AgentClaimDetails';
import { About } from '../pages/About';
import { NotFound } from '../pages/NotFound';

const ProtectedRoute = ({ children, allowedRole }: { children: React.ReactNode, allowedRole: 'customer' | 'agent' }) => {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role !== allowedRole) {
    return <Navigate to={user.role === 'agent' ? '/agent' : '/customer'} replace />;
  }

  return <>{children}</>;
};

export const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/about" element={<About />} />

        {/* Customer Portal */}
        <Route path="/customer" element={
          <ProtectedRoute allowedRole="customer">
            <CustomerLayout />
          </ProtectedRoute>
        }>
          <Route index element={<CustomerDashboard />} />
          <Route path="claims" element={<MyClaims />} />
          <Route path="new-claim" element={<NewClaim />} />
          <Route path="claims/:id" element={<ClaimAnalysis />} />
        </Route>

        {/* Full Screen Viewers */}
        <Route path="/customer/claims/:id/mesh" element={
          <ProtectedRoute allowedRole="customer">
            <MeshViewerPage />
          </ProtectedRoute>
        } />

        {/* Agent Portal */}
        <Route path="/agent" element={
          <ProtectedRoute allowedRole="agent">
            <AgentLayout />
          </ProtectedRoute>
        }>
          <Route index element={<AgentDashboard />} />
          <Route path="claims" element={<AgentClaims />} />
          <Route path="claims/:id" element={<AgentClaimDetails />} />
        </Route>

        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
};
