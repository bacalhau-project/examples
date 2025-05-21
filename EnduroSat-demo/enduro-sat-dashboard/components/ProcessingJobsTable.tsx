import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
import type {Satellite} from "@/types"
import React from "react";
import {useJobs} from "@/hooks/useGetJobs";

type JobTableProps = {
    satellites?: Satellite[]
}

function getJobSummary(data, statuses) {
    if(!data || data.length === 0)
        return []
    let items = data

    if (Array.isArray(statuses) && statuses.length > 0) {
        items = items.filter(j =>
            j.State &&
            statuses.includes(j.State.StateType)
        );
    }

    return items.map(j => ({
        id: j.ID,
        name: j.Name,
        satelliteName: j.Labels.sattelite_number
    }));
}

export function ProcessingJobsTable({ satellites }: JobTableProps) {
    const {jobs, loading , error} = useJobs()
    const filteredJobs = getJobSummary(jobs?.Items, ['Running'])

    return (
        <Card className="border shadow-md">
            <CardHeader className="py-2 px-3" style={{ backgroundColor: "#1e293b", color: "white" }}>
                <CardTitle className="text-sm font-medium">Processing Jobs</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                {loading ? (
                    <div className="p-4 text-center text-sm text-slate-500">Loading…</div>
                ) : error ? (
                    <div className="p-4 text-center text-sm text-red-500">{error}</div>
                ) : jobs.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">
                        No jobs running
                    </div>
                ) : (
                <div className="overflow-hidden">
                    <table className="min-w-full">
                        <thead className="bg-slate-100 border-b">
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Job Name
                            </th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                        {filteredJobs.map((job) => {
                                return  (<tr
                                    key={job.id}
                                    className="hover:bg-slate-50 transition-colors"
                                    style={
                                        satellites
                                            ? {backgroundColor: `${satellites.find((s) => s.id === job.satelliteId)?.color}10`}
                                            : {}
                                    }
                                >
                                    <td className="px-3 py-2 text-xs font-medium">
                                        {job.name}
                                    </td>
                                </tr>
                                )
                        })}
                        </tbody>
                    </table>
                </div>
                    )}
            </CardContent>
        </Card>
    )
}
