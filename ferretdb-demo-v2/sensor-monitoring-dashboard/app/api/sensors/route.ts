import { NextResponse } from "next/server"
import clientPromise from "@/lib/mongodb"

export async function GET() {
  try {
    const client = await clientPromise
    const db = client.db("postgres") // Database name

    // Get data points count per sensor with location
    const sensorStats = await db
      .collection("sensor_readings")
      .aggregate([
        // Updated collection name
        {
          $group: {
            _id: { sensor_id: "$sensor_id", location: "$location" },
            count: { $sum: 1 },
          },
        },
        {
          $project: {
            sensor_id: "$_id.sensor_id",
            location: "$_id.location",
            count: 1,
            _id: 0,
          },
        },
        { $sort: { sensor_id: 1 } },
      ])
      .toArray()

    return NextResponse.json({ success: true, data: sensorStats })
  } catch (error) {
    console.error("Error fetching sensor stats:", error)
    return NextResponse.json(
      {
        success: false,
        error: "Failed to fetch sensor data. Please ensure MongoDB connection is properly configured.",
      },
      { status: 500 },
    )
  }
}

