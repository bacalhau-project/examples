"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { WifiOff } from "lucide-react";

export const NetworkLossButton = ({ node }) => {
    const ip = node?.Info.Labels.PUBLIC_IP ?? "";
    const [isDisconnected, setIsDisconnected] = useState(false);

    useEffect(() => {
        if (!ip) return;

        let isMounted = true;

        const checkHealth = async () => {
            const controller = new AbortController();
            try {
                const response = await fetch(`http://${ip}:9123/nfs-healthz`, {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: "Bearer abrakadabra1234!@#",
                    },
                    signal: controller.signal,
                });

                if (!response.ok) {
                    throw new Error("Health check failed");
                }

                const data = await response.json();
                if (isMounted) {
                    setIsDisconnected(data.status === "unhealthy");
                }
            } catch (error) {
                if (error.name === "AbortError") {
                    console.log("Fetch aborted");
                    return;
                }
                console.error("Health check error:", error);
                if (isMounted) {
                    setIsDisconnected(true);
                }
            }
        };

        // Initial check and then poll every 1500ms
        checkHealth();
        const intervalId = setInterval(checkHealth, 3000);

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, [ip]);

    const handleClick = async () => {
        if (!ip) return;
        const endpoint = isDisconnected ? "open-nfs" : "close-nfs";
        try {
            const response = await fetch(`http://${ip}:9123/${endpoint}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: "Bearer abrakadabra1234!@#",
                },
                body: JSON.stringify({}),
            });

            if (!response.ok) {
                throw new Error("Error sending request");
            }
        } catch (error) {
            console.error("Error during request:", error);
        }
    };

    return (
        <Button variant={isDisconnected ? "destructive" : "outline"} size="sm" onClick={handleClick}>
            <WifiOff className="h-4 w-4 mr-1" />
            {isDisconnected ? "Nfs open" : "Nfs loss"}
        </Button>
    );
};
