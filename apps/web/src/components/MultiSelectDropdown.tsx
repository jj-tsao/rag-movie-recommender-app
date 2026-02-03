import { useState, useRef, useEffect } from "react";

type Props = {
  label: string;
  options: string[];
  selected: string[];
  onChange: (newValues: string[]) => void;
};

export default function MultiSelectDropdown({
  label,
  options,
  selected,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleOption = (opt: string) =>
    onChange(
      selected.includes(opt)
        ? selected.filter((o) => o !== opt)
        : [...selected, opt]
    );

  const removeItem = (val: string) =>
    onChange(selected.filter((v) => v !== val));

  return (
    <div className="relative w-full text-left" ref={dropdownRef}>
      <label className="block text-sm font-medium mb-1 text-foreground">
        {label}
      </label>

      <div
        className="w-full min-h-[2.5rem] rounded-lg border border-border bg-background text-foreground px-3 py-2 flex items-center flex-wrap gap-1 cursor-pointer"
        onClick={() => setOpen((prev) => !prev)}
      >
        {selected.length === 0 && (
          <span className="text-muted-foreground text-sm">Select...</span>
        )}

        {selected.map((val) => (
          <span
            key={val}
            className="flex items-center bg-muted text-muted-foreground text-sm px-2 py-0.5 rounded-full"
          >
            {val}
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeItem(val);
              }}
              className="ml-1 text-muted-foreground hover:text-destructive"
              aria-label={`Remove ${val}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>

      {open && (
        <div className="absolute z-10 mt-2 w-full rounded-lg bg-background border border-border shadow-lg max-h-60 overflow-y-auto">
          {options.map((option) => (
            <label
              key={option}
              className="flex items-center px-3 py-2 hover:bg-muted cursor-pointer text-sm"
            >
              <input
                type="checkbox"
                checked={selected.includes(option)}
                onChange={() => toggleOption(option)}
                className="mr-2 accent-primary"
              />
              {option}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
