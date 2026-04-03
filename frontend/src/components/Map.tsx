import React, { useState, useEffect } from 'react';
import Map, { Marker, Popup } from 'react-map-gl';
// @ts-ignore
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

interface Bin {
  id: number;
  lat: number;
  lng: number;
  fill_level: number;
}

export default function WasteMap() {
  const [bins, setBins] = useState<Bin[]>([]);
  const [selectedBin, setSelectedBin] = useState<Bin | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/bins')
      .then(response => response.json())
      .then(data => setBins(data))
      .catch(err => console.error("Error fetching bins:", err));
  }, []);

  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <Map
        initialViewState={{
          longitude: 76.8512,
          latitude: 43.2220,
          zoom: 11
        }}
        style={{width: '100vw', height: '100vh'}}
        mapStyle="mapbox://styles/mapbox/streets-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        {bins.map(bin => (
          <Marker key={bin.id} longitude={bin.lng} latitude={bin.lat} anchor="bottom">
            <div style={{
              backgroundColor: bin.fill_level > 80 ? 'red' : 'green',
              borderRadius: '50%',
              width: '15px',
              height: '15px',
              border: '2px solid white'
            }} title={`Bin ${bin.fill_level}% full`} />
          </Marker>
        ))}
      </Map>
    </div>
  );
}
