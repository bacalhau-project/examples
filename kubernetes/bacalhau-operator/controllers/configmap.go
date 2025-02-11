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
	jobv1 "bacalhau-operator/api/v1"
	"context"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

func (r *BacalhauJobReconciler) reconcileJobCM(ctx context.Context, job *jobv1.BacalhauJob, bjobID string) (*string, error) {
	l := log.FromContext(ctx)
	cm := &corev1.ConfigMap{}
	err := r.Get(ctx, client.ObjectKey{
		Name:      job.Name,
		Namespace: job.Namespace,
	}, cm)
	if err != nil {
		if client.IgnoreNotFound(err) != nil {
			l.Error(err, "unable to fetch ConfigMap")
			return nil, err
		}
		cm = r.generateConfigmap(*job, bjobID)
		err := controllerutil.SetControllerReference(job, cm, r.Scheme)
		if err != nil {
			l.Error(err, "could not set owner reference")
			return nil, err
		}

		err = r.Create(ctx, cm)
		if err != nil {
			l.Error(err, "unable to create ConfigMap")
			return nil, err
		}

	}
	id := cm.Data[jobID]
	return &id, nil
}

func (r *BacalhauJobReconciler) generateConfigmap(job jobv1.BacalhauJob, bjobID string) *corev1.ConfigMap {
	return &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      job.Name,
			Namespace: job.Namespace,
		},
		Immutable: pointerTo(true),
		Data: map[string]string{
			jobID: bjobID,
		},
	}
}
