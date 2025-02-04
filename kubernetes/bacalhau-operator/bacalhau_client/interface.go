package bacalhau_client

import (
	"context"

	bacalhau_models "github.com/bacalhau-project/bacalhau/pkg/models"
	bacalhau "github.com/bacalhau-project/bacalhau/pkg/publicapi/client/v2"
)

type BacalhauClienter interface {
	API() bacalhau.API
	Alive(ctx context.Context) (bool, error)
	Version(ctx context.Context) (*bacalhau_models.BuildVersionInfo, error)
	SubmitJob(ctx context.Context, job *bacalhau_models.Job) (string, error)
	GetJob(ctx context.Context, jobID string) (*bacalhau_models.Job, error)
	GetJobInfo(ctx context.Context, jobID string) ([]*bacalhau_models.JobHistory,
		[]*bacalhau_models.Execution,
		*bacalhau_models.State[bacalhau_models.JobStateType], error)
	GetJobStatus(ctx context.Context, jobID string) (*bacalhau_models.State[bacalhau_models.JobStateType], error)
	ListJobs(ctx context.Context, filter string) ([]*bacalhau_models.Job, error)
	ListQueuedJobs(ctx context.Context) ([]*bacalhau_models.Job, error)
	ListJobsWithCount(ctx context.Context, count int, filter string) ([]*bacalhau_models.Job, error)
	CancelJob(ctx context.Context, jobID string) error
	ListNodes(ctx context.Context) ([]*bacalhau_models.NodeState, error)
	PurgeDisconnectedNodes(ctx context.Context) error
}
