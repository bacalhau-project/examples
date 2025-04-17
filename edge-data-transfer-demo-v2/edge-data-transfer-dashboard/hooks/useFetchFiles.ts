import { useEffect, useState, useRef } from "react";
import {NodeProps} from "@/lib/JobProvider";

export function useFetchFiles(nodes: NodeProps[]) {
    const [files, setFiles] = useState([]);
    const fetched = useRef(false);

    useEffect(() => {
        const abortControllers: any[] = [];

        const fetchFiles = async () => {
            if (fetched.current) return;

            const validNodes = nodes.filter(
                (node) =>
                    node.Info.NodeType !== "Requester" && node.Info.Labels.PUBLIC_IP
            );

            for (const node of validNodes) {
                if (fetched.current) break;

                const controller = new AbortController();
                abortControllers.push(controller);

                try {
                    const response = await fetch(
                        `http://${node.Info.Labels.PUBLIC_IP}:9123/file`,
                        {
                            method: "GET",
                            headers: {
                                "Content-Type": "application/json",
                                Authorization: "Bearer abrakadabra1234!@#",
                            },
                            signal: controller.signal,
                        }
                    );

                    if (!response.ok) throw new Error("Request failed");

                    const data = await response.json();

                    if (data.files) {
                        setFiles(data.files.filter((file: string) => file !== ".healthcheck"));
                        fetched.current = true;
                        break;
                    }
                } catch (error) {
                    console.error(
                        `Error when fetching files on: ${node.Info.Labels.PUBLIC_IP}:`,
                        error
                    );
                }
            }
        };

        if (nodes.length > 0) {
            fetchFiles();

            const interval = setInterval(() => {
                if (!fetched.current) {
                    fetchFiles();
                } else {
                    clearInterval(interval);
                }
            }, 100000);

            return () => {
                clearInterval(interval);
                abortControllers.forEach((controller) => controller.abort());
            };
        }
    }, [nodes]);

    return files;
}
