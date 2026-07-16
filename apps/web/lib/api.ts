import type { Founder, Source, Topic } from "./types";

const serverApi = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function read<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${serverApi}/api/v1${path}`, { next: { revalidate: 30 } });
    return response.ok ? (await response.json() as T) : fallback;
  } catch {
    return fallback;
  }
}

export const getFounders = () => read<Founder[]>("/founders", []);
export const getTopics = () => read<Topic[]>("/topics", []);
export const getSources = () => read<Source[]>("/sources", []);
export const getSource = (id: string) => read<{ source: Source; chunk_count: number } | null>(`/sources/${id}`, null);
