import React from 'react';
import { CustomerDashboard } from './CustomerDashboard';

// For simplicity, MyClaims just reuses CustomerDashboard layout or a list
export const MyClaims: React.FC = () => {
  return (
    <div>
      <CustomerDashboard />
    </div>
  );
};
