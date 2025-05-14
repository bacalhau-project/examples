// Component for rendering job tables
import {Download} from "lucide-react"
import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card"
import {Button} from "@/components/ui/button"
import type {Satellite} from "@/types"

type JobTableProps = {
    title: string
    headerColor: string
    files: string[]
    satelliteName: string
}

interface RawJob {
    ID: string;
    Name: string;
    Labels?: Record<string, string>;
    Meta?: Record<string, string>;
}

export function JobTable({ title, headerColor, satelliteName, files }: JobTableProps) {
    const isLow = title === 'Low bandwidth';
    const bandwidth = isLow ? 'LOW_bandwidth' : 'HIGH_bandwidth';

    return (
        <Card className="border shadow-md">
            <CardHeader className="py-2 px-3" style={{ backgroundColor: headerColor, color: "white" }}>
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="overflow-visible">
                    <table className="min-w-full">
                        <thead className="bg-slate-100 border-b">
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Filename
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                Thumbnail
                            </th>
                            {!isLow && (
                                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Action
                                </th>
                            )}
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                        {files.map((file) => (
                            <tr
                                key={file}
                                className="hover:bg-slate-50 transition-colors"
                            >
                                {/* Filename */}
                                <td className="px-3 py-2 text-xs font-semibold">
                                    {file}
                                </td>

                                {/* Thumbnail + Hover Preview */}
                                <td className="px-3 py-2 text-xs relative group overflow-visible">
                                    <div
                                        className="w-8 h-8 bg-gray-100 flex items-center justify-center rounded-sm border border-slate-200 overflow-hidden">
                                        <img
                                            src={`/api/${satelliteName}-data/output/${bandwidth}/${file}`}
                                            alt={`${file} thumbnail`}
                                            className="max-w-full max-h-full object-contain cursor-pointer"
                                        />
                                    </div>

                                    {/* Tooltip preview */}
                                    <div
                                        className={`
                    pointer-events-none
                    opacity-0
                    group-hover:opacity-100
                    transition-opacity
                    absolute
                    top-1/2
                    ${isLow ? "left-full" : "right-full"}
                    ml-2
                    z-50
                    w-60
                    h-60
                    bg-white
                    p-1
                    rounded
                    shadow-lg
                    transform
                    -translate-y-1/2
                  `}
                                    >
                                        <div className="w-full h-full flex items-center justify-center">
                                            <img
                                                src={`/api/${satelliteName}-data/output/${bandwidth}/${file}`}
                                                alt={`${file} preview`}
                                                className="max-w-full max-h-full object-contain"
                                            />
                                        </div>
                                    </div>
                                </td>

                                {/* Download button only for High bandwidth */}
                                {!isLow && (
                                    <td className="px-3 py-2 text-xs">
                                        <Button size="sm" variant="outline"
                                                className="flex items-center gap-1 h-6 text-xs">
                                            <Download className="h-3 w-3"/>
                                        </Button>
                                    </td>
                                )}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </CardContent>
        </Card>
    )
}
