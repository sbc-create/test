/**
 * Референсный клиент Control Plane для TypeScript. Только чтение.
 *
 * Мутаций нет намеренно: помощник, умеющий писать, появится после IAM и
 * policy (FLEET-CORE-003). Клиент, дающий писать раньше прав, — это обход
 * политики, встроенный в библиотеку.
 */
export const CLIENT_VERSION = "fleet-client-ts/1.0.0";
const RETRYABLE = new Set([429, 502, 503, 504]);

export class ContractError extends Error {}

export interface SiteRecord {
  site_id: string;
  canonical_domain?: string;
  lifecycle_state?: string;
  environment?: string;
  [key: string]: unknown;   // неизвестные необязательные поля допустимы
}

export class FleetClient {
  constructor(
    private base = "http://127.0.0.1:8790",
    private timeoutMs = 15000,
    private retries = 3,
    private correlationId = crypto.randomUUID(),
  ) {}

  private async get<T>(path: string): Promise<{ status: number; body: T; headers: Headers }> {
    let delay = 100;
    let last: unknown = null;
    for (let attempt = 1; attempt <= this.retries; attempt++) {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), this.timeoutMs);
      try {
        const r = await fetch(this.base + path, {
          signal: ctl.signal,
          headers: {
            Accept: "application/json",
            "User-Agent": CLIENT_VERSION,
            "X-Correlation-ID": this.correlationId,
          },
        });
        const body = (await r.json().catch(() => ({}))) as T;
        // Неповторяемую ошибку повторять бессмысленно: 404 не станет 200.
        if (r.ok || !RETRYABLE.has(r.status)) {
          return { status: r.status, body, headers: r.headers };
        }
        last = new Error(`HTTP ${r.status}`);
      } catch (e) {
        last = e;
      } finally {
        clearTimeout(t);
      }
      if (attempt < this.retries) {
        // Джиттер обязателен: без него клиенты повторяют синхронно.
        await new Promise((res) => setTimeout(res, Math.min(delay, 2000) * (1 + Math.random() * 0.3)));
        delay *= 2;
      }
    }
    throw new ContractError(`${path}: ${String(last)}`);
  }

  manifest = async () => (await this.get<Record<string, unknown>>("/api/v1/contracts/manifest")).body;
  capabilities = async () => (await this.get<Record<string, unknown>>("/api/v1/capabilities")).body;
  controlPlaneVersion = async () => (await this.get<Record<string, unknown>>("/api/v1/control-plane/version")).body;

  async sites(environment?: string, lifecycleState?: string): Promise<SiteRecord[]> {
    const q: string[] = [];
    if (environment) q.push(`environment=${environment}`);
    if (lifecycleState) q.push(`lifecycle_state=${lifecycleState}`);
    const path = "/api/v1/sites" + (q.length ? "?" + q.join("&") : "");
    const { status, body } = await this.get<{ items: SiteRecord[] }>(path);
    if (status !== 200) throw new ContractError(`/api/v1/sites -> ${status}`);
    return body.items ?? [];
  }

  /** Девять сайтов берутся из реестра, а не из списка в коде. */
  activeProductionSites = () => this.sites("production", "ACTIVE");

  async snapshot(): Promise<{ body: Record<string, unknown>; etag: string | null }> {
    const { status, body, headers } = await this.get<Record<string, unknown>>("/api/v1/registry/snapshot");
    if (status !== 200) throw new ContractError(`snapshot -> ${status}`);
    return { body, etag: headers.get("ETag") };
  }

  async events(after = 0, limit = 100) {
    const { status, body } = await this.get<{ items: unknown[]; next_cursor: number }>(
      `/api/v1/events?after=${after}&limit=${limit}`);
    if (status !== 200) throw new ContractError(`events -> ${status}`);
    return body;
  }

  /** Отсутствие обязательного поля — отказ; лишнее поле — не отказ. */
  static validate(rec: Record<string, unknown>, required: string[]): void {
    const missing = required.filter((f) => !(f in rec));
    if (missing.length) throw new ContractError(`нет обязательных полей: ${missing.join(", ")}`);
  }
}
