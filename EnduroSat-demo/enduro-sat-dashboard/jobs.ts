
export const shipDetectJob = (satelliteName: string) => ({
    Job: {
        Name: "Ship Detection Job",
        Type: "batch",
        Count: 1,
        Constraints: [
            {
                Key: "SATTELITE_NAME",
                Operator: "=",
                Values: [satelliteName],
            },
        ],
        Labels: {
            sattelite_number: satelliteName,
        },
        Tasks: [
            {
                Name: 'Detect Ships',
                Engine: {
                    Type: 'docker',
                    Params: {
                        Image: "kitsune242/detect"
                    }
                },
                InputSources: [
                    {
                        Target: "/mnt/local_files",
                        Source: {
                            Type: "localdirectory",
                            Params: {
                                SourcePath: "/mnt/local_files",
                                readWrite: true,
                            },
                        },
                    },
                ],
                Resources: {
                    CPU: "4000m",
                    Memory: "3Gb",
                    Disk: "1000mb"
                }
            },
        ],
    }
})

export const highJob = (satelliteName: string) => ({
        Job: {
            Name: "data-transfer-high",
            Type: "batch",
            Count: 1,
            Constraints: [
                {
                    Key: "SATTELITE_NAME",
                    Operator: "=",
                    Values: [satelliteName],
                },
            ],
            Labels: {
                sattelite_number: satelliteName,
            },
            Tasks: [
                {
                    Name: "data-transfer",
                    Engine: {
                        Type: "docker",
                        Params: {
                            Image: "ubuntu:20.04",
                            Entrypoint: ["/bin/bash"],
                            Parameters: [
                                "-c",
                                `echo "📦 Listing files to transfer:" && \
ls -l /mnt/local_files/output/HIGH_bandwidth/ && \
cp -r /mnt/local_files/output/HIGH_bandwidth/* /mnt/s3_high/`,
                            ],
                        },
                    },
                    InputSources: [
                        {
                            Target: "/mnt/local_files",
                            Source: {
                                Type: "localdirectory",
                                Params: {
                                    SourcePath: "/mnt/local_files",
                                    readWrite: true,
                                },
                            },
                        },
                        {
                            Target: "/mnt/s3_high",
                            Source: {
                                Type: "localdirectory",
                                Params: {
                                    SourcePath: "/mnt/s3_high",
                                    readWrite: true,
                                },
                            },
                        },
                    ],
                    Publisher: { Type: "noop" },
                },
            ],
        },
})

export const lowJob = (satelliteName: string) => ({
    Job: {
        Name: "data-transfer-low",
        Type: "batch",
        Count: 1,
        Constraints: [
            {
                Key: "SATTELITE_NAME",
                Operator: "=",
                Values: [satelliteName],
            },
        ],
        Labels: {
            sattelite_number: satelliteName,
        },
        Tasks: [
            {
                Name: "data-transfer",
                Engine: {
                    Type: "docker",
                    Params: {
                        Image: "ubuntu:20.04",
                        Entrypoint: ["/bin/bash"],
                        Parameters: [
                            "-c",
                            `echo "📦 Listing files to transfer:" && \
ls -l /mnt/local_files/output/LOW_bandwidth/ && \
cp -r /mnt/local_files/output/LOW_bandwidth/* /mnt/s3_low/`,
                        ],
                    },
                },
                InputSources: [
                    {
                        Target: "/mnt/local_files",
                        Source: {
                            Type: "localdirectory",
                            Params: {
                                SourcePath: "/mnt/local_files",
                                readWrite: true,
                            },
                        },
                    },
                    {
                        Target: "/mnt/s3_low",
                        Source: {
                            Type: "localdirectory",
                            Params: {
                                SourcePath: "/mnt/s3_low",
                                readWrite: true,
                            },
                        },
                    },
                ],
                Publisher: { Type: "noop" },
            },
        ],
    },
})
