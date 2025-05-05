// Utility functions for calculations

// Adjust label positioning to match new satellite arc positions
export const calculateLabelPosition = (index: number, totalSatellites: number, panelWidth: number) => {
    const padding = panelWidth * 0.1
    const availableWidth = panelWidth - padding * 2
    const spacing = availableWidth / (totalSatellites - 1 || 1)

    // If only one satellite, center it
    if (totalSatellites === 1) {
        return { x: panelWidth / 2, y: 160 }
    }

    const x = padding + index * spacing

    // Calculate position along the arc
    const normalizedPosition = index / (totalSatellites - 1) // 0 to 1
    const arcHeight = 40 // Maximum height difference in the arc

    // Calculate y position - higher in the middle, lower at the edges
    const arcY = arcHeight * Math.sin(Math.PI * normalizedPosition)
    const y = 160 - arcY // Adjust y position based on arc

    return { x, y }
}

// Adjust name label positioning for the arc
export const calculateNameLabelPosition = (index: number, totalSatellites: number, panelWidth: number) => {
    const padding = panelWidth * 0.1
    const availableWidth = panelWidth - padding * 2
    const spacing = availableWidth / (totalSatellites - 1 || 1)

    // If only one satellite, center it
    if (totalSatellites === 1) {
        return { x: panelWidth / 2, y: -25, align: "center" as const }
    }

    const x = padding + index * spacing

    // Position name labels above satellites
    return {
        x,
        y: -25, // Above the satellite
        align: "center" as const,
    }
}

// Adjust satellite positioning to create an arc
export const calculateSatellitePosition = (index: number, totalSatellites: number, panelWidth: number) => {
    // Distribute satellites evenly across the top with padding
    const padding = panelWidth * 0.1 // 10% padding on each side
    const availableWidth = panelWidth - padding * 2
    const spacing = availableWidth / (totalSatellites - 1 || 1)

    // If only one satellite, center it
    if (totalSatellites === 1) {
        return { x: panelWidth / 2, y: 80 }
    }

    const x = padding + index * spacing

    // Calculate position along the arc
    const normalizedPosition = index / (totalSatellites - 1) // 0 to 1

    // Create a parabolic arc (higher in the middle, lower at the edges)
    // Using the formula: y = h * (1 - 4 * (x - 0.5)²) where h is the max height
    const arcHeight = 60 // Maximum height of the arc
    const arcY = arcHeight * (1 - 4 * Math.pow(normalizedPosition - 0.5, 2))

    const baseY = 100 // Base height from the top
    const y = baseY - arcY // Subtract to make the middle higher (smaller y value)

    return { x, y }
}
