import { useState } from "react";
import { CircleMarker, MapContainer, TileLayer, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const PUNE: [number, number] = [18.5204, 73.8567];

function ClickToPin({ onPick }: { onPick: (p: [number, number]) => void }) {
  useMapEvents({ click: (e) => onPick([e.latlng.lat, e.latlng.lng]) });
  return null;
}

/** Tap the map where the problem is. The server checks the point is inside a
 * PMC ward; nothing here snaps or guesses. */
export function PinPicker({ onConfirm, onCancel }: {
  onConfirm: (point: [number, number]) => void;
  onCancel: () => void;
}) {
  const [pin, setPin] = useState<[number, number] | null>(null);
  return (
    <div className="cfa-modal" role="dialog" aria-modal="true" aria-label="Drop a pin"
      onKeyDown={(e) => e.key === "Escape" && onCancel()}>
      <div className="cfa-modal__box">
        <header className="cfa-modal__head">
          <strong>Drop a pin on the problem</strong>
          <button type="button" className="cfa-icon-btn" onClick={onCancel} aria-label="Close">×</button>
        </header>
        <div className="cfa-map">
          <MapContainer center={PUNE} zoom={12} style={{ height: "100%" }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap contributors" />
            <ClickToPin onPick={setPin} />
            {pin && <CircleMarker center={pin} radius={9} pathOptions={{ color: "#fff", weight: 3, fillColor: "#0e1c2f", fillOpacity: 1 }} />}
          </MapContainer>
        </div>
        <footer className="cfa-modal__foot">
          <span>{pin ? `${pin[0].toFixed(5)}, ${pin[1].toFixed(5)}` : "Tap the map where the problem is."}</span>
          <button type="button" className="cfa-primary" disabled={!pin} onClick={() => pin && onConfirm(pin)}>
            Use this point
          </button>
        </footer>
      </div>
    </div>
  );
}
