"use client"

// Component for the job selection modal
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

type JobModalProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    selectedJobType: string | null
    onJobSelection: (jobType: string) => void
    onJobSubmit: () => void
}

export function JobModal({ open, onOpenChange, selectedJobType, onJobSelection, onJobSubmit }: JobModalProps) {
    const jobTypes = [
        {
            name: "Detect Ships",
            type: "DETECT_SHIP",
            description: "Use satellite imagery to detect and track ships",
        },
        {
            name: "Low Bandwidth Transfer",
            type: "LOW_BANDWIDTH",
            description: "Transfer data at reduced speed to conserve bandwidth",
        },
        {
            name: "High Bandwidth Transfer",
            type: "HIGH_BANDWIDTH",
            description: "Transfer data at maximum available speed",
        }
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-center">Select Job Type</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    {jobTypes.map((jobType) => (
                        <div
                            key={jobType.name}
                            className={cn(
                                "flex items-center p-3 rounded-md border cursor-pointer transition-all",
                                selectedJobType === jobType.type
                                    ? "border-primary bg-primary/5 shadow-sm"
                                    : "border-slate-200 hover:border-slate-300 hover:bg-slate-50",
                            )}
                            onClick={() => onJobSelection(jobType.type)}
                        >
                            <div className="flex-1">
                                <h3 className="font-medium">{jobType.name}</h3>
                                <p className="text-xs text-slate-500">{jobType.description}</p>
                            </div>
                            <div
                                className={cn(
                                    "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                                    selectedJobType === jobType.type ? "border-primary" : "border-slate-300",
                                )}
                            >
                                {selectedJobType === jobType.type && <div className="w-2.5 h-2.5 rounded-full bg-primary" />}
                            </div>
                        </div>
                    ))}
                </div>
                <DialogFooter>
                    <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
                        Cancel
                    </Button>
                    <Button size="sm" onClick={onJobSubmit} disabled={!selectedJobType} className="w-full sm:w-auto">
                        Start Job
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
