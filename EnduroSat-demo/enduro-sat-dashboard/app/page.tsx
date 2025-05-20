"use client"

import {useEffect, useState} from "react"
import {useSatellitesNodes} from "@/hooks/useGetSatelites";
import {highJob, lowJob, shipDetectJob} from "@/jobs";
import {DetailSection} from "@/components/DetailsSection";
import {GroundStationPanel} from "@/components/GroundStationPanel";

// Define types
type ConnectionStatus = "No Connection" | "Low Bandwidth" | "High Bandwidth"
type DetailViewType = "satellite" | "ground-station" | null
type Job = {
  id: string
  name: string
  priority: "low" | "high" | "todo"
  satelliteId: number
  thumbnail: string
}

const openNetwork = async (satelitte: string, status: ConnectionStatus, nodeStatus: "DISCONNECTED" | "CONNECTED", nodeIp: string) => {
  if(nodeStatus === 'DISCONNECTED') {
    try {
      const res = await fetch(
          `http://${nodeIp}:9123/open-network`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": "Bearer abrakadabra1234!@#"
            },
            body: JSON.stringify({}),
          }
      );

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errorText}`);
      }

      const data = await res.json();
      console.log("Disable network:", data);
    } catch (err) {
      console.error("Error when disabling network:", err);
    }
  }
  try {
    const res = await fetch(
        `http://${nodeIp}:9123/set-bandwidth`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer abrakadabra1234!@#"
          },
          body: JSON.stringify({"value": status === 'High Bandwidth' ? "HIGH": "LOW" }),
        }
    );

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errorText}`);
    }

    const data = await res.json();
    console.log("Disable network:", data);
  } catch (err) {
    console.error("Error when disabling network:", err);
  }
}

const disableNetwork = async (satelitte: string, nodeIp: string) => {
    try {
      const res = await fetch(
          `http://${nodeIp}:9123/close-network`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": "Bearer abrakadabra1234!@#"
            },
            body: JSON.stringify({}),
          }
      );

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errorText}`);
      }

      const data = await res.json();
      console.log("Disable network:", data);
    } catch (err) {
      console.error("Error when disabling network:", err);
    }
}
export const colorMap: Record<string, string> = {
  node1: '#E57373',
  node2: '#64B5F6',
  node3: '#81C784',
  node4: '#FFB74D',
  node5: '#BA68C8',
};
export default function Dashboard() {
  const [connections, setConnections] = useState<Record<string, ConnectionStatus>>({})
  const { data: satellites, isLoading } = useSatellitesNodes()

  useEffect(() => {
    const initial: Record<string, ConnectionStatus> = satellites && satellites.reduce((acc, node) => {
      acc[node.Info.NodeID] =
          node.ConnectionState.Status === 'CONNECTED'
              ? 'Low Bandwidth'
              : 'No Connection'
      return acc
    }, {})

    setConnections(initial)
  }, [satellites])

  const [selectedItem, setSelectedItem] = useState<{ type: DetailViewType; id: string }>({
    type: null,
    id: '',
  })

  const handleConnectionChange = (satelliteId: string, status: ConnectionStatus, nodeStatus: 'CONNECTED' | 'DISCONNECTED', nodeIp: string) => {
    status === 'No Connection' ?  disableNetwork(satelliteId, nodeIp) : openNetwork(satelliteId, status, nodeStatus, nodeIp)
    setConnections((prev) => ({
      ...prev,
      [satelliteId]: status,
    }))
  }

  const handleItemSelect = (type: DetailViewType, id: string) => {
    setSelectedItem({ type, id })
  }

    if (!satellites || !connections || isLoading) {
      return null
    }

    return (
        <div className="container mx-auto p-4 max-w-7xl">
          <GroundStationPanel
              satellites={satellites}
              connections={connections}
              selectedItem={selectedItem}
              onItemSelect={handleItemSelect}
          />

          <DetailSection selectedItem={selectedItem} satellites={satellites} connections={connections} onConnectionChange={handleConnectionChange} />
        </div>
    )
}
