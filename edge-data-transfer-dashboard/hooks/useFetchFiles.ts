import { useEffect, useState, useRef } from "react";

export function useFetchFiles(nodes) {
    const [files, setFiles] = useState([]);
    const fetched = useRef(false);

    useEffect(() => {
        let isMounted = true;
        const abortControllers = [];

        const fetchFiles = async () => {
            if (fetched.current) return;

            const validNodes = nodes.slice(1).filter(
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

                    if (isMounted && data.files) {
                        setFiles(data.files);
                        fetched.current = true;
                        break;
                    }
                } catch (error) {
                    console.error(
                        `Error when fetching files on:  ${node.Info.Labels.PUBLIC_IP}:`,
                        error
                    );
                }
            }
        };

        if (nodes.length > 1) {
            fetchFiles();

            const interval = setInterval(() => {
                if (!fetched.current) {
                    fetchFiles();
                } else {
                    clearInterval(interval);
                }
            }, 100000);

            return () => {
                isMounted = false;
                clearInterval(interval);
                abortControllers.forEach((controller) => controller.abort());
            };
        }
    }, [nodes]);

    return files;
}
