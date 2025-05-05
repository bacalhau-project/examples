"use client"

// Component for rendering the detail section
import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
import type {ConnectionStatus, Job, Satellite, SelectedItem} from "@/types"
import {JobTable} from "./JobTable"
import {SatelliteTable} from "@/components/SateliteTable";

type DetailSectionProps = {
    selectedItem: SelectedItem
    satellites: Satellite[]
    jobs: Job[]
    connections: { [key: number]: ConnectionStatus }
    onConnectionChange: (satelliteId: number, status: ConnectionStatus) => void
}
const colorMap: Record<string, string> = {
    node1: '#E57373',  // czerwony
    node2: '#64B5F6',  // niebieski
    node3: '#81C784',  // zielony
    node4: '#FFB74D',  // pomarańczowy
    node5: '#BA68C8',  // fioletowy
};

export function DetailSection({ selectedItem, satellites, connections, onConnectionChange  }: DetailSectionProps) {
    if (!selectedItem.type) return null

    return (
        <Card
            className="mb-8 overflow-hidden border-0 shadow-lg transition-all"
            style={{
                backgroundColor: selectedItem.type === "satellite" ? `#1e293b10` : undefined,
            }}
        >
            <CardHeader
                className="py-3 px-4 border-b"
                style={{
                    backgroundColor: selectedItem.type === "satellite" ? `#1e293b` : undefined,
                }}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        {selectedItem.type === "satellite" && selectedItem.id && (
                            <div className="w-3 h-3 rounded-full mr-2"></div>
                        )}
                        <CardTitle
                            className={`text-base ${selectedItem.type === "satellite" ? "text-white" : ""}`}
                        >
                            {selectedItem.type === "ground-station"
                                ? "Ground Station Details"
                                : `Satellites control panel`}
                        </CardTitle>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-4">
                {selectedItem.type === "ground-station" ? (
                    /* Job Tables when ground station is selected */
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* First Table: Queue */}
                        <JobTable
                            title="Queue"
                            headerColor="#1e293b" // slate-800
                            satellites={satellites}
                            showSatelliteColumn={true}
                        />

                        {/* Second Table: Low Priority */}
                        <JobTable
                            title="Low Priority"
                            headerColor="#d97706" // amber-600
                            satellites={satellites}
                            showSatelliteColumn={true}
                        />

                        {/* Third Table: High Priority */}
                        <JobTable
                            title="High Priority"
                            headerColor="#dc2626" // red-600
                            satellites={satellites}
                            showSatelliteColumn={true}
                        />
                    </div>
                ) : (
                    /* Satellite Table for all other cases */
                    <SatelliteTable
                        satellites={satellites}
                        connections={connections}
                        onConnectionChange={onConnectionChange}
                        selectedSatelliteId={selectedItem.id}
                    />
                )}
            </CardContent>
        </Card>
    )
}
