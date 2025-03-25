import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Slash } from "lucide-react";

export const DisconnectButton = ({ node }) => {
    const ip = node?.Info.Labels.PUBLIC_IP ?? '';
    const isDisconnected = node?.Connection === 'DISCONNECTED';

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
            variant={"outline"}
            size="sm"
            onClick={() => handleClick(ip)}
            disabled={buttonDisabled}
        >
            <Slash className="h-4 w-4 mr-1" />
            {isDisconnected ? 'Node Connect' : 'Node Disconnect'}
        </Button>
    );
};
