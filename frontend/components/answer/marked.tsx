import { splitValues } from "@/lib/format";

// Text with every verified value highlighted - the visual proof the figure is there.
export function Marked({ text, values }: { text: string; values: string[] }) {
  return splitValues(text, values).map(([part, hit], i) =>
    hit ? <mark key={i}>{part}</mark> : part,
  );
}
