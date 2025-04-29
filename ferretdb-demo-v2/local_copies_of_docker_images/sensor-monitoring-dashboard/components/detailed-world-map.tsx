"use client";

import React, { useState, useEffect, useMemo, useCallback, memo } from "react";
import { GoogleMap, Marker, OverlayView, useLoadScript } from "@react-google-maps/api";
import { useRouter } from "next/navigation";

const mapContainerStyle = {
  width: "100%",
  height: "350px",
};

const center = {
  lat: 0,
  lng: 0,
};

const options = {
  disableDefaultUI: true,
  zoomControl: true,
  styles: [
    { featureType: "all", elementType: "labels", stylers: [{ visibility: "true" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ visibility: "off" }] },
    { featureType: "road.highway", elementType: "labels", stylers: [{ visibility: "off" }] },
    { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ visibility: "off" }] },
  ],
};

interface SensorApiResponse {
  count: number;
  sensor_id: string;
  location: string; // np. "50.025629,8.561904"
}

interface Sensor {
  id: string;
  location: google.maps.LatLngLiteral;
}

interface SensorEvent {
  _id: string;
  id: number;
  timestamp: string;
  sensor_id: string;
  temperature: number;
  vibration: number;
  voltage: number;
  status_code: number;
  anomaly_flag: number;
  anomaly_type: string;
  firmware_version: string;
  model: string;
  manufacturer: string;
  location: string;
  synced: number;
}

interface SensorDataItem {
  event: SensorEvent;
  count: number;
  ping: boolean;
}

const BASE_COLOR = "#05ca53";

const createPingIcon = (baseColor: string, pingColor: string, size = 20): google.maps.Icon => {
  const half = size / 2;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${half}" cy="${half}" r="${half * 0.6}" fill="${baseColor}" />
      <circle cx="${half}" cy="${half}" r="${half * 0.6}" fill="none" stroke="${pingColor}" stroke-width="2">
        <animate attributeName="r" from="${half * 0.6}" to="${half}" dur="0.8s" fill="freeze" />
        <animate attributeName="opacity" from="1" to="0" dur="0.8s" fill="freeze" />
      </circle>
    </svg>
  `;
  return {
    url: `data:image/svg+xml,${encodeURIComponent(svg)}`,
    scaledSize: new window.google.maps.Size(size, size),
    anchor: new window.google.maps.Point(half, half),
  };
};

const createStaticIcon = (color: string, size = 20): google.maps.Icon => {
  const half = size / 2;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${half}" cy="${half}" r="${half * 0.6}" fill="${color}" />
    </svg>
  `;
  return {
    url: `data:image/svg+xml,${encodeURIComponent(svg)}`,
    scaledSize: new window.google.maps.Size(size, size),
    anchor: new window.google.maps.Point(half, half),
  };
};

interface SensorMarkerProps {
  sensor: Sensor;
  data?: SensorDataItem;
  zoom: number;
  onHover: (sensor: Sensor, data?: SensorDataItem) => void;
  onLeave: () => void;
}

const SensorMarker = memo(function SensorMarker({ sensor, data, zoom, onHover, onLeave }: SensorMarkerProps) {
  const router = useRouter();
  const event = data?.event;

  const size = useMemo(() => Math.max(10, 20 + (zoom - 2)), [zoom]);

  const icon = useMemo(() => {
    if (event && event.anomaly_flag === 1 && event.anomaly_type !== "trend") {
      return createStaticIcon("red", size);
    } else if (data?.ping) {
      return createPingIcon(BASE_COLOR, "#ff1500", size);
    } else {
      return createStaticIcon(BASE_COLOR, size);
    }
  }, [event, data, size]);

  const clickableShape = useMemo(() => ({
    type: "circle",
    coords: [size / 4, size  /4 , size],
  }), [size]);

  return (
      <Marker
          position={sensor.location}
          icon={icon}
          shape={clickableShape}
          onClick={() => router.push(`/sensor/${sensor.id}`)}
          onMouseOver={() => onHover(sensor, data)}
          onMouseOut={() => onLeave()}
          optimized={false}
      />
  );
});

