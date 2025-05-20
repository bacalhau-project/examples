"use client"

import {SatelliteIcon} from "lucide-react"
import {cn} from "@/lib/utils"
import type {ConnectionStatus, Satellite, SelectedItem} from "@/types"
import {calculateLabelPosition, calculateNameLabelPosition, calculateSatellitePosition} from "@/utils/calculations"
import {colorMap} from "@/app/page";

type SatelliteComponentProps = {
    satellite: Satellite
    index: number
    totalSatellites: number
    connectionStatus: ConnectionStatus
    selectedItem: SelectedItem
    onItemSelect: (type: "satellite" | "ground-station" | null, id: number | null) => void
    onConnectionChange: (satelliteId: number, status: ConnectionStatus) => void
    panelWidth: number
}

export function SatelliteComponent({
                                       satellite,
                                       index,
                                       totalSatellites,
                                       selectedItem,
                                       onItemSelect,
                                       panelWidth,
                                   }: SatelliteComponentProps) {
    const satellitePos = calculateSatellitePosition(index, totalSatellites, panelWidth)
    const labelPos = calculateLabelPosition(index, totalSatellites, panelWidth)
    const nameLabelPos = calculateNameLabelPosition(index, totalSatellites, panelWidth)
    const satelliteName = satellite.Info.Labels.SATTELITE_NAME
    return (
        <div key={satellite.id}>
            {/* Satellite */}
            <div
                className="absolute z-20"
                style={{
                    left: satellitePos.x,
                    top: satellitePos.y + 30,
                    transform: "translate(-50%, -50%)",
                }}
            >
                <div
                    className={cn(
                        "p-2.5 rounded-full cursor-pointer transition-all shadow-md border border-white hover:shadow-lg",
                        selectedItem.type === "satellite" && selectedItem.id === satellite.Info.NodeID
                            ? "ring-2 ring-primary ring-offset-2"
                            : "",
                    )}
                    style={{ backgroundColor: colorMap[satelliteName] }}
                    onClick={() => onItemSelect("satellite", satellite.Info.NodeID)}
                >
                    <SatelliteIcon className="h-5 w-5 text-white" />
                </div>

                {/* Satellite Name - Above the satellite */}
                <div
                    className="absolute bg-white rounded-sm shadow-sm px-2 py-0.5 border border-slate-100"
                    style={{
                        left: "50%",
                        top: nameLabelPos.y -20,
                        transform: "translateX(-50%)",
                        whiteSpace: "nowrap",
                        textAlign: "center",
                    }}
                >
                    <span className="text-xs font-bold text-slate-700">{satelliteName}</span>
                </div>
            </div>
        </div>
    )
}
