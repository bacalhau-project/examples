import { Button } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

interface ClearQueueModalProps {
  open: boolean;
  setOpen: (show: boolean) => void;
  clearQueue: () => void;
}

export default function ClearQueueModal({ open, setOpen, clearQueue }: ClearQueueModalProps) {
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="bg-background">
        <DialogHeader>
          <DialogTitle>Confirm Queue Clear</DialogTitle>
          <DialogDescription>
            Are you sure you want to clear the queue? This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} className="cursor-pointer">
            Cancel
          </Button>
          <Button variant="destructive" onClick={clearQueue} className="cursor-pointer">
            Clear Queue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
