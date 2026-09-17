import { proxy } from "@/lib/api";

export const GET = () => proxy("/health");
