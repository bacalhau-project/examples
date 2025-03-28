interface ClearQueueModalProps {
  setShowConfirm: (show: boolean) => void;
  clearQueue: () => void;
}

export default function ClearQueueModal({ setShowConfirm, clearQueue }: ClearQueueModalProps) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-bold">Confirm Queue Clear</h2>
        <p className="mb-6">Are you sure you want to clear the queue? This cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setShowConfirm(false)}
            className="cursor-pointer rounded border border-gray-300 px-4 py-2 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={clearQueue}
            className="cursor-pointer rounded bg-red-600 px-4 py-2 text-white hover:bg-red-700"
          >
            Clear Queue
          </button>
        </div>
      </div>
    </div>
  );
}
