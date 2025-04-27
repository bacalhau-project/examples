import Link from "next/link"
import { Button } from "../../../components/ui/button"
import SensorChart from "../../../components/sensor-chart"
import SensorDetails from "../../../components/sensor-details"

export default function SensorPage({ params }: { params: { id: string } }) {
  return (
    <main className="container mx-auto py-8 px-4">
      <SensorDetails sensorId={params.id} />

      <SensorChart sensorId={params.id} />
    </main>
  )
}

