"use client"

import React, {memo, useMemo} from "react"
import {HardDrive, Network,} from "lucide-react"
import {NodesList} from "@/components/NodesList"
import FilesGrid from "./components/FilesGrid"
import useFetchNodes from "@/hooks/useFetchNodes";
import {ClearMetadataButton} from "@/components/ClearMetadataButton";
import {NodeProps, useJobs} from "@/lib/JobProvider";

// -----------------------------------------
// Header Component (Memoized)
// -----------------------------------------
const HeaderComponent = React.memo(() => {
    const { nodes } = useFetchNodes()
    const {files} = useJobs()
    return (
        <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-16 items-center justify-between">
                <div className="flex items-center gap-2 font-semibold">
                    <Network className="h-6 w-6"/>
                    <span>Edge Data Transfer Demo</span>
                </div>
                <div className={"flex flex-row items-center gap-4"}>
                <div className={"flex flex-row items-center"}>
                    <div className="text-sm font-medium mr-2">Network Share:</div>
                    <div className="flex items-center justify-between p-2 gap-3 border rounded-md">
                        <div className="flex items-center gap-2">
                            <HardDrive className="h-4 w-4 text-muted-foreground"/>
                            <span>NFS Share</span>
                        </div>
                        <div className="text-sm text-muted-foreground">{files.length ?? 0}</div>
                    </div>
                </div>
                    <ClearMetadataButton nodes={nodes}/>
                </div>
            </div>
        </header>
    );
});

// -----------------------------------------
// Overview Tab Component (Memoized)
// -----------------------------------------
const OverviewTab = memo(() => {
    return (
        <div>
            <NodesList/>
            <FilesGrid/>
        </div>
    )
})

// -----------------------------------------
// Main Dashboard Component
// -----------------------------------------
export default function EdgeDataTransferDashboard() {

    return (
        <div className="flex min-h-screen flex-col bg-gray-50">
            <HeaderComponent/>
            <main className="flex-1 container py-6">
            <OverviewTab />
        </main>
      </div>
  )
}
