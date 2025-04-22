import { NextResponse } from "next/server"
import clientPromise from "../../../../lib/mongodb"

export async function GET(request: Request, context: { params: { id: string } }) {
  try {
    const params = await context.params;
    const sensorId = params.id;
    const client = await clientPromise;
    const db = client.db("postgres") // Database name

    // Get sensor readings with timestamp for the specific sensor
    // Sort by timestamp to ensure proper ordering for the chart
    const readings = await db
      .collection("sensor_readings") // Updated collection name
      .find({ sensor_id: sensorId })
      .sort({ timestamp: 1 })
      .toArray()

    return NextResponse.json({ success: true, data: readings })
  } catch (error) {
    console.error(`Error fetching data for sensor ${context.params.id}:`, error)
    return NextResponse.json(
      {
        success: false,
        error: `Failed to fetch data for sensor ${context.params.id}. Please ensure MongoDB connection is properly configured.`,
      },
      { status: 500 },
    )
  }
}

