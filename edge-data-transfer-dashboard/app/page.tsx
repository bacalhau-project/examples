"use client"

import EdgeDataTransferDashboard from "../dashboard"
import {NodeProvider} from "@/lib/NodeProvider";
import {JobsProvider} from "@/lib/JobProvider";

export default function SyntheticV0PageForDeployment() {
  return (<NodeProvider>
    <JobsProvider>
    <EdgeDataTransferDashboard />
    </JobsProvider>
  </NodeProvider>)
}
