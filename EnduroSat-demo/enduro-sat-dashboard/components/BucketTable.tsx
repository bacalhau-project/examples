import React, { useEffect, useState } from "react";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
    DialogTrigger,
    DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {Download} from "lucide-react";

type BucketFile = {
    id: string;
    result: { name: string };
    thumbnail: { name: string };
};

export const BucketTable = ({
    title,
    headerColor,
}: {
    title: string;
    headerColor: string;
}) => {
    const isLow = title === "Low bandwidth";
    const bandwidth = isLow ? "low-bandwidth" : "high-bandwidth";

    const [files, setFiles] = useState<BucketFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // modal state
    const [isModalOpen, setModalOpen] = useState(false);
    const [modalId, setModalId] = useState<string | null>(null);
    const [modalJson, setModalJson] = useState<any>(null);
    const [modalLoading, setModalLoading] = useState(false);
    const [modalError, setModalError] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            const res = await fetch(`/api/minio/${bandwidth}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: BucketFile[] = await res.json();
            setFiles(data);
            setError(null);
        } catch (err) {
            console.error(err);
            setError("Failed to load files");
        }
    };

    const openResultModal = async (id: string) => {
        setModalId(id);
        setModalOpen(true);
        setModalLoading(true);
        setModalError(null);

        try {
            const res = await fetch(`/api/minio/${bandwidth}/${id}/result.json`);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const json = await res.json();
            setModalJson(json);
        } catch (err) {
            console.error(err);
            setModalError("Failed to load result.json");
        } finally {
            setModalLoading(false);
        }
    };

    const downloadZip = (id: string) => {
        // triggers browser download
        window.location.href = `/api/minio/${bandwidth}/${id}/zip`;
    };

    useEffect(() => {
        setLoading(true);
        setError(null);
        fetchData().finally(() => setLoading(false));

        const intervalId = setInterval(fetchData, 1000);
        return () => clearInterval(intervalId);
    }, [bandwidth]);

    return (
        <>
            <Card className="border shadow-md">
                <CardHeader
                    className="py-2 px-3"
                    style={{ backgroundColor: headerColor, color: "white" }}
                >
                    <CardTitle className="text-sm font-medium">{title}</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {loading ? (
                        <div className="p-4 text-center text-sm text-slate-500">
                            Loading…
                        </div>
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
                                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Action
                                    </th>
                                </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                {files.map((file) => (
                                    <tr
                                        key={file.id}
                                        className="hover:bg-slate-50 transition-colors duration-200"
                                    >
                                        {/* Filename clickable */}
                                        <td className="px-3 py-2 text-xs font-semibold">
                                            <button
                                                onClick={() => openResultModal(file.id)}
                                                className="text-blue-600 hover:underline"
                                            >
                                                {file.id}
                                            </button>
                                        </td>

                                        {/* Thumbnail preview */}
                                        <td className="px-3 py-2 text-xs relative group overflow-visible">
                                            <div
                                                className="w-8 h-8 bg-gray-100 flex items-center justify-center rounded-sm border border-slate-200 overflow-hidden">
                                                <img
                                                    src={`/api/minio/${bandwidth}/${file.id}`}
                                                    alt={`${file.id} thumbnail`}
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
                                                        src={`/api/minio/${bandwidth}/${file.id}`}
                                                        alt={`${file.id} preview`}
                                                        className="max-w-full max-h-full object-contain"
                                                    />
                                                </div>
                                            </div>
                                        </td>

                                        <td className="px-3 py-2 text-xs">
                                            <Button size="sm" variant="outline"
                                                    className="flex items-center gap-1 h-6 text-xs"  onClick={() => downloadZip(file.id)}>
                                                <Download className="h-3 w-2"/>
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Modal for result.json */}
            <Dialog open={isModalOpen} onOpenChange={setModalOpen}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>
                            Result for <span className="font-mono">{modalId}</span>
                        </DialogTitle>
                    </DialogHeader>
                    <div className="mt-2">
                        {modalLoading ? (
                            <p>Loading…</p>
                        ) : modalError ? (
                            <p className="text-red-500">{modalError}</p>
                        ) : (
                            <pre className="overflow-auto max-h-[50vh] bg-gray-100 p-2 rounded text-xs">
                {JSON.stringify(modalJson, null, 2)}
              </pre>
                        )}
                    </div>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button size="sm">Close</Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};
