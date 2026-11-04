export interface Chunk {
  source: string;
  page: string;
  title: string;
  text: string;
}

export interface AskResponse {
  answer: string;
  chunks: Chunk[];
}

export interface Turn {
  id: number;
  question: string;
  status: "loading" | "done" | "error";
  answer?: string;
  chunks?: Chunk[];
  error?: string;
}
