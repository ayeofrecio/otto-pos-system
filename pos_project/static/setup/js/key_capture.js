const KEY_OPTIONS = [
    { value: String.fromCharCode(0xDC), label: 'F1' },
    { value: String.fromCharCode(0xD8), label: 'F2' },
    { value: String.fromCharCode(0xE9), label: 'F3' },
    { value: String.fromCharCode(0xF7), label: 'F4' },
    { value: String.fromCharCode(0xF8), label: 'F5' },
    { value: String.fromCharCode(0xF9), label: 'F6' },
    { value: String.fromCharCode(0xFA), label: 'F7' },
    { value: String.fromCharCode(0xFB), label: 'F8' },
    { value: String.fromCharCode(0xFC), label: 'F9' },
    { value: String.fromCharCode(0xFD), label: 'F10' },
    { value: String.fromCharCode(0xFE), label: 'F11' },
    { value: String.fromCharCode(0xFF), label: 'F12' },
    { value: 'CR', label: 'Enter' },
    { value: 'EC', label: 'Esc' },
    { value: 'TB', label: 'Tab' },
    { value: 'BK', label: 'Bksp' },
    { value: 'HM', label: 'Home' },
    { value: 'ND', label: 'End' },
    { value: 'PU', label: 'PgUp' },
    { value: 'PD', label: 'PgDn' },
    { value: 'AU', label: '↑' },
    { value: 'AD', label: '↓' },
    { value: 'AL', label: '←' },
    { value: 'AR', label: '→' },
    { value: 'IC', label: 'Ins' },
    { value: 'DL', label: 'Del' },
];

for (let code = 0x30; code <= 0x39; code += 1) {
    KEY_OPTIONS.push({ value: String.fromCharCode(code), label: String.fromCharCode(code) });
}

for (let code = 0x41; code <= 0x5A; code += 1) {
    KEY_OPTIONS.push({ value: String.fromCharCode(code), label: String.fromCharCode(code) });
}

const KEY_SECTIONS = [
    { title: 'Function Keys', options: KEY_OPTIONS.slice(0, 12) },
    { title: 'Navigation / Editing', options: KEY_OPTIONS.slice(12, 26) },
    { title: 'Digits / Letters', options: KEY_OPTIONS.slice(26) },
];

const VALUE_TO_LABEL = KEY_OPTIONS.reduce(function (lookup, option) {
    lookup[option.value] = option.label;
    return lookup;
}, {});

function storedValueToLabel(value) {
    if (!value) {
        return '';
    }

    if (VALUE_TO_LABEL[value]) {
        return VALUE_TO_LABEL[value];
    }

    if (value.length === 1) {
        return value.toUpperCase();
    }

    return value;
}

function getStoredValue(input) {
    return input.dataset.storedValue || input.value || '';
}

function setStoredValue(input, value) {
    input.dataset.storedValue = value || '';
    input.value = storedValueToLabel(value);
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

function refreshVisibleValue(input) {
    const storedValue = getStoredValue(input);
    input.value = storedValue ? storedValueToLabel(storedValue) : '';
    input.placeholder = storedValue ? '' : 'No key selected';
}

function buildPickerPanel(input) {
    const picker = document.createElement('div');
    picker.className = 'key-picker-panel key-picker-panel-inline';
    picker.setAttribute('role', 'group');
    picker.setAttribute('aria-label', 'Pick a key');

    const header = document.createElement('div');
    header.className = 'key-picker-header';
    header.textContent = 'Pick a key';
    picker.appendChild(header);

    const sections = document.createElement('div');
    sections.className = 'key-picker-sections';

    KEY_SECTIONS.forEach(function (section) {
        const sectionWrap = document.createElement('div');
        sectionWrap.className = 'key-picker-section';

        const sectionTitle = document.createElement('div');
        sectionTitle.className = 'key-picker-section-title';
        sectionTitle.textContent = section.title;
        sectionWrap.appendChild(sectionTitle);

        const grid = document.createElement('div');
        grid.className = 'key-picker-grid';

        section.options.forEach(function (option) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'key-picker-option';
            button.textContent = option.label;
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                setStoredValue(input, option.value);
                refreshVisibleValue(input);
            });
            grid.appendChild(button);
        });

        sectionWrap.appendChild(grid);
        sections.appendChild(sectionWrap);
    });

    picker.appendChild(sections);

    const footer = document.createElement('div');
    footer.className = 'key-picker-footer';

    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.className = 'key-picker-clear';
    clearButton.textContent = 'Clear';
    clearButton.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        setStoredValue(input, '');
        refreshVisibleValue(input);
    });

    footer.appendChild(clearButton);
    picker.appendChild(footer);

    return picker;
}

function buildPickerWidget(input) {
    if (input.dataset.keyPickerReady === '1') {
        return;
    }

    input.dataset.keyPickerReady = '1';
    input.dataset.storedValue = input.value || '';
    input.readOnly = true;
    input.tabIndex = -1;

    const shell = document.createElement('span');
    shell.className = 'key-picker-shell';

    const parent = input.parentNode;
    parent.insertBefore(shell, input);
    shell.appendChild(input);
    shell.appendChild(buildPickerPanel(input));

    refreshVisibleValue(input);

    const form = input.form;
    if (form && !form.dataset.keyPickerBound) {
        form.dataset.keyPickerBound = '1';
        form.addEventListener('submit', function () {
            form.querySelectorAll('.key-capture-input').forEach(function (field) {
                field.value = getStoredValue(field);
            });
        });
    }
}

function initKeyCaptureWidgets() {
    document.querySelectorAll('.key-capture-input').forEach(function (input) {
        buildPickerWidget(input);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initKeyCaptureWidgets);
} else {
    initKeyCaptureWidgets();
}