export default function DetailedWorldMap({apiKey}: {apiKey: string}) {
  const [sensorLocations, setSensorLocations] = useState<Sensor[]>([]);
  const [sensorsLoading, setSensorsLoading] = useState<boolean>(true);
  const [sensorData, setSensorData] = useState<Record<string, SensorDataItem>>({});
  const [zoom, setZoom] = useState<number>(2);
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const [hoveredSensor, setHoveredSensor] = useState<{ sensor: Sensor; data?: SensorDataItem } | null>(null);

  const { isLoaded, loadError } = useLoadScript({
    googleMapsApiKey: apiKey || "",
    language: "en",
  });

  const onIdle = useCallback(() => {
    if (map) {
      setZoom(map.getZoom());
    }
  }, [map]);

  const onLoad = useCallback((mapInstance: google.maps.Map) => {
    setMap(mapInstance);
    setZoom(mapInstance.getZoom());
  }, []);

  useEffect(() => {
    const fetchSensors = async () => {
      try {
        const res = await fetch("/api/sensors");
        if (!res.ok) throw new Error("Error fetching sensors list");
        const data = await res.json();
        const sensors: Sensor[] = data.data.map((item: SensorApiResponse) => {
          const [lat, lng] = item.location.split(",").map(Number);
          return { id: item.sensor_id, location: { lat, lng } };
        });
        setSensorLocations(sensors);
        setSensorsLoading(false);
      } catch (err) {
        console.error(err);
        setSensorsLoading(false);
      }
    };
    fetchSensors();
  }, []);

  useEffect(() => {
    if (sensorLocations.length === 0) return;

    const fetchSensorData = async () => {
      setSensorData((prevSensorData) => {
        const updatedData: Record<string, SensorDataItem> = { ...prevSensorData };

        Promise.all(
            sensorLocations.map(async (sensor) => {
              try {
                const res = await fetch(`/api/sensor-data/${sensor.id}`);
                if (!res.ok) {
                  console.error(`Error fetching data for sensor ${sensor.id}`);
                  return;
                }
                const eventsResponse = await res.json();
                if (eventsResponse.data && eventsResponse.data.length > 0) {
                  const newCount = eventsResponse.data.length;
                  const newEvent: SensorEvent = eventsResponse.data[newCount - 1];
                  const prevData = prevSensorData[sensor.id];
                  const ping = prevData ? newCount !== prevData.count : false;
                  updatedData[sensor.id] = { event: newEvent, count: newCount, ping };
                }
              } catch (err) {
                console.error(err);
              }
            })
        );
        return updatedData;
      });
    };

    fetchSensorData();
    const interval = setInterval(fetchSensorData, 3000);
    return () => clearInterval(interval);
  }, [sensorLocations]);

  if (loadError) return <div>Error loading map</div>;
  if (!isLoaded || sensorsLoading) return <div>Loading map...</div>;

  return (
      <GoogleMap
          onLoad={onLoad}
          onIdle={onIdle}
          mapContainerStyle={mapContainerStyle}
          zoom={zoom}
          center={center}
          options={options}
      >
        {sensorLocations.map((sensor) => (
            <SensorMarker
                key={sensor.id}
                sensor={sensor}
                data={sensorData[sensor.id]}
                zoom={zoom}
                onHover={(sensor, data) => setHoveredSensor({ sensor, data })}
                onLeave={() => setHoveredSensor(null)}
            />
        ))}

        {hoveredSensor && (
            <OverlayView
                position={hoveredSensor.sensor.location}
                mapPaneName="overlayMouseTarget"
                getPixelPositionOffset={(width, height) => ({
                  x: -(width / 2),
                  y: -height - 10,
                })}
            >
                  <div
                      style={{
                        background: "white",
                        padding: "5px 8px",
                        borderRadius: "3px",
                        width: "200px",
                        boxShadow: "0 1px 2px rgba(0,0,0,0.3)",
                        whiteSpace: "nowrap",
                      }}
                  >
                    <p style={{ margin: 0, fontWeight: "bold" }}>
                      Sensor ID: {hoveredSensor.sensor.id}
                    </p>
                    {hoveredSensor.data && hoveredSensor.data.event ? (
                        <div style={{ fontSize: "1.2em" }}>
                          <p style={{ margin: "2px 0" }}>
                            <span style={{ fontWeight: 500 }}>Time:</span>{" "}
                            {new Date(hoveredSensor.data.event.timestamp).toLocaleString()}
                          </p>
                          <p style={{ margin: "2px 0" }}>
                            <span style={{ fontWeight: 500 }}>Temp:</span>{" "}
                            {hoveredSensor.data.event.temperature.toFixed(2)}°C
                          </p>
                          <p style={{ margin: "2px 0" }}>
                            <span style={{ fontWeight: 500 }}>Vibration:</span>{" "}
                            {hoveredSensor.data.event.vibration.toFixed(2)}
                          </p>
                          <p style={{ margin: "2px 0" }}>
                            <span style={{ fontWeight: 500 }}>Voltage:</span>{" "}
                            {hoveredSensor.data.event.voltage.toFixed(2)}V
                          </p>
                          {hoveredSensor.data.event.anomaly_flag === 1 && hoveredSensor.data.event.anomaly_type !== "trend" && (
                          <p style={{ margin: "2px 0" }}>
                            <span style={{ fontWeight: 500 }}>Anomaly:</span>{" "}
                            {hoveredSensor.data.event.anomaly_type}
                          </p>
                              )}
                        </div>
                    ) : (
                        <p style={{ margin: 0 }}>No event data available</p>
                    )}
                  </div>
            </OverlayView>
        )}
      </GoogleMap>
  );
}
