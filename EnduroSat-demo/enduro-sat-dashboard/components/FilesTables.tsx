'use client';

import React, {useEffect, useState} from 'react';
import {Card, CardContent, CardHeader, CardTitle} from '@/components/ui/card';

type FilesProps = {
    title: 'Low bandwidth' | 'High bandwidth';
    headerColor: string;
    satelliteName: string;
};

export function FilesTable({ title, headerColor, satelliteName }: FilesProps) {
    const isLow = title === 'Low bandwidth';
    const bandwidth = isLow ? 'LOW_bandwidth' : 'HIGH_bandwidth';

    const [files, setFiles] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            const res = await fetch(`/api/${satelliteName}-data/output/${bandwidth}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: { images: string[] } = await res.json();
            setFiles(data.images);
            setError(null);
        } catch (err) {
            console.error(err);
            setError('Failed to load files');
        }
    };

    useEffect(() => {
        setLoading(true);
        setError(null);
        fetchData().finally(() => setLoading(false));

        const intervalId = setInterval(fetchData, 1000);

        return () => clearInterval(intervalId);
    }, [satelliteName, bandwidth]);

    return (
        <Card className="border shadow-md">
            <CardHeader
                className="py-2 px-3"
                style={{ backgroundColor: headerColor, color: 'white' }}
            >
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                {loading ? (
                    <div className="p-4 text-center text-sm text-slate-500">Loading…</div>
                ) : error ? (
                    <div className="p-4 text-center text-sm text-red-500">{error}</div>
                ) : files.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">
                        No files found.
                    </div>
                ) : (
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
                            </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200">
                            {files.map(file => (
                                <tr
                                    key={file}
                                    className="hover:bg-slate-50 transition-colors transition-opacity duration-200"
                                >
                                    <td className="px-3 py-2 text-xs font-semibold">{file}</td>

                                    <td className="px-3 py-2 text-xs relative group overflow-visible">
                                        <div className="w-8 h-8 bg-gray-100 flex items-center justify-center rounded-sm border border-slate-200 overflow-hidden">
                                            <img
                                                src={`/api/${satelliteName}-data/output/${bandwidth}/${file}`}
                                                alt={`${file} thumbnail`}
                                                className="max-w-full max-h-full object-contain cursor-pointer"
                                            />
                                        </div>
                                        <div
                                            className={`
                          pointer-events-none
                          opacity-0
                          group-hover:opacity-100
                          transition-opacity
                          absolute
                          top-1/2
                          ${isLow ? 'left-full' : 'right-full'}
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
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
