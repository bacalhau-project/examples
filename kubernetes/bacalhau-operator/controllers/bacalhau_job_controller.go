/*
Copyright 2023 - 2025.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package controllers

import (
	"bacalhau-operator/bacalhau_client"
	"context"
	"fmt"
	"time"

	bacalhau_models "github.com/bacalhau-project/bacalhau/pkg/models"
	"github.com/bacalhau-project/bacalhau/pkg/util/idgen"
	corev1 "k8s.io/api/core/v1"
	k8sErrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/tools/record"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	jobv1 "bacalhau-operator/api/v1"

	"github.com/bacalhau-project/bacalhau/cmd/util"
	"github.com/bacalhau-project/bacalhau/pkg/system"
)

const (
	jobID = "jobID"
)

// BacalhauJobReconciler reconciles a BacalhauJob object
type BacalhauJobReconciler struct {
	client.Client
	Scheme          *runtime.Scheme
	BCleanupManager *system.CleanupManager
	Bclient         bacalhau_client.BacalhauClienter
	EventRecorder   record.EventRecorder
}

//+kubebuilder:rbac:groups=core.bacalhau.org,resources=bacalhaujobs,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=core.bacalhau.org,resources=bacalhaujobs/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=core.bacalhau.org,resources=bacalhaujobs/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.9.2/pkg/reconcile
func (r *BacalhauJobReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	l := log.FromContext(ctx)
	const PollInterval = 5 * time.Second
	ctx = context.WithValue(ctx, util.SystemManagerKey, r.BCleanupManager)

	l.Info("Reconciling", "job", req.NamespacedName)
	job := &jobv1.BacalhauJob{}
	err := r.Get(ctx, req.NamespacedName, job)
	if err != nil {
		l.Info("unable to fetch BacalhauJob")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	jobCM := &corev1.ConfigMap{}
	err = r.Get(ctx, client.ObjectKey{
		Name:      job.Name,
		Namespace: job.Namespace,
	}, jobCM)
	if err != nil && !k8sErrors.IsNotFound(err) {
		l.Error(err, "unable to fetch ConfigMap")
		return ctrl.Result{}, err
	}

	bjobID := jobCM.Data[jobID]
	if err != nil && k8sErrors.IsNotFound(err) {

		id, result, createErr := r.createJob(ctx, job)
		if createErr != nil {
			return result, createErr
		}
		bjobID = *id
	}

	if job.Status.JobID != bjobID {
		job.Status.JobID = bjobID
		err = r.Status().Update(ctx, job)
		if err != nil {
			l.Error(err, "unable to update job status")
			return ctrl.Result{}, err
		}
	}

	if job.Status.LastPolled != nil && !job.Status.Terminated {
		lastPolled, err := time.Parse(time.RFC3339, *job.Status.LastPolled)
		if err == nil && time.Since(lastPolled) < PollInterval {
			return ctrl.Result{RequeueAfter: PollInterval}, nil
		}
	}
	result, err, done := r.updateJobStatus(ctx, err, job, PollInterval)
	if done {
		return result, err
	}

	l.Info("Reconciled successfully", "job", req.NamespacedName, "jobID", bjobID)

	return ctrl.Result{}, nil
}

func (r *BacalhauJobReconciler) createJob(ctx context.Context, job *jobv1.BacalhauJob) (*string, ctrl.Result, error) {
	l := log.FromContext(ctx)
	bjob, err := CreateJobSpec(ctx, job)
	if err != nil {
		l.Error(err, "unable to generate job")
		return nil, ctrl.Result{}, err
	}
	jobId, err := r.Bclient.SubmitJob(ctx, bjob)
	if err != nil {
		l.Error(err, "unable to execute job")
		return nil, ctrl.Result{}, err
	}

	// We create an immutable Configmap to store the jobID.
	// This is going to be used to be manage the lifecycle of the Bacalhau job
	id, err := r.reconcileJobCM(ctx, job, jobId)
	if err != nil {
		if k8sErrors.IsAlreadyExists(err) {
			// should never occur, but if it does, we requeue
			return nil, ctrl.Result{Requeue: true}, err
		}
		_ = r.Bclient.CancelJob(ctx, jobId)
		l.Error(err, "unable to reconcile job configmap")
		return nil, ctrl.Result{}, err
	}
	return id, ctrl.Result{}, nil
}

func (r *BacalhauJobReconciler) updateJobStatus(ctx context.Context, err error, job *jobv1.BacalhauJob,
	pollInterval time.Duration) (ctrl.Result, error, bool) {
	l := log.FromContext(ctx)
	jobHistoryEntries, executions, newState, err := r.Bclient.GetJobInfo(ctx, job.Status.JobID)
	now := time.Now().UTC().Format(time.RFC3339)

	if err != nil {
		l.Error(err, "Failed to poll for job status")
		return ctrl.Result{RequeueAfter: pollInterval}, nil, true
	}

	updateState := newState.StateType.String()
	if job.Status.JobState != updateState {
		r.EventRecorder.Eventf(job, "Normal", "StatusUpdate", "Status updated to: %s", updateState)
		job.Status.JobState = updateState
		job.Status.Terminated = newState.StateType.IsTerminal()
	}

	job.Status.Executions = r.parseExecutionHistory(executions, jobHistoryEntries)
	job.Status.LastPolled = &now

	if err := r.Status().Update(ctx, job); err != nil {
		l.Error(err, "Failed to update job status")
		return ctrl.Result{}, err, true
	}

	l.Info("Successfully updated job state", "state: ", newState.StateType.String())
	return ctrl.Result{}, nil, false
}

func (r *BacalhauJobReconciler) parseExecutionHistory(executions []*bacalhau_models.Execution,
	jobHistoryEntries []*bacalhau_models.JobHistory) []jobv1.ExecutionHistory {
	execHistoryMap := make(map[string]*jobv1.ExecutionHistory)
	for _, execution := range executions {
		for _, jobHistory := range jobHistoryEntries {
			event := fmt.Sprintf(
				"%s: %s %s",
				jobHistory.Occurred().Format(time.RFC3339),
				string(jobHistory.Event.Topic),
				jobHistory.Event.Message,
			)
			// initialize if not exist yet
			if _, exists := execHistoryMap[execution.ID]; !exists {
				execHistoryMap[execution.ID] = &jobv1.ExecutionHistory{
					ID:   idgen.ShortUUID(execution.ID),
					Logs: []string{},
				}
			}

			execHistoryMap[execution.ID].Logs = append(execHistoryMap[execution.ID].Logs, event)
			execHistoryMap[execution.ID].StdOutput = execution.RunOutput.STDOUT
			execHistoryMap[execution.ID].StdErr = execution.RunOutput.STDERR
		}
	}

	var execHistoryList []jobv1.ExecutionHistory
	for _, ex := range execHistoryMap {
		execHistoryList = append(execHistoryList, *ex)
	}
	return execHistoryList
}

// PointerTo converts passed value to pointer
func pointerTo[T any](value T) *T {
	return &value
}

// SetupWithManager sets up the controller with the Manager.
func (r *BacalhauJobReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&jobv1.BacalhauJob{}).
		Complete(r)
}
