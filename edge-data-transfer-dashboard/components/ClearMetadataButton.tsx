import { Button } from "@/components/ui/button";
import { FileJson } from "lucide-react";
import {NodeProps} from "@/lib/JobProvider";

export const ClearMetadataButton = ({ nodes} : {nodes: NodeProps[]}) => {
    const handleClick = async () => {
        try {
            await Promise.all(
                nodes.map(async (node) => {
                    try {
                        const {
                            Info: {
                                NodeType,
                                Labels: { PUBLIC_IP },
                            },
                        } = node;
                        if(NodeType !== 'Requester') {
                            // Adjust the URL and port as needed.
                            const response = await fetch(`http://${PUBLIC_IP}:9123/clear-metadata`, {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                    "Authorization": `Bearer abrakadabra1234!@#`,
                                },
                                body: JSON.stringify({}),
                            });
                            if (!response.ok) {
                                throw new Error("Error sending request");
                            }
                            const data = await response.json();
                            console.log("Server response:", data);
                        }
                    } catch (error) {
                        console.error("An error occurred:", error);
                    }
                })
            );
        } catch (error) {
            console.error("An error occurred:", error);
        }
    };

    return (
        <Button variant="default" size="sm" onClick={handleClick}>
            <FileJson className="h-4 w-4 mr-1" /> Clear metadata
        </Button>
    );
};
