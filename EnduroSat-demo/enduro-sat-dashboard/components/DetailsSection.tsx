"use client"

// Component for rendering the detail section
import { Play } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { Job, Satellite, SelectedItem } from "@/types"
import { JobTable } from "./JobTable"

type DetailSectionProps = {
    selectedItem: SelectedItem
    satellites: Satellite[]
    jobs: Job[]
    onStartJob: (satelliteId: number) => void
}
const colorMap: Record<string, string> = {
    node1: '#E57373',  // czerwony
    node2: '#64B5F6',  // niebieski
    node3: '#81C784',  // zielony
    node4: '#FFB74D',  // pomarańczowy
    node5: '#BA68C8',  // fioletowy
};

export function DetailSection({ selectedItem, satellites, onStartJob }: DetailSectionProps) {
    if (!selectedItem.type) return null

    const getSelectedSatelliteColor = () => {
        if (selectedItem.type === "satellite" && selectedItem.id) {
            const satellite = satellites?.find((s) => s.Info.NodeID === selectedItem.id) ?? null
            return satellite ? colorMap[satellite.Info.NodeID] : undefined
        }
        return undefined
    }

    return (
        <Card
            className="mb-8 overflow-hidden border-0 shadow-lg transition-all"
            style={{
                backgroundColor: selectedItem.type === "satellite" ? `${getSelectedSatelliteColor()}10` : undefined,
            }}
        >
            <CardHeader
                className="py-3 px-4 border-b"
                style={{
                    backgroundColor: selectedItem.type === "satellite" ? `${getSelectedSatelliteColor()}20` : undefined,
                }}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        {selectedItem.type === "satellite" && selectedItem.id && (
                            <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: getSelectedSatelliteColor() }}></div>
                        )}
                        <CardTitle className="text-base">
                            {selectedItem.type === "ground-station"
                                ? "Ground Station Details"
                                : `Satellite ${selectedItem.id} Details`}
                        </CardTitle>
                    </div>

                    {/* Add Start Job button only for satellite details */}
                    {selectedItem.type === "satellite" && selectedItem.id && (
                        <Button
                            variant="default"
                            size="sm"
                            className="flex items-center gap-1"
                            onClick={() => onStartJob(selectedItem.id!)}
                        >
                            <Play className="h-3.5 w-3.5" />
                            <span>Start Job</span>
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent className="p-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* First Table: To Do or Queue */}
                    <JobTable
                        title={selectedItem.type === "ground-station" ? "Queue" : "To Do"}
                        headerColor="#1e293b" // slate-800
                        satellites={satellites}
                        showSatelliteColumn={selectedItem.type === "ground-station"}
                        nodeName={selectedItem.id}
                        statuses={['Job Submitted', 'Running']}
                    />

                    {/* Second Table: Low Priority */}
                    <JobTable
                        title="Low Priority"
                        headerColor="#d97706" // amber-600
                        satellites={satellites}
                        nodeName={selectedItem.id}
                        jobName={'data-transfer-low'}
                        statuses={['Completed']}
                    />

                    {/* Third Table: High Priority */}
                    <JobTable
                        title="High Priority"
                        headerColor="#dc2626" // red-600
                        satellites={satellites}
                        nodeName={selectedItem.id}
                        jobName={'data-transfer-high'}
                        statuses={['Completed']}
                    />
                </div>
            </CardContent>
        </Card>
    )
}
