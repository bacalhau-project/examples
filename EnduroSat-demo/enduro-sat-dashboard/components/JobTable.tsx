// Component for rendering job tables
import {Download} from "lucide-react"
import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
import {Button} from "@/components/ui/button"
import type {Satellite} from "@/types"

type JobTableProps = {
    title: string
    headerColor: string
    satellites?: Satellite[]
    showSatelliteColumn?: boolean
    nodeName?: string
    jobName?: string
    jobs: RawJob[]
    statuses?: string[]
}

interface RawJob {
    ID: string;
    Name: string;
    Labels?: Record<string, string>;
    Meta?: Record<string, string>;
}

function getJobsSummary(data, jobName, statuses, satNames) {
    let items = data;

    if (jobName) {
        items = items.filter(j => j.Name === jobName);
    }

    if (Array.isArray(satNames) && satNames.length > 0) {
        items = items.filter(j =>
            j.Labels &&
            satNames.includes(j.Labels.sattelite_number)
        );
    }

    if (Array.isArray(statuses) && statuses.length > 0) {
        items = items.filter(j =>
            j.State &&
            statuses.includes(j.State.StateType)
        );
    }

    return items.map(j => ({
        id: j.ID,
        name: j.Name,
    }));
}

export function JobTable({ title, headerColor, satellites, showSatelliteColumn = false, jobs, jobName, statuses = [] }: JobTableProps) {
    if (!jobs || jobs.length === 0) {
        return null;
    }

    // Collect all satellite names
    const satNames = satellites
        .map(s => s.Info?.Labels?.SATTELITE_NAME)
        .filter(Boolean);

    // Filter jobs by jobName, statuses, and matching any satellite
    const filteredJobs = getJobsSummary(jobs, jobName, statuses, satNames);

    return (
        <Card className="border shadow-md">
            <CardHeader className="py-2 px-3" style={{ backgroundColor: headerColor, color: "white" }}>
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="overflow-hidden">
                    <table className="min-w-full">
                        <thead className="bg-slate-100 border-b">
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                {title === "To Do" ? "Job ID" : "Job Name"}
                            </th>
                            {showSatelliteColumn && (
                                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Satellite
                                </th>
                            )}
                            {title !== "To Do" && (
                                <>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Thumbnail
                                    </th>
                                    {title === 'High Priority' && (
                                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Action
                                    </th>)}
                                </>
                            )}
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                        {filteredJobs.map((job) => (
                            <tr
                                key={job.id}
                                className="hover:bg-slate-50 transition-colors"
                                style={
                                    showSatelliteColumn && satellites
                                        ? { backgroundColor: `${satellites.find((s) => s.id === job.satelliteId)?.color}10` }
                                        : {}
                                }
                            >
                                <td className="px-3 py-2 text-xs font-medium">
                                    {title === "To Do" ? `${job.id} - ${job.name}` : job.id}
                                </td>

                                    <>
                                    {(title === 'High Priority' || title === 'Low Priority') && (
                                        <td className="px-3 py-2 text-xs">
                                            <img
                                                src={'./thumbnail.jpg'}
                                                alt={job.name}
                                                className="w-8 h-8 object-cover rounded-sm border border-slate-200"
                                            />
                                        </td>
                                    )}
                                        {title === 'High Priority' && (
                                        <td className="px-3 py-2 text-xs">
                                            <Button size="sm" variant="outline" className="flex items-center gap-1 h-6 text-xs">
                                                <Download className="h-3 w-3" />
                                            </Button>
                                        </td>
                                        )}
                                    </>

                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </CardContent>
        </Card>
    )
}
