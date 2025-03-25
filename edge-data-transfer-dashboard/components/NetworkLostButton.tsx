import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { WifiOff } from "lucide-react";

export const NetworkLossButton = ({ node }) => {
    // Memoizacja IP, przeliczane tylko gdy node się zmienia
    const ip = useMemo(() => node?.Info?.Labels?.PUBLIC_IP ?? "", [node]);

    const [isDisconnected, setIsDisconnected] = useState(true);
    const [buttonDisabled, setButtonDisabled] = useState(false);

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
        const intervalId = setInterval(checkHealth, 3000);

        return () => {
            clearInterval(intervalId);
        };
    }, [ip]);

    const handleClick = useCallback(async () => {
        if (!ip || buttonDisabled) return;

        // Blokowanie przycisku na 3 sekundy
        setButtonDisabled(true);
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

        setTimeout(() => {
            setButtonDisabled(false);
        }, 3000);
    }, [ip, isDisconnected, buttonDisabled]);

    return (
        <Button
            variant={isDisconnected ? "destructive" : "outline"}
            size="sm"
            onClick={handleClick}
            disabled={buttonDisabled}
        >
            <WifiOff className="h-4 w-4 mr-1" />
            {isDisconnected ? "Nfs open" : "Nfs loss"}
        </Button>
    );
};
