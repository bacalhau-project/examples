"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import Link from "next/link";
import {Button} from "@/components/ui/button";

interface SensorDetailsProps {
  sensorId: string
}

type SensorInfo = {
  sensor_id: string
  model: string
  manufacturer: string
  firmware_version: string
  location: string
}

export default function SensorDetails({ sensorId }: SensorDetailsProps) {
  const [loading, setLoading] = useState(true)
  const [sensorInfo, setSensorInfo] = useState<SensorInfo | null>(null)

  useEffect(() => {
    async function fetchSensorInfo() {
      try {
        const response = await fetch(`/api/sensor-data/${sensorId}`)

        if (!response.ok) {
          throw new Error(`API responded with status: ${response.status}`)
        }

        const { success, data, error } = await response.json()

        if (!success || !data.length) {
          throw new Error(error || `No data found for sensor ${sensorId}`)
        }

        // Get the first record to extract sensor info
        const firstRecord = data[0]
        setSensorInfo({
          sensor_id: firstRecord.sensor_id,
          model: firstRecord.model,
          manufacturer: firstRecord.manufacturer,
          firmware_version: firstRecord.firmware_version,
          location: firstRecord.location,
        })
      } catch (err) {
        console.error(`Error fetching info for sensor ${sensorId}:`, err)
      } finally {
        setLoading(false)
      }
    }

    if (sensorId) {
      fetchSensorInfo()
    }
  }, [sensorId])

  return (
    <Card className="w-full border border-gray-200">
      <div className={"flex flex-row justify-between"}>

      <CardHeader>
        <CardTitle>Sensor: {sensorId}</CardTitle>
      </CardHeader>
        <div className="p-4">
        <Link href="/">
          <Button variant="default">← Back to Dashboard</Button>
        </Link>
        </div>
      </div>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : sensorInfo ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Model</p>
              <p className="text-md font-semibold">{sensorInfo.model}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Manufacturer</p>
              <p className="text-md font-semibold">{sensorInfo.manufacturer}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Firmware Version</p>
              <p className="text-md font-semibold">{sensorInfo.firmware_version}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Location</p>
              <p className="text-md font-semibold">{sensorInfo.location}</p>
            </div>
          </div>
        ) : (
          <p className="text-center text-muted-foreground">No sensor information available</p>
        )}
      </CardContent>
    </Card>
  )
}

