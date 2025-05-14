"use client"

import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
import type {ConnectionStatus, Job, Satellite, SelectedItem} from "@/types"
import {SatelliteTable} from "@/components/SateliteTable";
import {useJobs} from "@/hooks/useGetJobs";
import {BucketTable} from "@/components/BucketTable";

type DetailSectionProps = {
    selectedItem: SelectedItem
    satellites: Satellite[]
    jobs: Job[]
    connections: { [key: number]: ConnectionStatus }
    onConnectionChange: (satelliteId: number, status: ConnectionStatus) => void
}
const colorMap: Record<string, string> = {
    node1: '#E57373',
    node2: '#64B5F6',
    node3: '#81C784',
    node4: '#FFB74D',
    node5: '#BA68C8',
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
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/*<QueueTable*/}
                        {/*    title="Queue"*/}
                        {/*    headerColor="#1e293b" // slate-800WWW*/}
                        {/*    satellites={satellites}*/}
                        {/*    jobs={jobs && jobs.Items}*/}
                        {/*/>*/}
                        <BucketTable title={'Low bandwidth'} headerColor={"#d97706"}/>
                        <BucketTable title={'High bandwidth'} headerColor={"#dc2626"} />
                    </div>
                ) : (
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
