// Define types for the application
export type ConnectionStatus = "No Connection" | "Low Bandwidth" | "High Bandwidth"
export type DetailViewType = "satellite" | "ground-station" | null
export type Job = {
    id: string
    name: string
    priority: "low" | "high" | "todo"
    satelliteId: number
    thumbnail: string
}

export type SelectedItem = {
    type: DetailViewType
    id: number | null
}

export interface Satellite {
    id: string
    Info: {
        NodeID: string;
        NodeType: string;
        Labels: {
            PUBLIC_IP: string;
            SATELLITE_NAME: string
        };
    };
    Connection: string,
    ConnectionState: {
        Status: string
    }
}
