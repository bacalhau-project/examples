interface FooterProps {
  isConnected: boolean;
}

export default function Footer({ isConnected }: FooterProps) {
  return (
    <div className="mt-auto flex flex-col justify-between bg-white p-4 text-sm text-gray-600 shadow-md md:flex-row">
      <div>
        <span className="font-medium">CosmosDB Status:</span>{' '}
        {isConnected ? 'Connected' : 'Not Connected'}
      </div>
      <div suppressHydrationWarning>
        Event Puller Dashboard | {new Date().getFullYear()} | Expanso.io
      </div>
    </div>
  );
}
