// Component for rendering job tables
import { Download } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { Job, Satellite } from "@/types"
import {useEffect, useState} from "react";

type JobTableProps = {
    title: string
    headerColor: string
    satellites?: Satellite[]
    showSatelliteColumn?: boolean
    nodeName?: string
    jobName?: string
    statuses?: string[]
}

interface RawJob {
    ID: string;
    Name: string;
    Labels?: Record<string, string>;
    Meta?: Record<string, string>;
}

function getJobsSummary(data, jobName, statuses) {
    let items = data.Items;
    if (jobName) {
        items = items.filter(j => j.Name === jobName);
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

export function JobTable({ title, headerColor, satellites, showSatelliteColumn = false, nodeName, jobName, statuses }: JobTableProps) {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState<boolean>(!!nodeName);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!nodeName) return;

        const fetchJobs = async () => {
            setLoading(true);
            setError(null);
            try {
                const params = new URLSearchParams({
                    labels: `sattelite_number=${encodeURIComponent(nodeName)}`,
                });
                const res = await fetch(`http://localhost:8438/api/v1/orchestrator/jobs?${params.toString()}`);
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status} – ${res.statusText}`);
                }
                const data: { Jobs: RawJob[] } = await res.json();
                const mapped = getJobsSummary(data, jobName, statuses);
                setJobs(mapped);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchJobs();
    }, [nodeName]);

    if (loading) {
        return <div>Loading jobs for node “{nodeName}”…</div>;
    }
    if (error) {
        return <div style={{ color: "red" }}>Error loading jobs: {error}</div>;
    }

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
                                {title === "Queue" || title === "To Do" ? "Job ID" : "Job Name"}
                            </th>
                            {showSatelliteColumn && (
                                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Satellite
                                </th>
                            )}
                            {title !== "Queue" && title !== "To Do" && (
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
                        {jobs.map((job) => (
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
                                    {title === "Queue" || title === "To Do" ? `${job.id} - ${job.name}` : job.id}
                                </td>
                                {/*{showSatelliteColumn && satellites && (*/}
                                {/*    <td className="px-3 py-2 text-xs">*/}
                                {/*        <div className="flex items-center">*/}
                                {/*            <div*/}
                                {/*                className="w-2 h-2 rounded-full mr-1"*/}
                                {/*                style={{*/}
                                {/*                    backgroundColor: satellites.find((s) => s.id === job.satelliteId)?.color,*/}
                                {/*                }}*/}
                                {/*            ></div>*/}
                                {/*            Sat-{job.satelliteId}*/}
                                {/*        </div>*/}
                                {/*    </td>*/}
                                {/*)}*/}

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
