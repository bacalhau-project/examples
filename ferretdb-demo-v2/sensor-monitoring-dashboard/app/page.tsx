import SensorStats from "@/components/sensor-stats"
import DetailedWorldMap from "@/components/detailed-world-map"
import {TooltipProvider} from "@/components/ui/tooltip";
import {EnvProvider} from "@/providers/EnvProvider";

export default function Home() {
    return (
        <main className="container mx-auto py-8 px-4">
            <div className="mb-8">
                <EnvProvider>
                    <TooltipProvider>
                        <DetailedWorldMap/>
                    </TooltipProvider>
                </EnvProvider>
            </div>

            <SensorStats/>
        </main>
    )
}

