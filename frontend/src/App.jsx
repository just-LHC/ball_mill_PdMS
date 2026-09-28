import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';

export default function EquipmentChart({ mill = "Mill 6", equipment = "Mill Main Control" }) {
  const [data, setData] = useState({ time: [], vib: [], temp: [] });

  useEffect(() => {
    // Connect to deployed FastAPI WebSocket URL
    const ws = new WebSocket(`wss://your-fastapi-backend.onrender.com/ws/telemetry/${mill}`);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const now = new Date().toLocaleTimeString();

      setData((prev) => ({
        time: [...prev.time.slice(-30), now],
        vib: [...prev.vib.slice(-30), msg.vibration_mm_s],
        temp: [...prev.temp.slice(-30), msg.temperature_c]
      }));
    };

    return () => ws.close();
  }, [mill]);

  return (
    
   );
}