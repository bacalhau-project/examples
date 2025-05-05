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

export type Satellite = {
    id: number
    name: string
    color: string
}

export type SelectedItem = {
    type: DetailViewType
    id: number | null
}
