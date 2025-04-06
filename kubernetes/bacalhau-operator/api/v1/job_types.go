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

package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// BacalhauJobSpec defines the desired state of BacalhauJob
type BacalhauJobSpec struct {
	// Raw is the complete Bacalhau job specification
	// +kubebuilder:pruning:PreserveUnknownFields
	Raw runtime.RawExtension `json:"raw,omitempty"`
}

type BacalhauJobConstraint struct {
	Key      string   `json:"key"`
	Operator string   `json:"operator"`
	Values   []string `json:"values,omitempty"`
}

// BacalhauJobStatus defines the observed state of BacalhauJob
type BacalhauJobStatus struct {
	JobID      string             `json:"jobID,omitempty"`
	LastPolled *string            `json:"lastPolled,omitempty"`
	JobState   string             `json:"jobState,omitempty"`
	Terminated bool               `json:"terminated,omitempty"`
	Executions []ExecutionHistory `json:"executions,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:printcolumn:name="JobID",type="string",JSONPath=".status.jobID",description="ID of the BacalhauJob"
// +kubebuilder:printcolumn:name="LastPolled",type="string",JSONPath=".status.lastPolled",description="Last time the status was checked"
// +kubebuilder:printcolumn:name="JobState",type="string",JSONPath=".status.jobState",description="Latest status of the BacalhauJob"
// +kubebuilder:printcolumn:name="Terminated",type="boolean",JSONPath=".status.terminated",description="Is BacalhauJob in its terminated state"
// BacalhauJob is the Schema for the jobs API
type BacalhauJob struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec       BacalhauJobSpec    `json:"spec,omitempty"`
	Status     BacalhauJobStatus  `json:"status,omitempty"`
	Executions []ExecutionHistory `json:"executions,omitempty"`
}

type ExecutionHistory struct {
	ID        string   `json:"id,omitempty"`
	Logs      []string `json:"logs,omitempty"`
	StdOutput string   `json:"stdoutput,omitempty"`
	StdErr    string   `json:"stderror,omitempty"`
}

//+kubebuilder:object:root=true

// BacalhauJobList contains a list of BacalhauJob
type BacalhauJobList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []BacalhauJob `json:"items"`
}

func init() {
	SchemeBuilder.Register(&BacalhauJob{}, &BacalhauJobList{})
}
