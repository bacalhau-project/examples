// Utility functions for status-related operations
import type { ConnectionStatus } from "@/types"

export const getStatusColor = (status: ConnectionStatus) => {
    switch (status) {
        case "No Connection":
            return "#ef4444"
        case "Low Bandwidth":
            return "#f59e0b"
        case "High Bandwidth":
            return "#10b981"
        default:
            return "#6b7280"
    }
}
