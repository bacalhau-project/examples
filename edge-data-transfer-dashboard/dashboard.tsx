"use client"

import React, {useEffect, useState} from "react"
import {Card} from "@/components/ui/card"
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs"
import {Network,} from "lucide-react"
import useFetchNodes, {NodesList} from "@/components/NodesList"
import {ClearMetadataButton} from "@/components/ClearMetadataButton"
import FilesGrid from "./components/FilesGrid"

// -----------------------------------------
// Header Component (Memoized)
// -----------------------------------------
const HeaderComponent = React.memo(() => {
  return (
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center">
          <div className="flex items-center gap-2 font-semibold">
            <Network className="h-6 w-6" />
            <span>Edge Data Transfer Demo</span>
          </div>
        </div>
      </header>
  )
})

// -----------------------------------------
// Overview Tab Component (Memoized)
// -----------------------------------------
const OverviewTab = React.memo(
    ({ nodes, files, metaData }) => {
      return (
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <NodesList nodes={nodes} filesLength={files.length}/>
              <FilesGrid
                  nodes={nodes}
                  files={files}
                  metadata={metaData?.files}
              />
              <Card>
              </Card>
            </div>
          </TabsContent>
      )
    }
)

function useFetchFiles(nodes) {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    if (!nodes || nodes.length < 2 || files.length > 0) return;

    const fetchFiles = async () => {
      // Create an array of fetch promises for valid nodes (ignoring "Requester" nodes)
      const fetchPromises = nodes.slice(1).map((node) => {
        const {
          Info: {
            Labels: { PUBLIC_IP },
            NodeType,
          },
        } = node;
        if (NodeType !== "Requester" && PUBLIC_IP) {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 1000);
          return fetch(`http://${PUBLIC_IP}:9123/file`, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              Authorization: "Bearer abrakadabra1234!@#",
            },
            signal: controller.signal,
          })
              .then((response) => {
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error("Request failed");
                return response.json();
              })
              .catch((error) => {
                clearTimeout(timeoutId);
                console.error(`Error from ${PUBLIC_IP}:`, error);
                // Propagate the error so that Promise.any can ignore it later.
                return Promise.reject(error);
              });
        }
        return Promise.reject("Invalid node");
      });

      try {
        // Wait for the first promise that fulfills successfully
        const result = await Promise.any(fetchPromises);
        setFiles(result.files);
      } catch (error) {
        console.error("No node returned a valid response", error);
      }
    };

    fetchFiles();
    const intervalId = setInterval(fetchFiles, 10000);
    return () => clearInterval(intervalId);
  }, [nodes, files]);

  return files;
}

// -----------------------------------------
// Main Dashboard Component
// -----------------------------------------
export default function EdgeDataTransferDashboard() {
  const [activeTab, setActiveTab] = useState("overview")
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const files = useFetchFiles(nodes);
  useFetchNodes(setNodes, setLoading)

  return (
      <div className="flex min-h-screen flex-col bg-gray-50">
        <HeaderComponent/>
        <main className="flex-1 container py-6">
          <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <div className="flex justify-between items-center">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2">
                <ClearMetadataButton nodes={nodes} />
              </div>
            </div>
            <OverviewTab nodes={nodes} files={files} metaData={{ files: [] }} />
          </Tabs>
        </main>
      </div>
  )
}
