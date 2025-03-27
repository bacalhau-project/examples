"use client";

import React from "react";
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,} from "@/components/ui/tooltip";
import {useJobs} from "@/lib/JobProvider";

interface Job {
    id: number;
    fileName: string;
    nodeId: string; // "0" means empty; otherwise the real NodeID from backend
    metaInvalid?: boolean;
}

const JobGrid = React.memo(({ jobs, nodeColorsMapping }: { jobs: Job[]; nodeColorsMapping: Record<string, string> }) => {
    return (
        <TooltipProvider>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(15.5px,1fr))] gap-1">
                {jobs.map((job) => (
                    <Tooltip key={job.id}>
                        <TooltipTrigger asChild>
                            <div
                                className={`h-4 w-4 ${nodeColorsMapping[job.nodeId]} ${job.metaInvalid ? "border border-blue-500" : ""} cursor-pointer transition-transform hover:scale-150`}
                            />
                        </TooltipTrigger>
                        <TooltipContent side="top">
                            <p>{job.fileName}</p>
                        </TooltipContent>
                    </Tooltip>
                ))}
            </div>
        </TooltipProvider>
    );
});

const FilesGrid = React.memo(function FilesGrid() {
    const {jobs, nodeColorsMapping} = useJobs()

    return (
        <div className="space-y-6 p-4">
            <JobGrid jobs={jobs} nodeColorsMapping={nodeColorsMapping} />
        </div>
    );
});

export default FilesGrid;
