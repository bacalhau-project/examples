"use client"

import {Fragment, useState} from "react"
import {Button} from "@/components/ui/button"
import {Card, CardContent} from "@/components/ui/card"
import {ChevronDown, ChevronUp, Wifi, WifiHigh as WifiLow, WifiOff} from "lucide-react"
import type {ConnectionStatus, Satellite} from "@/types"
import {cn} from "@/lib/utils"
import {colorMap} from "@/app/page";
import {ProcessingJobsTable} from "@/components/ProcessingJobsTable";
import { FilesToProcessTable} from "@/components/FilesToProcessTable";
import {FilesTable} from "@/components/FilesTables";

type SatelliteTableProps = {
    satellites: Satellite[]
    connections: { [key: number]: ConnectionStatus }
    onConnectionChange: (satelliteId: number, status: ConnectionStatus, nodeStatus: "CONNECTED" | "DISCONNECTED", ip: string) => void
    selectedSatelliteId: number | null
}

export function SatelliteTable({
                                   satellites,
                                   connections,
                                   onConnectionChange,
                                   selectedSatelliteId,
                               }: SatelliteTableProps) {
    const [expandedSatellites, setExpandedSatellites] = useState<number[]>([])

    const toggleExpand = (satelliteId: number) => {
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
                        {satellites.map((satellite) => {
                            const isExpanded = expandedSatellites.includes(satellite.Info.NodeID)
                            const satelliteId = satellite.Info.NodeID
                            const nodeStatus = satellite.ConnectionState.Status
                            const nodeIp = satellite.Info.Labels.PUBLIC_IP
                            return (
                                <Fragment key={satelliteId}>
                                    <tr
                                        key={satellite.id}
                                        className={cn(
                                            "hover:bg-slate-50 transition-colors",
                                            selectedSatelliteId === satelliteId ? "bg-slate-50" : "",
                                        )}
                                    >
                                        <td className="px-4 py-3 whitespace-nowrap">
                                            <button
                                                onClick={() => toggleExpand(satelliteId)}
                                                className="text-slate-500 hover:text-slate-700 transition-colors"
                                            >
                                                {isExpanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                                            </button>
                                        </td>
                                        <td className="px-4 py-3 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: colorMap[satelliteId] }}></div>
                                                <span className="text-sm font-medium text-slate-900">{satellite.Info.Labels.SATTELITE_NAME}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-700">{'Yolo'}</td>
                                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                                            <div className="flex space-x-2">
                                                <Button
                                                    size="sm"
                                                    variant={connections[satelliteId] === "No Connection" ? "default" : "outline"}
                                                    className="h-7 text-xs"
                                                    onClick={() => onConnectionChange(satelliteId , "No Connection", nodeStatus, nodeIp)}
                                                >
                                                    <WifiOff className="h-3 w-3 mr-1" />
                                                    Disable connection
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant={connections[satelliteId] === "Low Bandwidth" ? "default" : "outline"}
                                                    className="h-7 text-xs"
                                                    onClick={() => onConnectionChange(satelliteId , "Low Bandwidth", nodeStatus, nodeIp)}
                                                >
                                                    <WifiLow className="h-3 w-3 mr-1" />
                                                    Low Bandwidth
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant={connections[satelliteId] === "High Bandwidth" ? "default" : "outline"}
                                                    className="h-7 text-xs"
                                                    onClick={() => onConnectionChange(satelliteId, "High Bandwidth", nodeStatus, nodeIp)}
                                                >
                                                    <Wifi className="h-3 w-3 mr-1" />
                                                    High Bandwidth
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                    {isExpanded && (
                                        <tr>
                                            <td colSpan={4} className="p-0 bg-slate-50 border-b">
                                                <div className="p-4">
                                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                                        <ProcessingJobsTable
                                                            satellites={satellites}
                                                        />
                                                        <FilesToProcessTable satelliteName={satelliteId}/>
                                                        <FilesTable
                                                            title="Low bandwidth"
                                                            headerColor="#d97706" // amber-600
                                                            satelliteName={satelliteId}
                                                        />
                                                        <FilesTable
                                                            title="High bandwidth"
                                                            headerColor="#dc2626" // red-600
                                                            satelliteName={satelliteId}
                                                        />
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            )
                        })}
                        </tbody>
                    </table>
                </div>
            </CardContent>
        </Card>
    )
}
