import { Container } from "@cloudflare/containers";

export class ContentStudioContainer extends Container {
  // Streamlit
  defaultPort = 8501;
  // Долгие сессии + ZeroGPT/LLM; WebSocket держит инстанс живым
  sleepAfter = "30m";
  enableInternet = true;

  override onStart(): void {
    console.log("Content Studio container started");
  }

  override onStop(): void {
    console.log("Content Studio container stopped");
  }

  override onError(error: unknown): void {
    console.error("Content Studio container error:", error);
  }
}

export interface Env {
  // Namespace с хелперами Container (getByName)
  CONTENT_STUDIO: DurableObjectNamespace<ContentStudioContainer> & {
    getByName: (name: string) => DurableObjectStub;
  };
  DEEPSEEK_API_KEY?: string;
  HYDRA_API_KEY?: string;
  LLM_API_KEY?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      return new Response("ok", { status: 200 });
    }

    // Один sticky-инстанс (pages/settings в контейнере эфемерны без R2)
    const container = env.CONTENT_STUDIO.getByName("main");
    return container.fetch(request);
  },
};
