import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { MapPinOff } from 'lucide-react';

export interface MapStopMarker {
  sequenceOrder: number;
  label: string;
  address?: string;
  latitude: number;
  longitude: number;
  status?: string;
  stopType?: 'PICKUP' | 'DELIVERY';
  coordsSource?: string;
}

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
  depotLat?: number | null;
  depotLng?: number | null;
  depotName?: string;
  stops?: MapStopMarker[];
  routePolyline?: [number, number][];
  heightClassName?: string;
}

const isValidCoord = (lat?: number | null, lng?: number | null): boolean => {
  if (lat === undefined || lat === null || lng === undefined || lng === null) return false;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return false;
  return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
};

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const getStopPinColor = (status?: string): string => {
  switch (status) {
    case 'COMPLETED':
      return '#10b981';
    case 'FAILED':
      return '#e11d48';
    case 'ARRIVED':
    case 'EN_ROUTE':
      return '#f59e0b';
    case 'SKIPPED':
      return '#64748b';
    default:
      return '#4f46e5';
  }
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
  depotLat,
  depotLng,
  depotName = 'Branch Depot',
  stops,
  routePolyline,
  heightClassName = 'h-80',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  const validStops = (stops || []).filter((s) => isValidCoord(s.latitude, s.longitude));
  const validPolyline = (routePolyline || []).filter((pt) => isValidCoord(pt[0], pt[1]));
  const hasOrigin = isValidCoord(originLat, originLng);
  const hasDest = isValidCoord(destLat, destLng);
  const hasCurrent = isValidCoord(currentLat, currentLng);
  const hasDepot = isValidCoord(depotLat, depotLng);
  const hasAnyCoords =
    hasOrigin || hasDest || hasCurrent || hasDepot || validStops.length > 0 || validPolyline.length > 0;
  const routeSignature = JSON.stringify({ validStops, validPolyline, depotLat, depotLng, depotName });

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
      // Default center: priority current -> depot -> first stop -> origin -> dest -> India center
      const defaultLat = hasCurrent
        ? currentLat!
        : hasDepot
          ? depotLat!
          : validStops.length > 0
            ? validStops[0].latitude
            : hasOrigin
              ? originLat!
              : hasDest
                ? destLat!
                : 20.5937;
      const defaultLng = hasCurrent
        ? currentLng!
        : hasDepot
          ? depotLng!
          : validStops.length > 0
            ? validStops[0].longitude
            : hasOrigin
              ? originLng!
              : hasDest
                ? destLng!
                : 78.9629;
      const zoomLevel = hasOrigin && hasDest ? 5 : validStops.length > 0 ? 12 : 6;

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
              ${escapeHtml(label)}
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
          .bindPopup(`<b>Origin:</b> ${escapeHtml(originName)}`);
      }

      // Add Destination Marker
      if (hasDest) {
        const destLatLng: [number, number] = [destLat!, destLng!] as [number, number];
        latLngs.push(destLatLng);
        L.marker(destLatLng, { icon: createMarkerIcon('#10b981', 'D') })
          .addTo(map)
          .bindPopup(`<b>Destination:</b> ${escapeHtml(destName)}`);
      }

      // Add Current Position Marker
      if (hasCurrent) {
        const curLatLng: [number, number] = [currentLat!, currentLng!] as [number, number];
        L.marker(curLatLng, { icon: createMarkerIcon('#8b5cf6', '★') })
          .addTo(map)
          .bindPopup(`<b>Current Location:</b> ${escapeHtml(currentLocationName)}`)
          .openPopup();
      }

      // Add Depot Hub Marker (Route Optimization)
      if (hasDepot) {
        const depotLatLng: [number, number] = [depotLat!, depotLng!];
        latLngs.push(depotLatLng);
        L.marker(depotLatLng, { icon: createMarkerIcon('#0f172a', 'H') })
          .addTo(map)
          .bindPopup(`<b>Hub Depot:</b> ${escapeHtml(depotName)}`);
      }

      // Add Numbered Route Stop Pins
      validStops.forEach((stop) => {
        const stopLatLng: [number, number] = [stop.latitude, stop.longitude];
        latLngs.push(stopLatLng);
        const color = getStopPinColor(stop.status);
        const details = [
          `<b>#${stop.sequenceOrder}: ${escapeHtml(stop.label)}</b>`,
          stop.stopType ? `Type: ${escapeHtml(stop.stopType)}` : '',
          stop.status ? `Status: ${escapeHtml(stop.status)}` : '',
          stop.address ? escapeHtml(stop.address) : '',
          stop.coordsSource ? `<small>Source: ${escapeHtml(stop.coordsSource)}</small>` : '',
        ]
          .filter(Boolean)
          .join('<br/>');
        L.marker(stopLatLng, { icon: createMarkerIcon(color, String(stop.sequenceOrder)) })
          .addTo(map)
          .bindPopup(details);
      });

      // Draw Route Polyline (multi-stop solid path or point-to-point dashed leg)
      const pathCoords: L.LatLngExpression[] =
        validPolyline.length >= 2 ? validPolyline : latLngs;
      if (pathCoords.length >= 2) {
        const isOptimizedRoute = validPolyline.length >= 2 || validStops.length > 0;
        const polyline = L.polyline(pathCoords, {
          color: isOptimizedRoute ? '#4f46e5' : '#6366f1',
          weight: isOptimizedRoute ? 4 : 3,
          dashArray: isOptimizedRoute ? undefined : '6, 8',
          opacity: 0.85,
        }).addTo(map);

        if (typeof polyline?.getBounds === 'function') {
          map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
        }
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
  }, [originLat, originLng, destLat, destLng, currentLat, currentLng, hasAnyCoords, routeSignature]);

  if (!hasAnyCoords) {
    return (
      <div className={`w-full ${heightClassName} rounded-2xl bg-slate-50 border border-slate-200 flex flex-col items-center justify-center text-slate-400 gap-2 p-4 text-center`}>
        <MapPinOff className="w-8 h-8 text-slate-300" />
        <p className="text-sm font-medium">GPS location coordinates are not available for this consignment yet</p>
        <p className="text-xs text-slate-400">Coordinates will appear once transit checkpoints or delivery scans are recorded</p>
      </div>
    );
  }

  return (
    <div className={`relative w-full ${heightClassName} rounded-2xl overflow-hidden border border-slate-200 shadow-inner z-0`}>
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
};
