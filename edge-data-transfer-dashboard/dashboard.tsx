"use client"

import React, {memo, useEffect, useMemo, useState} from "react"
import {Network,} from "lucide-react"
import {NodesList} from "@/components/NodesList"
import FilesGrid from "./components/FilesGrid"
import useFetchNodes from "@/hooks/useFetchNodes";

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
const OverviewTab = memo(({nodes}: {nodes: unknown}) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <NodesList nodes={nodes} />
            <FilesGrid nodes={nodes} />
        </div>
    )
})

// function useFetchFiles(nodes) {
//   const [files, setFiles] = useState([]);
//
//   useEffect(() => {
//     if (!nodes || nodes.length < 2 || files.length > 0) return;
//
//     const fetchFiles = async () => {
//       // Create an array of fetch promises for valid nodes (ignoring "Requester" nodes)
//       const fetchPromises = nodes.slice(1).map((node) => {
//         const {
//           Info: {
//             Labels: { PUBLIC_IP },
//             NodeType,
//           },
//         } = node;
//         if (NodeType !== "Requester" && PUBLIC_IP) {
//           const controller = new AbortController();
//           const timeoutId = setTimeout(() => controller.abort(), 1000);
//           return fetch(`http://${PUBLIC_IP}:9123/file`, {
//             method: "GET",
//             headers: {
//               "Content-Type": "application/json",
//               Authorization: "Bearer abrakadabra1234!@#",
//             },
//             signal: controller.signal,
//           })
//               .then((response) => {
//                 clearTimeout(timeoutId);
//                 if (!response.ok) throw new Error("Request failed");
//                 return response.json();
//               })
//               .catch((error) => {
//                 clearTimeout(timeoutId);
//                 console.error(`Error from ${PUBLIC_IP}:`, error);
//                 // Propagate the error so that Promise.any can ignore it later.
//                 return Promise.reject(error);
//               });
//         }
//         return Promise.reject("Invalid node");
//       });
//
//       try {
//         // Wait for the first promise that fulfills successfully
//         const result = await Promise.any(fetchPromises);
//         setFiles(result.files);
//       } catch (error) {
//         console.error("No node returned a valid response", error);
//       }
//     };
//
//     fetchFiles();
//     const intervalId = setInterval(fetchFiles, 100000);
//     return () => clearInterval(intervalId);
//   }, [nodes, files]);
//
//   return files;
// }

// -----------------------------------------
// Main Dashboard Component
// -----------------------------------------
export default function EdgeDataTransferDashboard() {
  const { nodes } = useFetchNodes()
  const memoizedNodes = useMemo(() => nodes, [nodes])
  return (
      <div className="flex min-h-screen flex-col bg-gray-50">
        <HeaderComponent/>
        <main className="flex-1 container py-6">
            <OverviewTab nodes={memoizedNodes} />
        </main>
      </div>
  )
}
