import { useState, useEffect, useRef } from 'react';

interface JobSummary {
    id: string;
    name: string;
    status: string;
}
export function useJobs(options?: {
    jobName?: string;
    statuses?: string[];
}): {
    jobs: JobSummary[];
    loading: boolean;
    error: string | null;
} {
    const { jobName, statuses } = options || {};
    const [jobs, setJobs] = useState<JobSummary[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const intervalId = useRef<number | null>(null);

    const fetchJobs = async () => {
        try {
            const params = new URLSearchParams();
            if (jobName) {
                params.set('jobName', jobName);
            }
            if (statuses && statuses.length > 0) {
                params.set('statuses', statuses.join(','));
            }

            const url = `http://localhost:8438/api/v1/orchestrator/jobs?${params.toString()}`;
            const res = await fetch(url);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status} – ${res.statusText}`);
            }
            const data= await res.json();
            setJobs(data);
            setError(null)
        } catch (err: any) {
            setError(err.message);
        }
    };

    useEffect(() => {
        setLoading(true);
        setError(null);
        fetchJobs().finally(() => setLoading(false));
        intervalId.current = window.setInterval(fetchJobs, 1000);

        return () => {
            if (intervalId.current !== null) {
                clearInterval(intervalId.current);
            }
        };
    }, [
        jobName ?? '',
        ...(statuses ?? []).join(','),
    ]);

    return { jobs, loading, error };
}
