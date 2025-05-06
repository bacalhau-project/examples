import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
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

function getJobSummary(data, jobName, statuses, satNames) {
    let items = data
    if (jobName) {
        items = items.filter(j => j.Name === jobName);
    }
    if (Array.isArray(statuses) && statuses.length > 0) {
        items = items.filter(j =>
            j.State &&
            statuses.includes(j.State.StateType)
        );
    }

    if (Array.isArray(satNames) && satNames.length > 0) {
        items = items.filter(j =>
            j.Labels &&
            satNames.includes(j.Labels.sattelite_number)
        );
    }

    return items.map(j => ({
        id: j.ID,
        name: j.Name,
        satelliteName: j.Labels.sattelite_number
    }));
}

export function QueueTable({ title, headerColor, satellites, jobs, jobName }: JobTableProps) {
    if(!jobs || jobs?.length === 0){
        return null
    }
    const satNames = satellites
        .map(s => s.Info?.Labels?.SATTELITE_NAME)
        .filter(Boolean);

    const filteredJobs = getJobSummary(jobs, jobName, ['Queued'], satNames)

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
                                Job ID
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Satellite
                            </th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                        {filteredJobs.map((job) => {
                              return  <tr
                                    key={job.id}
                                    className="hover:bg-slate-50 transition-colors"
                                    style={
                                        satellites
                                            ? {backgroundColor: `${satellites.find((s) => s.id === job.satelliteId)?.color}10`}
                                            : {}
                                    }
                                >
                                    <td className="px-3 py-2 text-xs font-medium">
                                        {job.id} - {job.name}
                                    </td>
                                    {satellites && (
                                        <td className="px-3 py-2 text-xs">
                                            <div className="flex items-center">
                                                <div
                                                    className="w-2 h-2 rounded-full mr-1"
                                                    style={{
                                                        backgroundColor: satellites.find((s) => s.id === job.satelliteId)?.color,
                                                    }}
                                                ></div>
                                                Sat-{job.satelliteName}
                                            </div>
                                        </td>
                                    )}
                                </tr>
                            }
                        )}
                        </tbody>
                    </table>
                </div>
            </CardContent>
        </Card>
    )
}
