"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { XAxis, YAxis, CartesianGrid, ResponsiveContainer, Line, LineChart, Legend } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"
import { parseISO, subHours } from "date-fns"
import { formatInTimeZone } from 'date-fns-tz';

type SensorReading = {
  timestamp: string
  temperature: number
  vibration: number
  voltage: number
  anomaly_flag: number // 0 or 1
  anomaly_type: string | null
  status_code: number
  firmware_version: string
  model: string
  manufacturer: string
  location: string
  formattedTime: string
  // For anomaly data series
  anomalyTemperature?: number | null
  anomalyVibration?: number | null
  anomalyVoltage?: number | null
}

interface SensorChartProps {
  sensorId: string
}

export default function SensorChart({ sensorId }: SensorChartProps) {
  const [loading, setLoading] = useState(true)
  const [sensorData, setSensorData] = useState<SensorReading[]>([])
  const [error, setError] = useState<string | null>(null)
  const [yDomains, setYDomains] = useState({
    temperature: [0, 100], // Default domain for temperature
    secondary: [0, 20], // Default domain for voltage and vibration
  })

  useEffect(() => {
    async function fetchSensorData() {
      try {
        setLoading(true)
        const response = await fetch(`/api/sensor-data/${sensorId}`)

        if (!response.ok) {
          throw new Error(`API responded with status: ${response.status}`)
        }

        const { success, data, error } = await response.json()

        if (!success) {
          throw new Error(error || `Failed to fetch data for sensor ${sensorId}`)
        }

        // Get current time to filter for last 2 hours
        const now = new Date();
        const nowUTC = new Date(Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate(),
            now.getUTCHours(),
            now.getUTCMinutes(),
            now.getUTCSeconds()
        ));

      const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      // Subtract the desired number of hours (e.g., 2 hours) using the universal timestamp
      const twoHoursAgo = subHours(nowUTC, 2);

      // Format and filter data using UTC formatting
        const formattedData = data
            .map((reading) => {
              const hasTimezone = /[+-]\d{2}:\d{2}$|Z$/.test(reading.timestamp);
              const timestampStr = hasTimezone
                  ? reading.timestamp
                  : reading.timestamp + 'Z';

              const timestamp = parseISO(timestampStr);

              return {
                ...reading,
                parsedTimestamp: timestamp,
                formattedTime: formatInTimeZone(timestamp, browserTimeZone, 'yyyy-MM-dd HH:mm'),
              };
            })
            .filter((reading) => reading.parsedTimestamp.getTime() >= twoHoursAgo.getTime())
            .sort((a, b) => a.parsedTimestamp - b.parsedTimestamp);

        const processedData = formattedData.map((reading: any) => {
          const isAnomaly = reading.anomaly_flag === 1 && reading.anomaly_type !== "trend"

          return {
            ...reading,
            // For anomaly data points, create separate series values
            anomalyTemperature: isAnomaly ? reading.temperature : null,
            anomalyVibration: isAnomaly ? reading.vibration : null,
            anomalyVoltage: isAnomaly ? reading.voltage : null,
          }
        })

        // Calculate appropriate Y-axis domains based on data
        if (processedData.length > 0) {
          // For temperature (left Y-axis)
          const tempValues = processedData.map((d) => d.temperature).filter(Boolean)
          const minTemp = Math.floor(Math.min(...tempValues) * 0.9)
          const maxTemp = Math.ceil(Math.max(...tempValues) * 1.1)

          // For voltage and vibration (right Y-axis)
          const voltValues = processedData.map((d) => d.voltage).filter(Boolean)
          const vibValues = processedData.map((d) => d.vibration).filter(Boolean)
          const secondaryValues = [...voltValues, ...vibValues]
          const minSecondary = Math.floor(Math.min(...secondaryValues) * 0.9)
          const maxSecondary = Math.ceil(Math.max(...secondaryValues) * 1.1)

          setYDomains({
            temperature: [minTemp, maxTemp],
            secondary: [minSecondary, maxSecondary],
          })
        }

        setSensorData(processedData)
      } catch (err) {
        console.error(`Error fetching data for sensor ${sensorId}:`, err)
        setError(err instanceof Error ? err.message : "Unknown error occurred")
      } finally {
        setLoading(false)
      }
    }

    if (sensorId) {
      fetchSensorData()
    }
  }, [sensorId])

  return (
    <Card className="w-full mt-8 border border-gray-200">
      <CardHeader className="pb-2">
        <CardTitle>Readings data</CardTitle>
        <CardDescription>Temperature, Vibration, and Voltage (last 2 hours)</CardDescription>
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
          <div className="h-[250px] w-full">
            <Skeleton className="h-full w-full" />
          </div>
        ) : sensorData.length === 0 ? (
          <div className="h-[250px] w-full flex items-center justify-center">
            <p className="text-muted-foreground">No data available for the last 2 hours</p>
          </div>
        ) : (
            <div className="h-[300px] w-full flex">
              <div className="flex-1 min-w-0 relative">
                <ChartContainer
                    style={{ width: '100%', height: '100%' }}
                    config={{
                      temperature: {
                        label: "Temperature",
                        color: "hsl(var(--chart-1))",
                      },
                      vibration: {
                        label: "Vibration",
                        color: "hsl(var(--chart-2))",
                      },
                      voltage: {
                        label: "Voltage",
                        color: "hsl(var(--chart-3))",
                      },
                      anomalyTemperature: {
                        label: "Anomaly (Temperature)",
                        color: "hsl(0, 100%, 50%)", // Red
                      },
                      anomalyVibration: {
                        label: "Anomaly (Vibration)",
                        color: "hsl(30, 100%, 50%)", // Orange
                      },
                      anomalyVoltage: {
                        label: "Anomaly (Voltage)",
                        color: "hsl(103,44%,26%)", // Green
                      },
                    }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sensorData} margin={{top: 10, right: 30, left: 0, bottom: 0}}>
                      <CartesianGrid strokeDasharray="3 3"/>
                      <XAxis
                          dataKey="formattedTime"
                          tick={{fontSize: 12}}
                          tickFormatter={(value) => value.split(" ")[1]}
                      />

                      {/* Left Y-axis for Temperature */}
                      <YAxis
                          yAxisId="left"
                          domain={yDomains.temperature}
                          tick={{fontSize: 12}}
                          tickCount={5}
                          label={{
                            value: "Temperature",
                            angle: -90,
                            position: "insideLeft",
                            style: {textAnchor: "middle"},
                          }}
                      />

                      {/* Right Y-axis for Voltage and Vibration */}
                      <YAxis
                          yAxisId="right"
                          orientation="right"
                          domain={yDomains.secondary}
                          tick={{fontSize: 8}}
                          tickCount={5}
                          label={{
                            value: "Voltage / Vibration",
                            angle: 90,
                            position: "insideRight",
                            style: {textAnchor: "middle"},
                          }}
                      />

                      <ChartTooltip content={<ChartTooltipContent/>}/>
                      <Legend/>

                      {/* Temperature data series (left axis) */}
                      <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="temperature"
                          stroke="var(--color-temperature)"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{r: 4}}
                          connectNulls
                      />

                      {/* Vibration data series (right axis) */}
                      <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="vibration"
                          stroke="var(--color-vibration)"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{r: 4}}
                          connectNulls
                      />

                      {/* Voltage data series (right axis) */}
                      <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="voltage"
                          stroke="var(--color-voltage)"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{r: 4}}
                          connectNulls
                      />

                      {/* Anomaly data series */}
                      <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="anomalyTemperature"
                          stroke="var(--color-anomalyTemperature)"
                          strokeWidth={0}
                          dot={{r: 3, strokeWidth: 2}}
                          activeDot={{r: 4}}
                          connectNulls
                      />
                      <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="anomalyVibration"
                          stroke="var(--color-anomalyVibration)"
                          strokeWidth={0}
                          dot={{r: 3, strokeWidth: 2}}
                          activeDot={{r: 4}}
                          connectNulls
                      />
                      <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="anomalyVoltage"
                          stroke="var(--color-anomalyVoltage)"
                          strokeWidth={0}
                          dot={{r: 3, strokeWidth: 2}}
                          activeDot={{r: 4}}
                          connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </div>
            </div>
              )}
            </CardContent>
          </Card>
          )
        }

