import { Button } from "@/components/ui/button";

type Props = {
  label: string;
  onClick: () => void;
};

export default function FloatingActionButton({ label, onClick}: Props) {
  return (
    <div
      className="fixed bottom-4 right-4 z-50"
    >
      <Button
        onClick={onClick}
        className="bg-primary text-white shadow-lg px-4 py-2 rounded-full"
      >
        {label}
      </Button>
    </div>
  );
}
