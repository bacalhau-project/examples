"use client"

import {useState} from "react"
import {Card, CardContent} from "@/components/ui/card"
import type {ConnectionStatus, Satellite} from "@/types"
import {SatelliteRow} from "@/components/SatelliteRow";

type SatelliteTableProps = {
    satellites: Satellite[]
    connections: { [key: number]: ConnectionStatus }
    onConnectionChange: (satelliteId: number, status: ConnectionStatus, nodeStatus: "CONNECTED" | "DISCONNECTED", ip: string) => void
    selectedSatelliteId: string | null
}

export function SatelliteTable({
                                   satellites,
                                   connections,
                                   onConnectionChange,
                                   selectedSatelliteId,
                               }: SatelliteTableProps) {
    const [expandedSatellites, setExpandedSatellites] = useState<string[]>([])

    const toggleExpand = (satelliteId: string) => {
        setExpandedSatellites((prev) =>
            prev.includes(satelliteId) ? prev.filter((id) => id !== satelliteId) : [...prev, satelliteId],
        )
    }

    return (
        <Card className="border shadow-md">
            <CardContent className="p-0">
                <div className="overflow-hidden">
                    <table className="min-w-full">
                        <thead className="bg-slate-100 border-b">
                        <tr>
                            <th className="w-10 px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider"></th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Satellite
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Model
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Connection Control
                            </th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                        {satellites.map((satellite: Satellite) => {
                               const isExpanded = expandedSatellites.includes(satellite.Info.NodeID)
                               const satelliteId = satellite.Info.NodeID
                               const nodeStatus = satellite.ConnectionState.Status
                               const nodeIp = satellite.Info.Labels.PUBLIC_IP
                               return <SatelliteRow
                                    satellite={satellite}
                                    satellites={satellites}
                                    satelliteId={satelliteId}
                                    onConnectionChange={onConnectionChange}
                                    connections={connections}
                                    selectedSatelliteId={selectedSatelliteId}
                                    nodeIp={nodeIp}
                                    nodeStatus={nodeStatus}
                                    isExpanded={isExpanded}
                                    toggleExpand={toggleExpand}
                                />
                            }
                        )}
                        </tbody>
                    </table>
                </div>
            </CardContent>
        </Card>
    )
}
