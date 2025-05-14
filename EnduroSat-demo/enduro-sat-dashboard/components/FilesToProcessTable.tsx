import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import React, { useEffect, useState } from "react";

type FilesTableProps = {
    satelliteName: string;
};

export function FilesToProcessTable({ satelliteName }: FilesTableProps) {
    const [files, setFiles] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Funkcja fetchująca bez zmiany stanu `loading`
    const fetchData = async () => {
        try {
            const res = await fetch(`/api/${satelliteName}-data/input`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: { images: string[] } = await res.json();
            setFiles(data.images);
            setError(null);
        } catch (err) {
            console.error(err);
            setError("Failed to load files");
        }
    };

    useEffect(() => {
        // 1️⃣ Pierwsze wywołanie: pokazujemy loading
        setLoading(true);
        setError(null);
        fetchData().finally(() => {
            setLoading(false);
        });

        // 2️⃣ Ustawiamy interwał, który fetchuje **tylko** dane
        const intervalId = setInterval(fetchData, 1000);

        // Cleanup przy zmianie satelliteName lub unmount
        return () => clearInterval(intervalId);
    }, [satelliteName]);

    return (
        <Card className="border shadow-md">
            <CardHeader className="py-2 px-3" style={{ backgroundColor: "#1e293b", color: "white" }}>
                <CardTitle className="text-sm font-medium">Files to process</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                {loading ? (
                    <div className="p-4 text-center text-sm text-slate-500">Loading…</div>
                ) : error ? (
                    <div className="p-4 text-center text-sm text-red-500">{error}</div>
                ) : files.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">No files found.</div>
                ) : (
                    <div className="overflow-hidden">
                        <table className="min-w-full">
                            <thead className="bg-slate-100 border-b">
                            <tr>
                                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    File Name
                                </th>
                            </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200">
                            {files.map((file) => (
                                <tr
                                    key={file}
                                    className="hover:bg-slate-50 transition-colors transition-opacity duration-300"
                                >
                                    <td className="px-3 py-2 text-xs font-semibold">{file}</td>
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
