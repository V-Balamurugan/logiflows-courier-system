import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

interface LeafletMapProps {
  originLat?: number;
  originLng?: number;
  destLat?: number;
  destLng?: number;
  currentLat?: number;
  currentLng?: number;
  originName?: string;
  destName?: string;
  currentLocationName?: string;
}

export const LeafletMap: React.FC<LeafletMapProps> = ({
  originLat,
  originLng,
  destLat,
  destLng,
  currentLat,
  currentLng,
  originName = 'Origin Hub',
  destName = 'Destination Hub',
  currentLocationName = 'In Transit',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy prior map instance if existing
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    // Default center India if no coords provided
    const defaultLat = currentLat || originLat || 20.5937;
    const defaultLng = currentLng || originLng || 78.9629;
    const zoomLevel = originLat && destLat ? 5 : 6;

    const map = L.map(mapContainerRef.current).setView([defaultLat, defaultLng], zoomLevel);
    mapInstanceRef.current = map;

    // Standard OpenStreetMap TileLayer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    const latLngs: L.LatLngExpression[] = [];

    // Custom Icons using DivIcon for clean styling
    const createMarkerIcon = (color: string, label: string) =>
      L.divIcon({
        className: 'custom-leaflet-marker',
        html: `
          <div style="background-color: ${color}; width: 28px; height: 28px; border-radius: 50%; border: 3px solid white; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 11px; font-weight: bold;">
            ${label}
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

    // Add Origin Marker
    if (originLat && originLng) {
      const originLatLng: [number, number] = [originLat, originLng];
      latLngs.push(originLatLng);
      L.marker(originLatLng, { icon: createMarkerIcon('#3b82f6', 'O') })
        .addTo(map)
        .bindPopup(`<b>Origin:</b> ${originName}`);
    }

    // Add Destination Marker
    if (destLat && destLng) {
      const destLatLng: [number, number] = [destLat, destLng];
      latLngs.push(destLatLng);
      L.marker(destLatLng, { icon: createMarkerIcon('#10b981', 'D') })
        .addTo(map)
        .bindPopup(`<b>Destination:</b> ${destName}`);
    }

    // Add Current Position Marker
    if (currentLat && currentLng) {
      const curLatLng: [number, number] = [currentLat, currentLng];
      L.marker(curLatLng, { icon: createMarkerIcon('#8b5cf6', '★') })
        .addTo(map)
        .bindPopup(`<b>Current Location:</b> ${currentLocationName}`)
        .openPopup();
    }

    // Draw route line
    if (latLngs.length >= 2) {
      const polyline = L.polyline(latLngs, {
        color: '#6366f1',
        weight: 3,
        dashArray: '6, 8',
        opacity: 0.8,
      }).addTo(map);

      map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [originLat, originLng, destLat, destLng, currentLat, currentLng]);

  return (
    <div className="relative w-full h-80 rounded-2xl overflow-hidden border border-slate-200 shadow-inner z-0">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
};

