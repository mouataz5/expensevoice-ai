import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function TagInput({
  value,
  onChange,
  placeholder = "Type and press Enter",
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [text, setText] = useState("");

  const add = () => {
    const v = text.trim();
    if (!v) return;
    if (value.includes(v)) return setText("");
    onChange([...value, v]);
    setText("");
  };

  const remove = (t: string) => onChange(value.filter((x) => x !== t));

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          className="rounded-xl"
        />
        <Button type="button" variant="outline" className="rounded-xl" onClick={add}>
          Add
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {value.map((t) => (
          <Badge key={t} variant="secondary" className="rounded-xl">
            {t}
            <button
              type="button"
              className="ml-2 text-xs hover:opacity-80"
              onClick={() => remove(t)}
              aria-label={`Remove ${t}`}
            >
              ✕
            </button>
          </Badge>
        ))}
      </div>
    </div>
  );
}
