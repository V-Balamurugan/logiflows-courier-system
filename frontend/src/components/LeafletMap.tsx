import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { MapPinOff } from 'lucide-react';

interface LeafletMapProps {
  originLat?: number | null;
  originLng?: number | null;
  destLat?: number | null;
  destLng?: number | null;
  currentLat?: number | null;
  currentLng?: number | null;
  originName?: string;
  destName?: string;
  currentLocationName?: string;
}

const isValidCoord = (lat?: number | null, lng?: number | null): boolean => {
  if (lat === undefined || lat === null || lng === undefined || lng === null) return false;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return false;
  return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
};

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

  const hasOrigin = isValidCoord(originLat, originLng);
  const hasDest = isValidCoord(destLat, destLng);
  const hasCurrent = isValidCoord(currentLat, currentLng);
  const hasAnyCoords = hasOrigin || hasDest || hasCurrent;

  useEffect(() => {
    if (!mapContainerRef.current || !hasAnyCoords) return;

    // Destroy prior map instance if existing
    if (mapInstanceRef.current) {
      try {
        mapInstanceRef.current.remove();
      } catch (e) {
        console.warn('Error removing prior map instance:', e);
      }
      mapInstanceRef.current = null;
    }

    try {
      // Default center: priority current -> origin -> dest -> India center
      const defaultLat = hasCurrent ? currentLat! : (hasOrigin ? originLat! : (hasDest ? destLat! : 20.5937));
      const defaultLng = hasCurrent ? currentLng! : (hasOrigin ? originLng! : (hasDest ? destLng! : 78.9629));
      const zoomLevel = hasOrigin && hasDest ? 5 : 6;

      const map = L.map(mapContainerRef.current).setView([defaultLat, defaultLng], zoomLevel);
      mapInstanceRef.current = map;

      // Standard OpenStreetMap TileLayer with error fallback
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      }).addTo(map);

      const latLngs: L.LatLngExpression[] = [];

      // Custom Icons using DivIcon
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
      if (hasOrigin) {
        const originLatLng: [number, number] = [originLat!, originLng!] as [number, number];
        latLngs.push(originLatLng);
        L.marker(originLatLng, { icon: createMarkerIcon('#3b82f6', 'O') })
          .addTo(map)
          .bindPopup(`<b>Origin:</b> ${originName}`);
      }

      // Add Destination Marker
      if (hasDest) {
        const destLatLng: [number, number] = [destLat!, destLng!] as [number, number];
        latLngs.push(destLatLng);
        L.marker(destLatLng, { icon: createMarkerIcon('#10b981', 'D') })
          .addTo(map)
          .bindPopup(`<b>Destination:</b> ${destName}`);
      }

      // Add Current Position Marker
      if (hasCurrent) {
        const curLatLng: [number, number] = [currentLat!, currentLng!] as [number, number];
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
    } catch (err) {
      console.error('Failed to initialize Leaflet map:', err);
    }

    return () => {
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.remove();
        } catch (e) {
          // ignore cleanup error
        }
        mapInstanceRef.current = null;
      }
    };
  }, [originLat, originLng, destLat, destLng, currentLat, currentLng, hasAnyCoords]);

  if (!hasAnyCoords) {
    return (
      <div className="w-full h-80 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col items-center justify-center text-slate-400 gap-2">
        <MapPinOff className="w-8 h-8 text-slate-300" />
        <p className="text-sm font-medium">GPS location coordinates are not available for this consignment yet</p>
        <p className="text-xs text-slate-400">Coordinates will appear once transit checkpoints or delivery scans are recorded</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-80 rounded-2xl overflow-hidden border border-slate-200 shadow-inner z-0">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
};
