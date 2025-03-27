"use client"

import React, {memo, useMemo} from "react"
import {Network,} from "lucide-react"
import {NodesList} from "@/components/NodesList"
import FilesGrid from "./components/FilesGrid"
import useFetchNodes from "@/hooks/useFetchNodes";
import {ClearMetadataButton} from "@/components/ClearMetadataButton";
import {NodeProps} from "@/lib/JobProvider";

// -----------------------------------------
// Header Component (Memoized)
// -----------------------------------------
const HeaderComponent = React.memo(({ nodes }: {nodes: NodeProps[]}) => {
    return (
        <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-16 items-center justify-between">
                <div className="flex items-center gap-2 font-semibold">
                    <Network className="h-6 w-6" />
                    <span>Edge Data Transfer Demo</span>
                </div>
                <ClearMetadataButton nodes={nodes} />
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
            <NodesList />
            <FilesGrid />
        </div>
    )
})

// -----------------------------------------
// Main Dashboard Component
// -----------------------------------------
export default function EdgeDataTransferDashboard() {
  const { nodes } = useFetchNodes()
  const memoizedNodes = useMemo(() => nodes, [nodes])
  return (
      <div className="flex min-h-screen flex-col bg-gray-50">
        <HeaderComponent nodes={memoizedNodes}/>
        <main className="flex-1 container py-6">
            <OverviewTab  />
        </main>
      </div>
  )
}
