document.addEventListener('DOMContentLoaded', function () {

    // Maps JS key name → Clipper chr() equivalent (single raw character)
    // These match exactly what is stored in your DBF/MySQL functions table
    const KEY_LABELS = {
        'F1' : String.fromCharCode(0xDC),   // chr(220)
        'F2' : String.fromCharCode(0xD8),   // chr(216) - pPaymntKey
        'F3' : String.fromCharCode(0xE9),   // chr(233) - pODeptKey
        'F4' : String.fromCharCode(0xF7),   // chr(247) - pSubTotKey
        'F5' : String.fromCharCode(0xF8),   // chr(248) - pISusRtKey
        'F6' : String.fromCharCode(0xF9),   // chr(249) - pVoidTrKey
        'F7' : String.fromCharCode(0xFA),   // chr(250) - pIVoidAKey
        'F8' : String.fromCharCode(0xFB),   // chr(251) - pIVoidKey
        'F9' : String.fromCharCode(0xFC),   // chr(252) - pIRetKey
        'F10': String.fromCharCode(0xFD),   // chr(253) - pPrOverKey
        'F11': String.fromCharCode(0xFE),   // chr(254) - pSTDiscKey
        'F12': String.fromCharCode(0xFF),   // chr(255) - pIDiscKey

        // Non-F-key specials — each gets its own byte so it survives the
        // 2-char DB column without colliding (previously these fell through
        // to key.substring(0,2), so 'End'/'Enter' both became "En" and all
        // four arrow keys became "Ar"). Mirrors CHAR_TO_FKEY in cashier.html.
        'Enter'     : String.fromCharCode(0x0D),
        'Escape'    : String.fromCharCode(0x1B),
        'Backspace' : String.fromCharCode(0x08),
        'Tab'       : String.fromCharCode(0x09),
        'Insert'    : String.fromCharCode(0x1A),
        'Delete'    : String.fromCharCode(0x7F),
        'Home'      : String.fromCharCode(0x01),
        'End'       : String.fromCharCode(0x02),
        'PageUp'    : String.fromCharCode(0x04),
        'PageDown'  : String.fromCharCode(0x05),
        'ArrowUp'   : String.fromCharCode(0x0B),
        'ArrowDown' : String.fromCharCode(0x0C),
        'ArrowLeft' : String.fromCharCode(0x0E),
        'ArrowRight': String.fromCharCode(0x0F),
    };

    // Display-friendly label shown in the badge (does not affect saved value)
    const KEY_DISPLAY = {
        'F1' :'F1',  'F2' :'F2',  'F3' :'F3',  'F4' :'F4',
        'F5' :'F5',  'F6' :'F6',  'F7' :'F7',  'F8' :'F8',
        'F9' :'F9',  'F10':'F10', 'F11':'F11', 'F12':'F12',
        'Enter'    :'Enter', 'Escape'  :'Esc',
        'Insert'   :'Ins',   'Delete'  :'Del',
        'Home'     :'Home',  'End'     :'End',
        'PageUp'   :'PgUp',  'PageDown':'PgDn',
        'ArrowUp'  :'↑',     'ArrowDown' :'↓',
        'ArrowLeft':'←',     'ArrowRight':'→',
        'Backspace':'Bksp',  'Tab'     :'Tab',
    };

    document.querySelectorAll('.key-capture-input').forEach(function (input) {

        if (input.value) {
            updateBadge(input, input.value);
        }

        input.addEventListener('focus', function () {
            input.classList.add('listening');
            input.placeholder = '🎯 Press a key now...';
        });

        input.addEventListener('blur', function () {
            input.classList.remove('listening');
            input.placeholder = 'Click here, then press a key...';
        });

        input.addEventListener('keydown', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const key = e.key;
            if (['Control', 'Alt', 'Shift', 'Meta'].includes(key)) return;

            let keycode = '';
            let displayName = '';

            if (KEY_LABELS[key] !== undefined) {
                // Function key — store raw Clipper chr() character
                keycode = KEY_LABELS[key];
                displayName = KEY_DISPLAY[key] || key;
            } else if (KEY_DISPLAY[key] !== undefined) {
                // Special key with no Clipper mapping — store as-is
                keycode = key.substring(0, 2);
                displayName = KEY_DISPLAY[key];
            } else if (key.length === 1) {
                // Regular printable character — store uppercase (matches Clipper upper(chr(ckey)))
                keycode = key.toUpperCase();
                displayName = keycode;
            } else {
                return; // unknown key, ignore
            }

            input.value = keycode;
            updateBadge(input, displayName);
            input.classList.add('key-captured');
            setTimeout(() => input.classList.remove('key-captured'), 600);
        });
    });

    function updateBadge(input, label) {
        const existing = input.parentNode.querySelector('.key-badge');
        if (existing) existing.remove();

        const badge = document.createElement('span');
        badge.className = 'key-badge';

        // Show human-readable label in badge instead of raw char
        const DISPLAY_MAP = {
            [String.fromCharCode(0xFF)]: 'F12',
            [String.fromCharCode(0xFE)]: 'F11',
            [String.fromCharCode(0xFD)]: 'F10',
            [String.fromCharCode(0xFC)]: 'F9',
            [String.fromCharCode(0xFB)]: 'F8',
            [String.fromCharCode(0xFA)]: 'F7',
            [String.fromCharCode(0xF9)]: 'F6',
            [String.fromCharCode(0xF8)]: 'F5',
            [String.fromCharCode(0xF7)]: 'F4',
            [String.fromCharCode(0xE9)]: 'F3',
            [String.fromCharCode(0xD8)]: 'F2',
            [String.fromCharCode(0xDC)]: 'F1',
        };

        badge.textContent = DISPLAY_MAP[label] || label;
        input.parentNode.style.position = 'relative';
        input.parentNode.appendChild(badge);
    }
});