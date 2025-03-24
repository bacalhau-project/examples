import {Button} from "@/components/ui/button";
import {Slash, WifiOff} from "lucide-react";


export const NetworkLossButton = ({node, jobRunning}) => {
    const ip = node?.Info.Labels.PUBLIC_IP ?? ''
    const isDisconnected = node?.Connection === 'DISCONNECTED'

    const handleClick = async (ip:string) => {
        const url = isDisconnected ? 'open-nfs': 'close-nfs'
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
        } catch (error) {
            console.error('An error occurred:', error);
        }
    };
    return (  <Button
            variant={isDisconnected ? "destructive" : "outline"}
            size="sm"
            onClick={() => handleClick(ip)}
            // disabled={!jobRunning}
        >
            <WifiOff className="h-4 w-4 mr-1" />  {isDisconnected ? 'Network open' : 'Network loss'}
        </Button>
    )
}
