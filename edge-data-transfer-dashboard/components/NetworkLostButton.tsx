import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {Button} from "@/components/ui/button";
import {WifiOff} from "lucide-react";

export const NetworkLossButton = ({ node }) => {
    // Memoize the IP so it's recalculated only when node changes
    const ip = useMemo(() => node?.Info?.Labels?.PUBLIC_IP ?? "", [node]);

    const [isDisconnected, setIsDisconnected] = useState(true);

    useEffect(() => {
        if (!ip) return;

        const checkHealth = async () => {
            try {
                const response = await fetch(`http://${ip}:9123/nfs-healthz`, {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: "Bearer abrakadabra1234!@#",
                    },
                });

                if (!response.ok) {
                    throw new Error("Health check failed");
                }

                const data = await response.json();
                setIsDisconnected(data.status !== "healthy");
            } catch (error) {
                setIsDisconnected(true);
            }
        };

        checkHealth();
        const intervalId = setInterval(checkHealth, 7000);

        return () => {
            clearInterval(intervalId);
        };
    }, [ip]);

    const handleClick = useCallback(async () => {
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
    }, [ip, isDisconnected]);

    return (
        <Button variant={isDisconnected ? "destructive" : "outline"} size="sm" onClick={handleClick}>
            <WifiOff className="h-4 w-4 mr-1" />
            {isDisconnected ? "Nfs open" : "Nfs loss"}
        </Button>
    );
};
