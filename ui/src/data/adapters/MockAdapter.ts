const mockLoaders = import.meta.glob('../mocks/**/*.json', { import: 'default' });

export interface MockAdapterOptions {
  minDelayMs?: number;
  maxDelayMs?: number;
}

const DEFAULT_MIN_DELAY = 200;
const DEFAULT_MAX_DELAY = 600;

export class MockAdapter {
  private static cache = new Map<string, unknown>();

  static async fetch<T>(mockFile: string, options: MockAdapterOptions = {}): Promise<T> {
    const path = this.resolveMockPath(mockFile);
    const loader = mockLoaders[path];

    if (!loader) {
      throw new Error(`Mock file not found: ${path}`);
    }

    await this.simulateDelay(options);

    if (!this.cache.has(path)) {
      const data = await loader();
      this.cache.set(path, data);
    }

    return this.cache.get(path) as T;
  }

  private static resolveMockPath(mockFile: string): string {
    const normalized = mockFile.startsWith('/') ? mockFile.slice(1) : mockFile;
    const withExtension = normalized.endsWith('.json') ? normalized : `${normalized}.json`;
    return `../mocks/${withExtension}`;
  }

  private static async simulateDelay({ minDelayMs, maxDelayMs }: MockAdapterOptions): Promise<void> {
    const min = minDelayMs ?? DEFAULT_MIN_DELAY;
    const max = maxDelayMs ?? DEFAULT_MAX_DELAY;
    const duration = Math.floor(Math.random() * (max - min + 1)) + min;

    await new Promise((resolve) => setTimeout(resolve, duration));
  }
}
