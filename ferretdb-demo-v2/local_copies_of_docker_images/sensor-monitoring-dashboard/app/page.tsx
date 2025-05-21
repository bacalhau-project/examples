import SensorStats from "@/components/sensor-stats"
import DetailedWorldMap from "@/components/detailed-world-map"
import {TooltipProvider} from "@/components/ui/tooltip";

export const dynamic = 'force-dynamic'

export default async function Home() {
    const mapsKey = process.env.GOOGLE_MAPS_API_KEY
    return (
        <main className="container mx-auto py-8 px-4">
            <div className="mb-8">
                    <TooltipProvider>
                        <DetailedWorldMap apiKey={mapsKey ?? ''}/>
                    </TooltipProvider>
            </div>
            <SensorStats/>
        </main>
    )
}

