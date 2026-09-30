        // Reverse map: Clipper chr() value → physical key name (e.g. "\xff" → "F12")
        // Mirrors KEY_LABELS in key_capture.js
        const CHAR_TO_FKEY = {
            [String.fromCharCode(0xDC)]: 'F1',
            [String.fromCharCode(0xD8)]: 'F2',
            [String.fromCharCode(0xE9)]: 'F3',
            [String.fromCharCode(0xF7)]: 'F4',
            [String.fromCharCode(0xF8)]: 'F5',
            [String.fromCharCode(0xF9)]: 'F6',
            [String.fromCharCode(0xFA)]: 'F7',
            [String.fromCharCode(0xFB)]: 'F8',
            [String.fromCharCode(0xFC)]: 'F9',
            [String.fromCharCode(0xFD)]: 'F10',
            [String.fromCharCode(0xFE)]: 'F11',
            [String.fromCharCode(0xFF)]: 'F12',
            // Non-F-key specials — see matching KEY_LABELS in key_capture.js
            [String.fromCharCode(0x0D)]: 'Enter',
            [String.fromCharCode(0x1B)]: 'Escape',
            [String.fromCharCode(0x08)]: 'Backspace',
            [String.fromCharCode(0x09)]: 'Tab',
            [String.fromCharCode(0x1A)]: 'Insert',
            [String.fromCharCode(0x7F)]: 'Delete',
            [String.fromCharCode(0x01)]: 'Home',
            [String.fromCharCode(0x02)]: 'End',
            [String.fromCharCode(0x04)]: 'PageUp',
            [String.fromCharCode(0x05)]: 'PageDown',
            [String.fromCharCode(0x0B)]: 'ArrowUp',
            [String.fromCharCode(0x0C)]: 'ArrowDown',
            [String.fromCharCode(0x0E)]: 'ArrowLeft',
            [String.fromCharCode(0x0F)]: 'ArrowRight',
        };
        // Translate all POS_KEYS values to their physical key names for keydown comparisons
        const POS_FKEYS = {};
        for (const fn in POS_KEYS) {
            const raw = POS_KEYS[fn];
            const physKey = CHAR_TO_FKEY[raw] ||
                (raw && raw.length === 1 && raw.charCodeAt(0) >= 0x20 && raw.charCodeAt(0) < 0x7F ? raw : null);
            if (physKey) POS_FKEYS[fn] = physKey;
        }

        // Human-readable labels for each POS function key slot
        const POS_KEY_LABELS = {
            iDisc: 'Item Discount',
            iView: 'Item Lookup',
            stDisc: 'SubTotal Discount',
            prOver: 'Price Override',
            iRet: 'Item Return',
            iVoid: 'Line Item Void',
            iVoidA: 'Void All Items',
            voidTr: 'Void Previous Transaction',
            iSusRt: 'Transaction Suspend / Retrieve',
            stat: 'Sales Status',
            subTot: 'SubTotal',
            paymnt: 'Payment',
            iQty: 'Quantity',
            tsRep: 'X-Reading / Terminal Sales',
            zRead: 'Z-Reading / End of Day',
            jRep: 'Journal Report',
            sOff: 'Sign Off / Log Off',
            menu: 'Menu Key',
            sman: 'Reprint Transactions',
            cWithD: 'Cash Withdrawal',
            resendTxt: 'Resend Text File',
        };