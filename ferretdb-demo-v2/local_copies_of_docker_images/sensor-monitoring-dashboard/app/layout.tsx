import type React from "react"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata = {
  title: "Sensor Monitoring Dashboard",
  description: "Monitor sensor data and detect anomalies",
    generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-background">
          <div className="bg-primary py-4 px-6 text-white">
            <div className="container mx-auto">
              <h1 className="text-xl font-bold">Sensor Monitoring Dashboard</h1>
            </div>
          </div>
          {children}
        </div>
      </body>
    </html>
  )
}



import './globals.css'