"use client"

// Component for rendering the ground station panel
import {useEffect, useRef, useState} from "react"
import {Antenna} from "lucide-react"
import {Card, CardContent} from "@/components/ui/card"
import {cn} from "@/lib/utils"
import type {ConnectionStatus, Satellite, SelectedItem} from "@/types"
import {SatelliteComponent} from "./SatelliteComponent"
import {ConnectionLine} from "./ConnectionLine"
import {calculateSatellitePosition} from "@/utils/calculations"

type GroundStationPanelProps = {
    satellites: Satellite[]
    connections: { [key: number]: ConnectionStatus }
    selectedItem: SelectedItem
    onItemSelect: (type: "satellite" | "ground-station" | null, id: number | null) => void
    onConnectionChange: (satelliteId: number, status: ConnectionStatus) => void
}

// Adjust paddings and improve the layout
export function GroundStationPanel({
                                       satellites,
                                       connections,
                                       selectedItem,
                                       onItemSelect,
                                       onConnectionChange,
                                   }: GroundStationPanelProps) {
    const panelRef = useRef<HTMLDivElement>(null)
    const [panelWidth, setPanelWidth] = useState(0)

    // Ground station dimensions
    const groundStationWidth = 160
    const groundStationHeight = 50

    // Update panel width on resize
    useEffect(() => {
        if (panelRef.current) {
            setPanelWidth(panelRef.current.offsetWidth)

            const handleResize = () => {
                if (panelRef.current) {
                    setPanelWidth(panelRef.current.offsetWidth)
                }
            }

            window.addEventListener("resize", handleResize)
            return () => window.removeEventListener("resize", handleResize)
        }
    }, [])

    return (
        <Card className="mb-8 overflow-hidden border-0 shadow-lg">
            <CardContent className="p-0">
                <div
                    ref={panelRef}
                    className="relative h-[350px] flex items-center justify-center bg-gradient-to-b from-sky-300 to-sky-100"
                >
                    {/* Ground Station - Now a rectangle at the bottom */}
                    <div
                        className={cn(
                            "absolute z-20 cursor-pointer bg-slate-800 rounded-md shadow-md transition-all border border-slate-700 hover:shadow-lg flex items-center justify-center px-4",
                            selectedItem.type === "ground-station" ? "ring-1 ring-primary ring-offset-1" : "",
                        )}
                        style={{
                            width: groundStationWidth,
                            height: groundStationHeight,
                            left: "50%",
                            bottom: "10px",
                            transform: "translateX(-50%)",
                        }}
                        onClick={() => onItemSelect("ground-station", null)}
                    >
                        <Antenna className="h-6 w-6 text-white mr-2" />
                        <span className="text-white text-sm font-medium">Ground Station</span>
                    </div>

                    {/* Connection Lines Container */}
                    <div className="absolute inset-0 z-10">
                        {satellites.map((satellite, index) => {
                            const satellitePos = calculateSatellitePosition(index, satellites.length, panelWidth)

                            // Ground station position
                            const groundStationPos = {
                                x: panelWidth / 2,
                                y: 350 - 30 - groundStationHeight, // Bottom of panel - margin - height
                                width: groundStationWidth,
                                height: groundStationHeight,
                            }
                            return (
                                <ConnectionLine
                                    key={`line-${satellite.Info.NodeID}`}
                                    satellite={satellite}
                                    satellitePosition={satellitePos}
                                    groundStationPosition={groundStationPos}
                                    connectionStatus={connections[satellite.Info.NodeID]}
                                    panelWidth={panelWidth}
                                />
                            )
                        })}
                    </div>

                    {/* Satellites */}
                    {satellites.map((satellite, index) => (
                        <SatelliteComponent
                            key={satellite.Info.NodeID}
                            satellite={satellite}
                            index={index}
                            totalSatellites={satellites.length}
                            connectionStatus={connections[satellite.Info.NodeID]}
                            selectedItem={selectedItem}
                            onItemSelect={onItemSelect}
                            onConnectionChange={onConnectionChange}
                            panelWidth={panelWidth}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}
