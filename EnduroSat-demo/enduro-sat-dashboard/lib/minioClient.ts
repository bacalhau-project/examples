import { Client } from 'minio'

const client = new Client({
    endPoint: 'storage',
    port: 9000,
    useSSL: false,
    accessKey: 'minioadmin',
    secretKey: 'minioadmin'
})

export default client
