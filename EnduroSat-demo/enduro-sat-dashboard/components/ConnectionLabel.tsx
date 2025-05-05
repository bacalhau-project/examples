"use client"

// Component for rendering connection status labels
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Wifi, WifiOff, WifiOffIcon as WifiLow } from "lucide-react"
import type { ConnectionStatus, Satellite } from "@/types"
import { getStatusColor } from "@/utils/status-helpers"

type ConnectionLabelProps = {
    satellite: Satellite
    position: { x: number; y: number }
    connectionStatus: ConnectionStatus
    onConnectionChange: (satelliteId: number, status: ConnectionStatus) => void
}

export const getStatusIcon = (status: ConnectionStatus) => {
    switch (status) {
        case "No Connection":
            return <WifiOff className="h-3 w-3 mr-1" />
        case "Low Bandwidth":
            return <WifiLow className="h-3 w-3 mr-1" />
        case "High Bandwidth":
            return <Wifi className="h-3 w-3 mr-1" />
        default:
            return null
    }
}
export function ConnectionLabel({ satellite, position, connectionStatus, onConnectionChange }: ConnectionLabelProps) {
    const statusColor = getStatusColor(connectionStatus)
    const statusIcon = getStatusIcon(connectionStatus)

    return (
        <div
            className="absolute z-20"
            style={{
                left: position.x,
                top: position.y -20,
                transform: "translate(-50%, -50%)",
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
                        <span>{connectionStatus}</span>
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                    <DropdownMenuItem onClick={() => onConnectionChange(satellite.Info.NodeID, "High Bandwidth")}>
                        <Wifi className="h-3.5 w-3.5 mr-2" />
                        High Bandwidth
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onConnectionChange(satellite.Info.NodeID, "Low Bandwidth")}>
                        <WifiLow className="h-3.5 w-3.5 mr-2" />
                        Low Bandwidth
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onConnectionChange(satellite.Info.NodeID, "No Connection")}>
                        <WifiOff className="h-3.5 w-3.5 mr-2" />
                        No Connection
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}
