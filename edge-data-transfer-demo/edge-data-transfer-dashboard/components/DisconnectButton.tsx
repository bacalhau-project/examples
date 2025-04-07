import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Slash } from "lucide-react";

export const DisconnectButton = ({ ip, isDisconnected }: {ip: string, isDisconnected: boolean}) => {
    const [buttonDisabled, setButtonDisabled] = useState(false);

    const handleClick = async (ip: string) => {
        if (buttonDisabled) return;

        setButtonDisabled(true);
        const url = isDisconnected ? 'open-network' : 'close-network';
        try {
            const response = await fetch(`http://${ip}:9123/${url}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer abrakadabra1234!@#`,
                },
                body: JSON.stringify({}),
            });

            if (!response.ok) {
                throw new Error('Error sending request');
            }

            const data = await response.json();
            console.log('Server response:', data);
        } catch (error) {
            console.error('An error occurred:', error);
        }

        setTimeout(() => {
            setButtonDisabled(false);
        }, 3000);
    };

    return (
        <Button
            variant={isDisconnected ? "destructive" : "outline"}
            size="sm"
            onClick={() => handleClick(ip)}
            disabled={buttonDisabled}
            className={`w-40`}
        >
            <Slash className="h-4 w-4 mr-1" />
            {isDisconnected ? 'Node Reconnect' : 'Node Disconnect'}
        </Button>
    );
};
