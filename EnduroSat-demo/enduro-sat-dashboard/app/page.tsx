"use client"

import {useEffect, useState} from "react"
import {useSatellitesNodes} from "@/hooks/useGetSatelites";
import {highJob, lowJob, shipDetectJob} from "@/jobs";
import {JobModal} from "@/components/JobModal";
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

const openNetwork = async (ip: string) => {
  try {
    const res = await fetch(
        `http://${ip}:9123/open-network`,
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

const disableNetwork = async (ip: string) => {
    try {
      const res = await fetch(
          `http://${ip}:9123/close-network`,
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
  node1: '#E57373',  // czerwony
  node2: '#64B5F6',  // niebieski
  node3: '#81C784',  // zielony
  node4: '#FFB74D',  // pomarańczowy
  node5: '#BA68C8',  // fioletowy
};
export default function Dashboard() {
  // Satellites data
  const [connections, setConnections] = useState<Record<string, ConnectionStatus>>({})
  const { data: satellites, isLoading, error } = useSatellitesNodes()
  const [jobModalOpen, setJobModalOpen] = useState(false)
  const [selectedJobType, setSelectedJobType] = useState<string | null>(null)



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

  // Sample jobs data
  const jobs: Job[] = []

  const [selectedItem, setSelectedItem] = useState<{ type: DetailViewType; id: string }>({
    type: null,
    id: '',
  })

  const handleConnectionChange = (satelliteId: string, status: ConnectionStatus, nodeIP: string) => {
    status === 'No Connection' ?  disableNetwork(nodeIP) : openNetwork(nodeIP)
    setConnections((prev) => ({
      ...prev,
      [satelliteId]: status,
    }))
  }

  // Handle item selection
  const handleItemSelect = (type: DetailViewType, id: string) => {
    setSelectedItem({ type, id })
  }

  // Handle job selection
  const handleJobSelection = (jobType: string) => {
    setSelectedJobType(jobType)
  }

  const jobPayloads = (nodeId: string) => ({
    DETECT_SHIP: shipDetectJob(nodeId),
    LOW_BANDWIDTH: lowJob(nodeId),
    HIGH_BANDWIDTH: highJob(nodeId),
  });

  // Handle job submission
  const handleJobSubmit = async () => {
    if (selectedItem.type === "satellite" && selectedItem.id && selectedJobType) {
      console.log(`Starting new job "${selectedJobType}" for Satellite ${selectedItem.id}`)
      const nodeId = selectedItem.id;
      const payload = jobPayloads(nodeId)[selectedJobType];
      if (!payload) {
        console.error(`Invalid job type: ${selectedJobType}`);
        return;
      }
      setJobModalOpen(false)
      setSelectedJobType(null)
      try {
        const res = await fetch(`http://localhost:8438/api/v1/orchestrator/jobs`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`HTTP ${res.status}: ${errorText}`);
        }

        const data = await res.json();
        console.log("Job created:", data);
      } catch (err) {
        console.error("Error creating job:", err);
      }
    }
  }
    if (!satellites || !connections || isLoading) {
      return null
    }

    return (
        <div className="container mx-auto p-4 max-w-7xl">
          {/* Ground Station Panel */}
          <GroundStationPanel
              satellites={satellites}
              connections={connections}
              selectedItem={selectedItem}
              onItemSelect={handleItemSelect}
          />

          <DetailSection selectedItem={selectedItem} satellites={satellites} connections={connections} onConnectionChange={handleConnectionChange} />
          <JobModal
              open={jobModalOpen}
              onOpenChange={setJobModalOpen}
              selectedJobType={selectedJobType}
              onJobSelection={handleJobSelection}
              onJobSubmit={handleJobSubmit}
          />
        </div>
    )
}
