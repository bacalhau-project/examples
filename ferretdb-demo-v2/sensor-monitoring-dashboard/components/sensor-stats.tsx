"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

type SensorStat = {
  sensor_id: string
  location: string
  count: number
}

export default function SensorStats() {
  const [loading, setLoading] = useState(true)
  const [sensorStats, setSensorStats] = useState<SensorStat[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchSensorStats() {
      try {
        const response = await fetch("/api/sensors");

        if (!response.ok) {
          throw new Error(`API responded with status: ${response.status}`);
        }

        const { success, data, error } = await response.json();

        if (!success) {
          throw new Error(error || "Failed to fetch sensor stats");
        }

        setSensorStats(data);
      } catch (err) {
        console.error("Error fetching sensor stats:", err);
        setError(err instanceof Error ? err.message : "Unknown error occurred");
      } finally {
        setLoading(false);
      }
    }

    fetchSensorStats();
    const intervalId = setInterval(fetchSensorStats, 5000);

    return () => clearInterval(intervalId);
  }, []);

  return (
    <Card className="w-full border border-gray-200">
      <CardHeader>
        <CardTitle>Sensor Statistics</CardTitle>
        <CardDescription>Number of data points per sensor and location</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>
              {error}
              <div className="mt-2">
                Please ensure your MongoDB connection is properly configured in environment variables.
              </div>
            </AlertDescription>
          </Alert>
        ) : loading ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-gray-200">
                <TableHead>Sensor ID</TableHead>
                <TableHead>Location</TableHead>
                <TableHead className="text-right">Data Points</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sensorStats.map((stat) => (
                <TableRow key={stat.sensor_id} className="border-gray-200">
                  <TableCell className="font-medium">
                    <a href={`/sensor/${stat.sensor_id}`} className="text-blue-500 hover:underline">
                      {stat.sensor_id}
                    </a>
                  </TableCell>
                  <TableCell>{stat.location}</TableCell>
                  <TableCell className="text-right">{stat.count}</TableCell>
                </TableRow>
              ))}
              {sensorStats.length === 0 && (
                <TableRow className="border-gray-200">
                  <TableCell colSpan={3} className="text-center p-4">
                    No sensor data available
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

