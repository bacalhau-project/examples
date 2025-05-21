import { MongoClient } from "mongodb"

// Use the provided MongoDB connection string
const MONGODB_URI = process.env.FERRETDB_URI ?? `mongodb://expansouser:safepassword@$127.0.0.1:27017/postgres`

let client: MongoClient
let clientPromise: Promise<MongoClient>

// Function to create a new client
const createClient = () => {
  return new MongoClient(MONGODB_URI)
}

if (process.env.NODE_ENV === "development") {
  // In development mode, use a global variable so that the value
  // is preserved across module reloads caused by HMR (Hot Module Replacement).
  const globalWithMongo = global as typeof globalThis & {
    _mongoClientPromise?: Promise<MongoClient>
  }

  if (!globalWithMongo._mongoClientPromise) {
    client = createClient()
    globalWithMongo._mongoClientPromise = client.connect()
  }

  clientPromise = globalWithMongo._mongoClientPromise
} else {
  // In production mode, it's best to not use a global variable.
  client = createClient()
  clientPromise = client.connect()
}

// Export a module-scoped MongoClient promise
export default clientPromise

