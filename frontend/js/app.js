/**
 * Main application controller for SD Prompt Tag Generator.
 */
(function () {
    'use strict';

    // --- Model Definitions ---
    const MODEL_OPTIONS = {
        openai: [
            { value: 'gpt-4.1', label: 'GPT-4.1' },
            { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
            { value: 'gpt-4.1-nano', label: 'GPT-4.1 Nano' },
            { value: 'gpt-4o', label: 'GPT-4o' },
            { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
            { value: 'o4-mini', label: 'o4 Mini (Reasoning)' },
            { value: 'o3', label: 'o3 (Reasoning)' },
            { value: 'o3-mini', label: 'o3 Mini (Reasoning)' },
        ],
        gemini: [
            { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
            { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
            { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
            { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
            { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
        ],
        ollama: [],
    };

    const DEFAULT_MODELS = {
        openai: 'gpt-4o-mini',
        gemini: 'gemini-2.5-flash',
        ollama: 'llama3.2',
    };

    // --- DOM Elements ---
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsClose = document.getElementById('settings-close');
    const settingsPanel = document.getElementById('settings-panel');
    const settingsOverlay = document.getElementById('settings-overlay');
    const providerSelect = document.getElementById('provider-select');
    const modelSelect = document.getElementById('model-select');
    const modelHint = document.getElementById('model-hint');
    const apiKeyInput = document.getElementById('api-key-input');
    const apiKeyGroup = document.getElementById('api-key-group');
    const ollamaUrlInput = document.getElementById('ollama-url-input');
    const ollamaUrlGroup = document.getElementById('ollama-url-group');
    const temperatureRange = document.getElementById('temperature-range');
    const tempDisplay = document.getElementById('temp-display');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const configStatus = document.getElementById('config-status');

    // Tabs
    const tabs = document.querySelectorAll('.tab');
    const modePanels = {
        generate: document.getElementById('mode-generate'),
        random: document.getElementById('mode-random'),
        scene: document.getElementById('mode-scene'),
    };

    // Generate mode
    const descriptionInput = document.getElementById('description-input');
    const tagsMinusBtn = document.getElementById('tags-minus');
    const tagsPlusBtn = document.getElementById('tags-plus');
    const tagsCountEl = document.getElementById('tags-count');
    const detailedCheck = document.getElementById('detailed-check');
    const animaCheck = document.getElementById('anima-check');
    const generateBtn = document.getElementById('generate-btn');

    // Random expand mode
    const randomBaseInput = document.getElementById('random-base-input');
    const randomAnimaCheck = document.getElementById('random-anima-check');
    const nsfwBtns = document.querySelectorAll('.nsfw-btn');
    const randomGenerateBtn = document.getElementById('random-generate-btn');

    // Scene expand mode
    const sceneBaseInput = document.getElementById('scene-base-input');
    const sceneDescInput = document.getElementById('scene-desc-input');
    const sceneAnimaCheck = document.getElementById('scene-anima-check');
    const sceneGenerateBtn = document.getElementById('scene-generate-btn');

    // Status & Log
    const statusBar = document.getElementById('status-bar');
    const statusMessage = document.getElementById('status-message');
    const logSection = document.getElementById('log-section');
    const logToggleBtn = document.getElementById('log-toggle');
    const logDot = document.getElementById('log-dot');
    const logCount = document.getElementById('log-count');
    const logContainer = document.getElementById('log-container');
    const logEntries = document.getElementById('log-entries');

    // Results
    const resultsSection = document.getElementById('results-section');
    const rawTagsEl = document.getElementById('raw-tags');
    const rawTagCountEl = document.getElementById('raw-tag-count');
    const matchedTagsEl = document.getElementById('matched-tags');
    const selectAllBtn = document.getElementById('select-all-btn');
    const deselectAllBtn = document.getElementById('deselect-all-btn');
    const customTagInput = document.getElementById('custom-tag-input');
    const addCustomBtn = document.getElementById('add-custom-btn');
    const autocompleteDropdown = document.getElementById('autocomplete-dropdown');
    const finalPromptEl = document.getElementById('final-prompt');
    const copyBtn = document.getElementById('copy-btn');
    const copyText = copyBtn.querySelector('.copy-text');
    const copiedText = copyBtn.querySelector('.copied-text');

    const healthDot = document.getElementById('health-indicator');
    const healthText = document.getElementById('health-text');

    // --- State ---
    let numTags = 20;
    let currentMode = 'generate';
    let nsfwLevel = null; // 'spicy' | 'boost' | 'explicit' | null
    let tagEditor;
    let autocompleteTimer = null;
    let abortController = null;
    let logEntryCount = 0;

    // --- Initialize ---
    function init() {
        tagEditor = new TagEditor(matchedTagsEl, onTagsChanged);

        // Settings
        settingsToggle.addEventListener('click', openSettings);
        settingsClose.addEventListener('click', closeSettings);
        settingsOverlay.addEventListener('click', closeSettings);
        providerSelect.addEventListener('change', onProviderChange);
        temperatureRange.addEventListener('input', () => {
            tempDisplay.textContent = temperatureRange.value;
        });
        saveConfigBtn.addEventListener('click', saveConfig);

        // Tabs
        tabs.forEach(tab => {
            tab.addEventListener('click', () => switchMode(tab.dataset.mode));
        });

        // Generate mode
        tagsMinusBtn.addEventListener('click', () => updateTagCount(-5));
        tagsPlusBtn.addEventListener('click', () => updateTagCount(5));
        generateBtn.addEventListener('click', handleGenerate);

        // Random expand mode
        nsfwBtns.forEach(btn => {
            btn.addEventListener('click', () => toggleNsfw(btn));
        });
        randomGenerateBtn.addEventListener('click', handleRandomExpand);

        // Scene expand mode
        sceneGenerateBtn.addEventListener('click', handleSceneExpand);

        // Results
        selectAllBtn.addEventListener('click', () => tagEditor.selectAll());
        deselectAllBtn.addEventListener('click', () => tagEditor.deselectAll());
        copyBtn.addEventListener('click', copyPrompt);
        addCustomBtn.addEventListener('click', addCustomTag);
        customTagInput.addEventListener('input', onCustomTagInput);
        customTagInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') addCustomTag();
        });

        // Log toggle
        logToggleBtn.addEventListener('click', toggleLog);

        // Keyboard shortcuts
        descriptionInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleGenerate();
        });

        // Close autocomplete on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.autocomplete-wrapper')) {
                autocompleteDropdown.classList.add('hidden');
            }
        });

        // Boot
        loadConfig();
        checkHealth();
    }

    // ===========================
    //  Settings
    // ===========================
    function openSettings() {
        settingsPanel.classList.add('open');
        settingsOverlay.classList.add('visible');
    }

    function closeSettings() {
        settingsPanel.classList.remove('open');
        settingsOverlay.classList.remove('visible');
    }

    function onProviderChange() {
        const provider = providerSelect.value;

        // Toggle API key / Ollama URL visibility
        if (provider === 'ollama') {
            apiKeyGroup.classList.add('hidden');
            ollamaUrlGroup.classList.remove('hidden');
        } else {
            apiKeyGroup.classList.remove('hidden');
            ollamaUrlGroup.classList.add('hidden');
        }

        // Populate model dropdown
        populateModelSelect(provider);
    }

    function populateModelSelect(provider, currentModel) {
        modelSelect.textContent = '';

        const options = MODEL_OPTIONS[provider];

        if (options && options.length > 0) {
            // Predefined models
            options.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt.value;
                el.textContent = opt.label;
                modelSelect.appendChild(el);
            });

            // "Custom..." option for manual entry
            const customOpt = document.createElement('option');
            customOpt.value = '__custom__';
            customOpt.textContent = 'Custom...';
            modelSelect.appendChild(customOpt);

            modelHint.textContent = '';

            // Set current model if it exists in the list
            if (currentModel) {
                const exists = options.some(o => o.value === currentModel);
                if (exists) {
                    modelSelect.value = currentModel;
                } else {
                    // Model not in list - add it as a custom option at the top
                    const customEntry = document.createElement('option');
                    customEntry.value = currentModel;
                    customEntry.textContent = `${currentModel} (current)`;
                    modelSelect.insertBefore(customEntry, modelSelect.firstChild);
                    modelSelect.value = currentModel;
                }
            }

            // Handle custom model selection
            modelSelect.onchange = function () {
                if (modelSelect.value === '__custom__') {
                    const custom = prompt('Enter model name:');
                    if (custom && custom.trim()) {
                        const entry = document.createElement('option');
                        entry.value = custom.trim();
                        entry.textContent = `${custom.trim()} (custom)`;
                        modelSelect.insertBefore(entry, modelSelect.lastChild);
                        modelSelect.value = custom.trim();
                    } else {
                        modelSelect.value = options[0].value;
                    }
                }
            };
        } else {
            // Ollama - no predefined models, show common ones + custom
            const commonOllama = [
                { value: 'llama3.2', label: 'Llama 3.2' },
                { value: 'llama3.1', label: 'Llama 3.1' },
                { value: 'mistral', label: 'Mistral' },
                { value: 'mixtral', label: 'Mixtral' },
                { value: 'qwen2.5', label: 'Qwen 2.5' },
                { value: 'gemma2', label: 'Gemma 2' },
                { value: 'phi3', label: 'Phi-3' },
            ];

            commonOllama.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt.value;
                el.textContent = opt.label;
                modelSelect.appendChild(el);
            });

            const customOpt = document.createElement('option');
            customOpt.value = '__custom__';
            customOpt.textContent = 'Custom...';
            modelSelect.appendChild(customOpt);

            modelHint.textContent = 'Select or enter a locally installed model';

            if (currentModel) {
                const exists = commonOllama.some(o => o.value === currentModel);
                if (exists) {
                    modelSelect.value = currentModel;
                } else {
                    const customEntry = document.createElement('option');
                    customEntry.value = currentModel;
                    customEntry.textContent = `${currentModel} (current)`;
                    modelSelect.insertBefore(customEntry, modelSelect.firstChild);
                    modelSelect.value = currentModel;
                }
            }

            modelSelect.onchange = function () {
                if (modelSelect.value === '__custom__') {
                    const custom = prompt('Enter Ollama model name:');
                    if (custom && custom.trim()) {
                        const entry = document.createElement('option');
                        entry.value = custom.trim();
                        entry.textContent = `${custom.trim()} (custom)`;
                        modelSelect.insertBefore(entry, modelSelect.lastChild);
                        modelSelect.value = custom.trim();
                    } else {
                        modelSelect.value = commonOllama[0].value;
                    }
                }
            };
        }
    }

    async function loadConfig() {
        try {
            const cfg = await API.getConfig();
            providerSelect.value = cfg.provider;
            temperatureRange.value = cfg.temperature;
            tempDisplay.textContent = cfg.temperature;
            ollamaUrlInput.value = cfg.ollama_base_url;
            if (cfg.has_api_key) apiKeyInput.placeholder = '(configured)';

            // Populate model select AFTER setting provider
            onProviderChange();
            populateModelSelect(cfg.provider, cfg.model);
        } catch (e) {
            console.warn('Failed to load config:', e);
            onProviderChange();
        }
    }

    async function saveConfig() {
        const config = {
            provider: providerSelect.value,
            model: modelSelect.value,
            temperature: parseFloat(temperatureRange.value),
        };

        if (providerSelect.value === 'ollama') {
            config.ollama_base_url = ollamaUrlInput.value;
        }

        if (apiKeyInput.value) {
            config.api_key = apiKeyInput.value;
        }

        try {
            await API.updateConfig(config);
            showConfigStatus('Settings saved!', false);
            apiKeyInput.value = '';
            apiKeyInput.placeholder = '(configured)';
            checkHealth();
        } catch (e) {
            showConfigStatus(e.message, true);
        }
    }

    function showConfigStatus(text, isError) {
        configStatus.textContent = text;
        configStatus.className = isError ? 'config-status error' : 'config-status success';
        setTimeout(() => { configStatus.textContent = ''; configStatus.className = 'config-status'; }, 3000);
    }

    // ===========================
    //  Mode Tabs
    // ===========================
    function switchMode(mode) {
        currentMode = mode;

        tabs.forEach(t => {
            t.classList.toggle('active', t.dataset.mode === mode);
        });

        Object.entries(modePanels).forEach(([key, panel]) => {
            panel.classList.toggle('hidden', key !== mode);
        });
    }

    // ===========================
    //  Tag Count
    // ===========================
    function updateTagCount(delta) {
        numTags = Math.max(5, Math.min(50, numTags + delta));
        tagsCountEl.textContent = numTags;
    }

    // ===========================
    //  NSFW Toggle (Random Expand)
    // ===========================
    function toggleNsfw(btn) {
        const level = btn.dataset.level;
        if (nsfwLevel === level) {
            nsfwLevel = null;
            btn.classList.remove('active');
        } else {
            nsfwBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            nsfwLevel = level;
        }
    }

    // ===========================
    //  Streaming Log
    // ===========================
    function toggleLog() {
        const expanded = logToggleBtn.classList.toggle('expanded');
        logContainer.classList.toggle('expanded', expanded);
    }

    function clearLog() {
        logEntries.textContent = '';
        logEntryCount = 0;
        logCount.textContent = '';
        logDot.classList.remove('active');
    }

    function addLogEntry(type, content) {
        const icons = {
            info: '\u2139',
            model: '\u2728',
            function_call: '\u2699',
            function_result: '\u2705',
            error: '\u274C',
            system: '\u25CF',
            user: '\u25B6',
        };

        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;

        const icon = document.createElement('span');
        icon.className = 'log-icon';
        icon.textContent = icons[type] || '\u25CF';

        const text = document.createElement('span');
        text.className = 'log-text';
        text.textContent = content;

        entry.appendChild(icon);
        entry.appendChild(text);
        logEntries.appendChild(entry);

        logEntryCount++;
        logCount.textContent = `(${logEntryCount})`;

        // Auto-scroll
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    function processLogEvent(event) {
        if (event.type === 'log') {
            const d = event.data;
            let content = d.content || '';

            if (d.type === 'function_call') {
                content = `${d.functionName}(${d.functionArgs || ''})`;
            } else if (d.type === 'function_result') {
                const result = d.functionResult || '';
                content = result.length > 200 ? result.substring(0, 200) + '...' : result;
            }

            if (content) {
                addLogEntry(d.type || 'info', content);
            }
        }
    }

    // ===========================
    //  Generate (Streaming)
    // ===========================
    async function handleGenerate() {
        const description = descriptionInput.value.trim();
        if (!description) {
            showStatus('Please enter an image description.', true);
            return;
        }

        const body = {
            description,
            num_tags: numTags,
            detailed: detailedCheck.checked,
            anima_mode: animaCheck.checked,
        };

        await runStreaming('/api/generate/stream', body, generateBtn);
    }

    async function handleRandomExpand() {
        const baseTags = randomBaseInput.value.trim();
        if (!baseTags) {
            showStatus('Please enter base tags.', true);
            return;
        }

        const body = {
            base_tags: baseTags,
            anima_mode: randomAnimaCheck.checked,
            spicy: nsfwLevel === 'spicy',
            boost: nsfwLevel === 'boost',
            explicit: nsfwLevel === 'explicit',
        };

        await runStreaming('/api/generate/random-expand/stream', body, randomGenerateBtn);
    }

    async function handleSceneExpand() {
        const baseTags = sceneBaseInput.value.trim();
        const sceneDesc = sceneDescInput.value.trim();
        if (!baseTags) {
            showStatus('Please enter base tags.', true);
            return;
        }
        if (!sceneDesc) {
            showStatus('Please enter a scene description.', true);
            return;
        }

        const body = {
            base_tags: baseTags,
            scene_description: sceneDesc,
            anima_mode: sceneAnimaCheck.checked,
        };

        await runStreaming('/api/generate/scene-expand/stream', body, sceneGenerateBtn);
    }

    async function runStreaming(url, body, btn) {
        // Cancel any previous request
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        setLoading(btn, true);
        clearLog();
        logSection.classList.remove('hidden');
        logDot.classList.add('active');

        // Expand log if not already
        if (!logToggleBtn.classList.contains('expanded')) {
            toggleLog();
        }

        resultsSection.classList.add('hidden');
        tagEditor.clear();
        showStatus('Generating tags...');

        try {
            for await (const event of API.streamGenerate(url, body, abortController.signal)) {
                if (event.type === 'log') {
                    processLogEvent(event);
                } else if (event.type === 'complete') {
                    logDot.classList.remove('active');

                    if (event.data.success) {
                        const tags = event.data.tags || [];
                        const promptText = event.data.promptText || '';

                        // Extract raw tag names for display
                        const rawTags = tags.map(t => t.tag || t);
                        renderRawTags(rawTags);

                        // If tags are already TagCandidate objects from the stream
                        if (tags.length > 0 && typeof tags[0] === 'object' && tags[0].match_method) {
                            tagEditor.setTags(tags);
                        } else {
                            // Tags are strings - need to display as all-selected
                            const tagObjects = tags.map(t => {
                                const tagName = typeof t === 'string' ? t : (t.tag || String(t));
                                return {
                                    tag: tagName,
                                    category: typeof t === 'object' ? (t.category || 0) : 0,
                                    count: typeof t === 'object' ? (t.count || 0) : 0,
                                    match_method: 'exact',
                                    similarity_score: 1.0,
                                    llm_original: tagName,
                                };
                            });
                            tagEditor.setTags(tagObjects);
                        }

                        resultsSection.classList.remove('hidden');
                        hideStatus();
                        addLogEntry('info', `Done! ${tags.length} tags generated.`);
                    } else {
                        showStatus(`Error: ${event.data.error || 'Unknown error'}`, true);
                        addLogEntry('error', event.data.error || 'Generation failed');
                    }
                }
            }
        } catch (e) {
            if (e.name !== 'AbortError') {
                showStatus(`Error: ${e.message}`, true);
                addLogEntry('error', e.message);
            }
        } finally {
            logDot.classList.remove('active');
            setLoading(btn, false);
            abortController = null;
        }
    }

    function setLoading(btn, loading) {
        btn.disabled = loading;
        btn.classList.toggle('loading', loading);
        const text = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.spinner');
        if (text) text.classList.toggle('hidden', loading);
        if (spinner) spinner.classList.toggle('hidden', !loading);
    }

    // ===========================
    //  Raw Tags Display
    // ===========================
    function renderRawTags(tags) {
        rawTagsEl.textContent = '';
        rawTagCountEl.textContent = tags.length;

        tags.forEach(tag => {
            const tagName = typeof tag === 'string' ? tag : (tag.tag || String(tag));
            const el = document.createElement('span');
            el.className = 'raw-tag';
            el.textContent = tagName;
            rawTagsEl.appendChild(el);
        });
    }

    // ===========================
    //  Tag Change Callback
    // ===========================
    function onTagsChanged() {
        finalPromptEl.textContent = tagEditor.getPromptString();
    }

    // ===========================
    //  Custom Tag
    // ===========================
    async function onCustomTagInput() {
        const query = customTagInput.value.trim();
        if (query.length < 2) {
            autocompleteDropdown.classList.add('hidden');
            return;
        }

        clearTimeout(autocompleteTimer);
        autocompleteTimer = setTimeout(async () => {
            try {
                const results = await API.searchTags(query);
                renderAutocomplete(results);
            } catch {
                autocompleteDropdown.classList.add('hidden');
            }
        }, 200);
    }

    function renderAutocomplete(results) {
        autocompleteDropdown.textContent = '';
        if (!results.length) {
            autocompleteDropdown.classList.add('hidden');
            return;
        }

        results.forEach(r => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';

            const tagSpan = document.createElement('span');
            tagSpan.textContent = r.tag;

            const countSpan = document.createElement('span');
            countSpan.className = 'ac-count';
            countSpan.textContent = formatCount(r.count);

            item.appendChild(tagSpan);
            item.appendChild(countSpan);

            item.addEventListener('click', () => {
                tagEditor.addTag(r.tag, r.category, r.count);
                customTagInput.value = '';
                autocompleteDropdown.classList.add('hidden');
            });

            autocompleteDropdown.appendChild(item);
        });

        autocompleteDropdown.classList.remove('hidden');
    }

    function addCustomTag() {
        const tag = customTagInput.value.trim().replace(/\s+/g, '_').toLowerCase();
        if (!tag) return;
        tagEditor.addTag(tag, 0, 0);
        customTagInput.value = '';
        autocompleteDropdown.classList.add('hidden');
    }

    // ===========================
    //  Copy
    // ===========================
    async function copyPrompt() {
        const text = tagEditor.getPromptString();
        if (!text) return;

        try {
            await navigator.clipboard.writeText(text);
            copyText.classList.add('hidden');
            copiedText.classList.remove('hidden');
            setTimeout(() => {
                copyText.classList.remove('hidden');
                copiedText.classList.add('hidden');
            }, 2000);
        } catch {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        }
    }

    // ===========================
    //  Status
    // ===========================
    function showStatus(msg, isError) {
        statusBar.classList.remove('hidden', 'error');
        if (isError) statusBar.classList.add('error');
        statusMessage.textContent = msg;
    }

    function hideStatus() {
        statusBar.classList.add('hidden');
    }

    // ===========================
    //  Health Check
    // ===========================
    async function checkHealth() {
        try {
            const h = await API.healthCheck();
            healthDot.className = 'health-dot ok';
            const parts = [];
            parts.push(`${h.tag_count.toLocaleString()} tags`);
            parts.push(h.index_loaded ? 'FAISS ready' : 'FAISS not loaded');
            parts.push(h.llm_configured ? 'LLM ready' : 'LLM not configured');
            healthText.textContent = parts.join(' \u00B7 ');
        } catch {
            healthDot.className = 'health-dot error';
            healthText.textContent = 'Server not connected';
        }
    }

    // ===========================
    //  Utilities
    // ===========================
    function formatCount(count) {
        if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
        if (count >= 1_000) return `${(count / 1_000).toFixed(0)}K`;
        return String(count);
    }

    // --- Boot ---
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
