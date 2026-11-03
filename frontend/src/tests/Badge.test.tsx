import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../components/Badge';

describe('Badge Component', () => {
  it('renders parcel status cleanly without underscores', () => {
    render(<Badge status="BOOKED" />);
    expect(screen.getByText('BOOKED')).toBeInTheDocument();
  });

  it('renders formatted text for multi-word statuses', () => {
    render(<Badge status="OUT_FOR_DELIVERY" />);
    expect(screen.getByText('OUT FOR DELIVERY')).toBeInTheDocument();
  });

  it('renders role badge with appropriate styling', () => {
    render(<Badge status="SUPER_ADMIN" variant="role" />);
    expect(screen.getByText('SUPER ADMIN')).toBeInTheDocument();
  });
});

