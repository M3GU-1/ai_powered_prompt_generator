/**
 * API client for the SD Prompt Tag Generator backend.
 * Supports both standard REST calls and SSE streaming.
 */
const API = {
    BASE: '',

    async _fetch(path, options = {}) {
        const res = await fetch(this.BASE + path, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
    },

    async healthCheck() {
        return this._fetch('/api/health');
    },

    async generateTags(description, numTags = 20, includeCategories = [0, 3, 4, 5]) {
        return this._fetch('/api/generate', {
            method: 'POST',
            body: JSON.stringify({
                description,
                num_tags: numTags,
                include_categories: includeCategories,
            }),
        });
    },

    async matchTag(tag) {
        return this._fetch('/api/match', {
            method: 'POST',
            body: JSON.stringify({ tag }),
        });
    },

    async getConfig() {
        return this._fetch('/api/config');
    },

    async updateConfig(config) {
        return this._fetch('/api/config', {
            method: 'PUT',
            body: JSON.stringify(config),
        });
    },

    async searchTags(query, limit = 10) {
        return this._fetch(`/api/tags/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    },

    async getUsage() {
        return this._fetch('/api/usage');
    },

    async resetUsage() {
        return this._fetch('/api/usage', { method: 'DELETE' });
    },

    /**
     * Stream tag generation via SSE (POST).
     * Yields parsed SSE event objects: { type: "log"|"complete", data: {...} }
     * @param {string} url - Endpoint path (e.g., /api/generate/stream)
     * @param {Object} body - Request body
     * @param {AbortSignal} [signal] - Optional abort signal
     */
    async *streamGenerate(url, body, signal) {
        const res = await fetch(this.BASE + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(trimmed.slice(6));
                            yield data;
                        } catch {
                            // Skip malformed JSON lines
                        }
                    }
                }
            }

            // Process any remaining buffer
            if (buffer.trim().startsWith('data: ')) {
                try {
                    yield JSON.parse(buffer.trim().slice(6));
                } catch {
                    // Skip
                }
            }
        } finally {
            reader.releaseLock();
        }
    },
};
