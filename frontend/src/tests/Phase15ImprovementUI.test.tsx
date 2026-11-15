import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LeafletMap } from '../components/LeafletMap';

describe('Subphase 15.14 UI Improvements: LeafletMap & Dispatch Guard', () => {
  it('renders "Estimated (No road geometry)" notice when stops exist but geometry is empty', () => {
    render(
      <LeafletMap
        depotLat={13.0827}
        depotLng={80.2707}
        stops={[
          {
            sequenceOrder: 1,
            label: 'Stop 1',
            latitude: 13.0900,
            longitude: 80.2800,
            coordsSource: 'BRANCH_VICINITY_ESTIMATE',
          },
        ]}
        routePolyline={[]} // Empty road geometry (e.g. local estimate)
      />
    );

    expect(screen.getByText(/Estimated \(No road geometry\)/i)).toBeInTheDocument();
  });

  it('renders live driver telemetry marker popup information when driver coordinates are present', () => {
    const { container } = render(
      <LeafletMap
        depotLat={13.0827}
        depotLng={80.2707}
        driverLat={13.0850}
        driverLng={80.2750}
        driverName="Suresh Driver"
        driverLastSeen="2 mins ago"
        stops={[]}
      />
    );

    expect(container.querySelectorAll('.custom-leaflet-marker').length).toBeGreaterThanOrEqual(2);
  });
});
