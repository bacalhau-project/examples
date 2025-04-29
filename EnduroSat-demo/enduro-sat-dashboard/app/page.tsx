"use client"

import {useEffect, useState } from "react"
import { Antenna, Satellite, Download, Wifi, WifiOff, WifiHigh, Play } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {useSatellitesNodes} from "@/hooks/useGetSatelites";
import {highJob, lowJob, shipDetectJob} from "@/jobs";
import {JobModal} from "@/components/JobModal";
import {DetailSection} from "@/components/DetailsSection";

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

export default function Dashboard() {
  // Satellites data
  const [connections, setConnections] = useState<Record<string, ConnectionStatus>>({})
  const { data: satellites, isLoading, error } = useSatellitesNodes()
  const [jobModalOpen, setJobModalOpen] = useState(false)
  const [selectedJobType, setSelectedJobType] = useState<string | null>(null)

  const colorMap: Record<string, string> = {
    node1: '#E57373',  // czerwony
    node2: '#64B5F6',  // niebieski
    node3: '#81C784',  // zielony
    node4: '#FFB74D',  // pomarańczowy
    node5: '#BA68C8',  // fioletowy
  };

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

  // Get connection status color
  const getStatusColor = (status: ConnectionStatus) => {
    switch (status) {
      case "No Connection":
        return "#1a352b"
      case "Low Bandwidth":
        return "#f59e0b"
      case "High Bandwidth":
        return "#ed0000"
      default:
        return "#6b7280"
    }
  }

  // Get connection status icon
  const getStatusIcon = (status: ConnectionStatus) => {
    switch (status) {
      case "No Connection":
        return <WifiOff className="h-3 w-3 mr-1" />
      case "Low Bandwidth":
        return <WifiHigh className="h-3 w-3 mr-1" />
      case "High Bandwidth":
        return <Wifi className="h-3 w-3 mr-1" />
      default:
        return null
    }
  }

  // Calculate optimal label position
  const calculateLabelPosition = (angle: number, radius: number) => {
    // Position the label at 40% of the distance from center to satellite
    const labelDistanceRatio = 0.4
    const labelRadius = radius * labelDistanceRatio

    // Calculate base position
    let x = Math.cos(angle) * labelRadius
    let y = Math.sin(angle) * labelRadius

    // Adjust position based on quadrant to improve visibility
    // Add slight offset to avoid overlapping with the line
    const quadrantOffset = 20

    // Right side (positive x)
    if (x > 0) {
      x += quadrantOffset
    }
    // Left side (negative x)
    else if (x < 0) {
      x -= quadrantOffset
    }

    // Bottom half (positive y)
    if (y > 0) {
      y += quadrantOffset / 2
    }
    // Top half (negative y)
    else if (y < 0) {
      y -= quadrantOffset / 2
    }

    return { x, y }
  }

  const handleStartJob = (satelliteId: number) => {
    setJobModalOpen(true)
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

    // Calculate optimal satellite name label position
    const calculateNameLabelPosition = (angle: number) => {
      // Determine the quadrant and position the label accordingly
      // This ensures labels are positioned away from the center and don't overlap

      // Determine quadrant (1: top-right, 2: top-left, 3: bottom-left, 4: bottom-right)
      let quadrant = 1
      if (angle >= Math.PI / 2 && angle < Math.PI) quadrant = 2
      else if (angle >= Math.PI && angle < (3 * Math.PI) / 2) quadrant = 3
      else if (angle >= (3 * Math.PI) / 2) quadrant = 4

      // Set position based on quadrant
      let position = {x: 0, y: 0, align: "center" as const}

      switch (quadrant) {
        case 1: // top-right
          position = {x: 40, y: -5, align: "left"}
          break
        case 2: // top-left
          position = {x: -20, y: -5, align: "right"}
          break
        case 3: // bottom-left
          position = {x: -20, y: 20, align: "right"}
          break
        case 4: // bottom-right
          position = {x: 40, y: 20, align: "left"}
          break
      }

      return position
    }
    if (!satellites || !connections || isLoading) {
      return null
    }

    return (
        <div className="container mx-auto p-4 max-w-7xl">
          {/* Ground Station Panel */}
          <Card className="mb-8 overflow-hidden border-2 shadow-lg">
            <CardContent className="p-0">
              <div
                  className="relative h-[400px] flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100">
                {/* Ground Station */}
                <div
                    className={cn(
                        "absolute z-20 cursor-pointer p-3 bg-white rounded-full shadow-md transition-all border border-slate-200 hover:shadow-lg",
                        selectedItem.type === "ground-station" ? "ring-1 ring-primary ring-offset-1" : "",
                    )}
                    onClick={() => handleItemSelect("ground-station", null)}
                >
                  <Antenna className="h-6 w-6 text-slate-800"/>
                </div>

                {/* Connection Lines Container */}
                <div className="absolute inset-0 z-10">
                  {satellites.map((satellite, index) => {
                    // Calculate position in a circle
                    const angle = index * ((2 * Math.PI) / satellites.length)
                    const radius = 180 // Increased radius for more distance from ground station
                    const x = Math.cos(angle) * radius
                    const y = Math.sin(angle) * radius

                    // Calculate center point
                    const centerX = "50%"
                    const centerY = "50%"

                    // Determine line style based on connection status
                    let strokeDasharray = ""
                    const lineColor = getStatusColor(connections[satellite.Info.NodeID])

                    switch (connections[satellite.Info.NodeID]) {
                      case "No Connection":
                        strokeDasharray = "3,3"
                        break
                      case "Low Bandwidth":
                        strokeDasharray = "6,3"
                        break
                      case "High Bandwidth":
                        strokeDasharray = ""
                        break
                    }

                    return (
                        <svg
                            key={`line-${satellite.Info.NodeID}`}
                            className="absolute inset-0 w-full h-full"
                            style={{overflow: "visible"}}
                        >
                          <line
                              x1={centerX}
                              y1={centerY}
                              x2={`calc(${centerX} + ${x}px)`}
                              y2={`calc(${centerY} + ${y}px)`}
                              stroke={lineColor}
                              strokeWidth="1.5"
                              strokeDasharray={strokeDasharray}
                          />
                        </svg>
                    )
                  })}
                </div>

                {/* Satellites */}
                {satellites.map((satellite, index) => {
                  // Calculate position in a circle
                  const angle = index * ((2 * Math.PI) / satellites.length)
                  const radius = 180 // Increased radius for more distance from ground station
                  const x = Math.cos(angle) * radius
                  const y = Math.sin(angle) * radius

                  // Calculate optimized label position
                  const labelPos = calculateLabelPosition(angle, radius)

                  // Calculate optimized name label position
                  const nameLabelPos = calculateNameLabelPosition(angle)

                  // Determine status color
                  const statusColor = getStatusColor(connections[satellite.Info.NodeID])
                  const statusIcon = getStatusIcon(connections[satellite.Info.NodeID])

                  return (
                      <div key={satellite.Info.NodeID}>
                        {/* Satellite */}
                        <div
                            className="absolute z-20"
                            style={{
                              left: "50%",
                              top: "50%",
                              transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
                            }}
                        >
                          <div
                              className={cn(
                                  "p-2 rounded-full cursor-pointer transition-all shadow-sm border border-white hover:shadow-md",
                                  selectedItem.type === "satellite" && selectedItem.id === satellite.Info.NodeID
                                      ? "ring-1 ring-primary ring-offset-1"
                                      : "",
                              )}
                              style={{backgroundColor: colorMap[satellite.Info.NodeID]}}
                              onClick={() => handleItemSelect("satellite", satellite.Info.NodeID)}
                          >
                            <Satellite className="h-4 w-4 text-white"/>
                          </div>

                          {/* Satellite Name - Improved positioning */}
                          <div
                              className="absolute bg-white rounded-sm shadow-sm px-2 py-0.5 border border-slate-100"
                              style={{
                                left: nameLabelPos.x,
                                top: nameLabelPos.y,
                                textAlign: nameLabelPos.align,
                                transform: nameLabelPos.align === "right" ? "translateX(-100%)" : "",
                                whiteSpace: "nowrap",
                              }}
                          >
                            <span className="text-xs font-medium text-slate-700">{satellite.Info.NodeID}</span>
                          </div>
                        </div>

                        {/* Connection Label - Dynamically positioned */}
                        <div
                            className="absolute z-20"
                            style={{
                              left: "50%",
                              top: "50%",
                              transform: `translate(calc(-50% + ${labelPos.x}px), calc(-50% + ${labelPos.y}px))`,
                            }}
                        >
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs font-medium shadow-sm border h-6 px-2 whitespace-nowrap"
                                  style={{
                                    borderColor: statusColor,
                                    color: statusColor,
                                    backgroundColor: "white",
                                    borderRadius: "2px",
                                  }}
                              >
                                {statusIcon}
                                <span>{connections[satellite.Info.NodeID]}</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent>
                              <DropdownMenuItem
                                  onClick={() => handleConnectionChange(satellite.Info.NodeID, "High Bandwidth", satellite.Info.Labels.PUBLIC_IP)}>
                                <Wifi className="h-3.5 w-3.5 mr-2"/>
                                High Bandwidth
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                  onClick={() => handleConnectionChange(satellite.Info.NodeID, "Low Bandwidth", satellite.Info.Labels.PUBLIC_IP)}>
                                <WifiHigh className="h-3.5 w-3.5 mr-2"/>
                                Low Bandwidth
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                  onClick={() => handleConnectionChange(satellite.Info.NodeID, "No Connection", satellite.Info.Labels.PUBLIC_IP)}>
                                <WifiOff className="h-3.5 w-3.5 mr-2"/>
                                No Connection
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
          <DetailSection selectedItem={selectedItem} satellites={satellites} jobs={jobs} onStartJob={handleStartJob}/>
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
