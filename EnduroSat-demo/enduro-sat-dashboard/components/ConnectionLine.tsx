import type { ConnectionStatus } from "@/types"
import { getStatusColor } from "@/utils/status-helpers"

type ConnectionLineProps = {
    satellitePosition: { x: number; y: number }
    groundStationPosition: { x: number; y: number; width: number; height: number }
    connectionStatus: ConnectionStatus
}

export function ConnectionLine({
                                   satellitePosition,
                                   groundStationPosition,
                                   connectionStatus,
                               }: ConnectionLineProps) {
    let strokeDasharray = ""
    const lineColor = getStatusColor(connectionStatus)

    switch (connectionStatus) {
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

    // Calculate connection line start point (from ground station)
    const startX = groundStationPosition.x // Center of ground station
    const startY = groundStationPosition.y // Top of ground station

    return (
        <svg className="absolute inset-0 w-full h-full" style={{ overflow: "visible" }}>
            <line
                x1={startX}
                y1={startY + 20 }
                x2={satellitePosition.x}
                y2={satellitePosition.y + 20}
                stroke={lineColor}
                strokeWidth="1.5"
                strokeDasharray={strokeDasharray}
            />
        </svg>
    )
}
