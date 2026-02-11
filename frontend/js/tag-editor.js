/**
 * Tag chip editor component for managing matched tags.
 */
class TagEditor {
    constructor(containerEl, onChangeCallback) {
        this.container = containerEl;
        this.onChange = onChangeCallback;
        this.tags = [];
    }

    setTags(tagCandidates) {
        this.tags = tagCandidates.map(t => ({
            ...t,
            selected: t.match_method === 'exact' || t.match_method === 'alias' || t.similarity_score >= 0.7,
        }));
        this.render();
        this._notifyChange();
    }

    addTag(tag, category, count, matchMethod = 'exact') {
        if (this.tags.some(t => t.tag === tag)) return;
        this.tags.push({
            tag,
            category,
            count,
            match_method: matchMethod,
            similarity_score: matchMethod === 'exact' || matchMethod === 'alias' ? 1.0 : 0.0,
            llm_original: 'custom',
            selected: true,
        });
        this.render();
        this._notifyChange();
    }

    selectAll() {
        this.tags.forEach(t => t.selected = true);
        this.render();
        this._notifyChange();
    }

    deselectAll() {
        this.tags.forEach(t => t.selected = false);
        this.render();
        this._notifyChange();
    }

    getSelectedTags() {
        return this.tags.filter(t => t.selected).map(t => t.tag);
    }

    getPromptString() {
        return this.getSelectedTags().map(t => t.replaceAll('_', ' ')).join(', ');
    }

    clear() {
        this.tags = [];
        this.container.textContent = '';
        this._notifyChange();
    }

    render() {
        this.container.textContent = '';

        if (this.tags.length === 0) return;

        // Legend
        this.container.appendChild(this._buildLegend());

        // Tag chips grid
        const grid = document.createElement('div');
        grid.className = 'tag-grid';

        this.tags.forEach((t, idx) => {
            grid.appendChild(this._buildChip(t, idx));
        });

        this.container.appendChild(grid);
    }

    _buildLegend() {
        const legend = document.createElement('div');
        legend.className = 'legend';

        const usedMethods = new Set(this.tags.map(t => t.match_method));

        const methods = [
            { label: 'Exact', cls: 'exact' },
            { label: 'Alias', cls: 'alias' },
            { label: 'Fuzzy', cls: 'fuzzy' },
            { label: 'Vector', cls: 'vector' },
            { label: 'Custom', cls: 'custom' },
            { label: 'Unmatched', cls: 'unmatched' },
        ];

        methods.filter(m => usedMethods.has(m.cls)).forEach(m => {
            const item = document.createElement('span');
            item.className = 'legend-item';

            const dot = document.createElement('span');
            dot.className = `match-dot ${m.cls}`;

            item.appendChild(dot);
            item.appendChild(document.createTextNode(` ${m.label}`));
            legend.appendChild(item);
        });

        return legend;
    }

    _buildChip(t, idx) {
        const chip = document.createElement('div');
        chip.className = `tag-chip${t.selected ? ' selected' : ''}`;
        chip.dataset.index = idx;

        // Match method dot
        const dot = document.createElement('span');
        dot.className = `match-dot ${t.match_method}`;
        chip.appendChild(dot);

        // Tag name
        const name = document.createElement('span');
        name.className = 'tag-name';
        name.textContent = t.tag;
        chip.appendChild(name);

        // Meta info (score + count)
        const meta = document.createElement('span');
        meta.className = 'tag-meta';
        const parts = [];
        if (t.similarity_score < 1.0) {
            parts.push(`${(t.similarity_score * 100).toFixed(0)}%`);
        }
        if (t.count > 0) {
            parts.push(this._formatCount(t.count));
        }
        if (parts.length > 0) {
            meta.textContent = parts.join(' \u00B7 ');
            chip.appendChild(meta);
        }

        // Remove button
        const remove = document.createElement('span');
        remove.className = 'tag-remove';
        remove.textContent = '\u00D7';
        remove.dataset.action = 'remove';
        chip.appendChild(remove);

        // Tooltip
        const tooltip = document.createElement('span');
        tooltip.className = 'tooltip';
        tooltip.textContent = `${t.llm_original} \u2192 ${t.tag} | ${t.match_method} (${(t.similarity_score * 100).toFixed(1)}%) | ${this._categoryName(t.category)} | ${t.count.toLocaleString()}`;
        chip.appendChild(tooltip);

        // Event handler
        chip.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'remove') {
                this.tags.splice(idx, 1);
                this.render();
                this._notifyChange();
                return;
            }
            t.selected = !t.selected;
            this.render();
            this._notifyChange();
        });

        return chip;
    }

    _notifyChange() {
        if (this.onChange) this.onChange();
    }

    _formatCount(count) {
        if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
        if (count >= 1_000) return `${(count / 1_000).toFixed(0)}K`;
        return String(count);
    }

    _categoryName(cat) {
        const names = { 0: 'General', 1: 'Artist', 3: 'Copyright', 4: 'Character', 5: 'Meta' };
        return names[cat] || `Cat ${cat}`;
    }
}
