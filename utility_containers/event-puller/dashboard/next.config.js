/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'export',
    allowedDevOrigins: ['172.16.23.62'],
    images: {
        remotePatterns: [
            {
                hostname: '**',
            },
        ],
        unoptimized: true,
    },
    async rewrites() {
        return [
            {
                source: '/ws',
                destination: 'http://172.16.23.62:8080/ws',
            },
        ];
    },
};
module.exports = nextConfig;
