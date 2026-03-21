/**
 * POS Cashier - barcode handling, live time, toast dismiss, item search
 */
document.addEventListener('keydown', function (evt) {
  console.log('key:', evt.key, '| code:', evt.code);


(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Live time tick
  // ---------------------------------------------------------------------------
  function updateTime() {
    const now = new Date();
    const timeEl = document.getElementById('live-time');
    const dateEl = document.getElementById('live-date');
    if (timeEl) {
      timeEl.textContent = now.toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
      });
    }
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString('en-US', {
        weekday: 'long', month: 'short', day: 'numeric', year: 'numeric'
      });
    }
  }
  if (document.getElementById('live-time')) {
    setInterval(updateTime, 1000);
  }

  // ---------------------------------------------------------------------------
  // Dynamic max-height for Items Entered based on bottom bar position
  // ---------------------------------------------------------------------------
  function updateScannedItemsMaxHeight() {
    const inner = document.querySelector('.scanned-items-inner');
    const actionsBar = document.querySelector('.actions');
    if (!inner || !actionsBar) { return; }
    const innerRect = inner.getBoundingClientRect();
    const barRect = actionsBar.getBoundingClientRect();
    const gap = 8;
    const maxH = Math.max(100, barRect.top - innerRect.top - gap);
    inner.style.maxHeight = maxH + 'px';
  }
  function onResizeOrLoad() {
    updateScannedItemsMaxHeight();
  }
  if (document.querySelector('.scanned-items-inner')) {
    onResizeOrLoad();
    window.addEventListener('resize', onResizeOrLoad);
  }
  // Re-run when HTMX updates the page (cart updates swap scanned-items-panel oob)
  var lastRequestWasCartAdd = false;
  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath || '';
    lastRequestWasCartAdd = path.indexOf('/cart/add') !== -1;
  });
  document.body.addEventListener('htmx:afterSettle', function () {
    updateScannedItemsMaxHeight();
    if (lastRequestWasCartAdd) {
      lastRequestWasCartAdd = false;
      const scannedInner = document.querySelector('.scanned-items-inner');
      if (scannedInner) { scannedInner.scrollTop = scannedInner.scrollHeight; }
      const cartList = document.querySelector('.cart-list');
      if (cartList) { cartList.scrollTop = cartList.scrollHeight; }
    }
  });

  // Capture barcode value just before htmx submits (needed for search prefill on not-found)
  var lastScannedBarcode = '';
  const barcodeFormEl = document.getElementById('barcode-form');
  if (barcodeFormEl) {
    barcodeFormEl.addEventListener('submit', function () {
      const inp = document.getElementById('barcode-input');
      lastScannedBarcode = inp ? inp.value.trim() : '';
    });
  }

  // ---------------------------------------------------------------------------
  // Toast auto-dismiss + open search on item-not-found
  // ---------------------------------------------------------------------------
  document.body.addEventListener('htmx:afterSwap', function (evt) {
    if (evt.detail.target.id !== 'toast-container') { return; }
    const container = evt.detail.target;
    if (!container.innerHTML) { return; }
    // Auto-dismiss toast after 2 s
    setTimeout(function () { container.innerHTML = ''; }, 2000);
    // If item not found, open search modal prefilled with what was scanned
    if (container.querySelector('[data-open-search]')) {
      setTimeout(function () {
        window.openSearchModal(lastScannedBarcode || '');
      }, 120);
    }
  });

  // After cart_add: clear barcode, reset qty to 1, reset item discount, refocus
  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath;
    if (!path) { return; }
    const barcodeInput = document.getElementById('barcode-input');
    const qtyInput = document.getElementById('qty-input');
    if (barcodeInput && path.includes('/cart/add')) {
      barcodeInput.value = '';
      if (qtyInput) { qtyInput.value = '1'; }
      // Item discount is one-shot — reset after each scan
      window.clearDiscount();
      barcodeInput.focus();
    } else if (barcodeInput && path.includes('/cart/')) {
      barcodeInput.focus();
    }
  });

  // F2 → focus qty input; F3 → open discount modal
  // * in empty barcode field → focus qty input
  document.addEventListener('keydown', function (evt) {
    const barcodeInput = document.getElementById('barcode-input');
    const qtyInput = document.getElementById('qty-input');

    if (evt.key === 'F1') {
      evt.preventDefault();
      window.openSearchModal();
      return;
    }

    if (evt.key === 'F2') {
      evt.preventDefault();
      if (qtyInput) { qtyInput.focus(); qtyInput.select(); }
      return;
    }

    if (evt.key === POS_KEYS.iDisc) {
      evt.preventDefault();
      window.openDiscountModal();
      return;
    }

    if (evt.key === POS_KEYS.stDisc) {
      evt.preventDefault();
      window.openTransDiscModal();
      return;
    }

    // if (evt.key === POS_KEYS.stDisc) {
    //   evt.preventDefault();
    //   window.openPayModal();
    //   return;
    // }

    if (evt.key === '*' && qtyInput && document.activeElement === barcodeInput && !barcodeInput.value) {
      evt.preventDefault();
      qtyInput.focus();
      qtyInput.select();
      return;
    }

    if (evt.key === 'Escape') {
      const payModal = document.getElementById('pay-modal');
      const discModal = document.getElementById('discount-modal');
      const tdModal = document.getElementById('trans-disc-modal');
      if (payModal && payModal.classList.contains('open')) { window.closePayModal(); }
      else if (discModal && discModal.classList.contains('open')) { window.closeDiscountModal(); }
      else if (tdModal && tdModal.classList.contains('open')) { window.closeTransDiscModal(); }
    }
  });

  // After editing qty, pressing Enter moves focus to barcode input
  const qtyInputEl = document.getElementById('qty-input');
  if (qtyInputEl) {
    qtyInputEl.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        const barcodeInput = document.getElementById('barcode-input');
        if (barcodeInput) { barcodeInput.focus(); }
      }
    });
  }

  // Pressing Enter in the barcode field submits the form.
  // (Required because adding the qty number input means the browser no longer
  // auto-submits a multi-input form on Enter.)
  const barcodeInputEl = document.getElementById('barcode-input');
  if (barcodeInputEl) {
    barcodeInputEl.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        const form = document.getElementById('barcode-form');
        if (form) {
          form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Discount Modal (F3)
  // ---------------------------------------------------------------------------
  var pendingDisc = { pct: 0, type: '', label: '' };

  window.openDiscountModal = function () {
    const modal = document.getElementById('discount-modal');
    const input = document.getElementById('disc-pct-modal-input');
    if (!modal) { return; }
    modal.classList.add('open');
    // Pre-fill with current pending discount
    if (input) { input.value = pendingDisc.pct || 0; }
    refreshDiscTypeBtns(pendingDisc.type);
    setTimeout(function () {
      if (pendingDisc.type === 'REG' || !pendingDisc.type) {
        if (input) { input.focus(); input.select(); }
      }
    }, 80);
  };

  window.closeDiscountModal = function () {
    const modal = document.getElementById('discount-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeDiscountModalOutside = function (evt) {
    if (evt.target === document.getElementById('discount-modal')) {
      window.closeDiscountModal();
    }
  };

  window.selectDiscType = function (btn, code, label, defaultPct) {
    pendingDisc.type = code;
    pendingDisc.label = label;
    refreshDiscTypeBtns(code);
    const input = document.getElementById('disc-pct-modal-input');
    if (input) {
      if (defaultPct > 0) { input.value = defaultPct; }
      input.focus();
      input.select();
    }
  };

  function refreshDiscTypeBtns(selectedCode) {
    document.querySelectorAll('.disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-disc-code') === selectedCode);
    });
  }

  window.applyDiscount = function () {
    const input = document.getElementById('disc-pct-modal-input');
    const pct = parseFloat(input ? input.value : 0) || 0;
    if (pct <= 0) {
      window.removeDiscountAndClose();
      return;
    }
    pendingDisc.pct = pct;
    if (!pendingDisc.type) {
      pendingDisc.type = 'REG';
      pendingDisc.label = 'Regular';
    }
    syncDiscFields();
    window.closeDiscountModal();
  };

  window.removeDiscountAndClose = function () {
    window.clearDiscount();
    window.closeDiscountModal();
  };

  window.clearDiscount = function () {
    pendingDisc = { pct: 0, type: '', label: '' };
    syncDiscFields();
  };

  function syncDiscFields() {
    const badge = document.getElementById('disc-badge');
    const badgeText = document.getElementById('disc-badge-text');
    const pctField = document.getElementById('disc-pct-field');
    const typeField = document.getElementById('disc-type-field');
    if (pctField) { pctField.value = pendingDisc.pct; }
    if (typeField) { typeField.value = pendingDisc.type; }
    if (badge) {
      if (pendingDisc.pct > 0) {
        badge.classList.add('visible');
        if (badgeText) {
          badgeText.textContent = pendingDisc.pct + '% — ' + (pendingDisc.label || pendingDisc.type);
        }
      } else {
        badge.classList.remove('visible');
      }
    }
  }

  // Allow Enter in the discount % field to immediately apply
  const discPctInput = document.getElementById('disc-pct-modal-input');
  if (discPctInput) {
    discPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyDiscount(); }
    });
  }

  // ---------------------------------------------------------------------------
  // Line Discount Modal (click row in Items Entered)
  // ---------------------------------------------------------------------------
  var lineDiscRecCtr = null;
  var lineDiscType = '';

  window.openLineDiscModal = function (recCtr) {
    lineDiscRecCtr = recCtr;
    lineDiscType = 'REG';
    const modal = document.getElementById('line-disc-modal');
    const recInput = document.getElementById('line-disc-rec-ctr');
    const pctInput = document.getElementById('line-disc-pct-input');
    const typeInput = document.getElementById('line-disc-type');
    if (!modal || !recInput) { return; }
    recInput.value = recCtr;
    typeInput.value = 'REG';
    pctInput.value = 0;
    refreshLineDiscTypeBtns('REG');
    modal.classList.add('open');
    setTimeout(function () { if (pctInput) { pctInput.focus(); pctInput.select(); } }, 80);
  };

  window.closeLineDiscModal = function () {
    const modal = document.getElementById('line-disc-modal');
    if (modal) { modal.classList.remove('open'); }
    lineDiscRecCtr = null;
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeLineDiscModalOutside = function (evt) {
    if (evt.target === document.getElementById('line-disc-modal')) {
      window.closeLineDiscModal();
    }
  };

  window.selectLineDiscType = function (btn, code, label, defaultPct) {
    lineDiscType = code;
    refreshLineDiscTypeBtns(code);
    const typeInput = document.getElementById('line-disc-type');
    const pctInput = document.getElementById('line-disc-pct-input');
    if (typeInput) { typeInput.value = code; }
    if (pctInput) {
      if (defaultPct > 0) { pctInput.value = defaultPct; }
      pctInput.focus();
      pctInput.select();
    }
  };

  function refreshLineDiscTypeBtns(selectedCode) {
    document.querySelectorAll('.line-disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-code') === selectedCode);
    });
  }

  window.applyLineDisc = function () {
    const pctInput = document.getElementById('line-disc-pct-input');
    const pct = parseFloat(pctInput ? pctInput.value : 0) || 0;
    if (pct <= 0) {
      window.removeLineDiscAndClose();
      return;
    }
    const form = document.getElementById('line-disc-form');
    if (form) {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    }
    window.closeLineDiscModal();
  };

  window.removeLineDiscAndClose = function () {
    const pctInput = document.getElementById('line-disc-pct-input');
    const typeInput = document.getElementById('line-disc-type');
    if (pctInput) { pctInput.value = 0; }
    if (typeInput) { typeInput.value = ''; }
    const form = document.getElementById('line-disc-form');
    if (form) {
      const recInput = document.getElementById('line-disc-rec-ctr');
      if (recInput && recInput.value) {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    }
    window.closeLineDiscModal();
  };

  const lineDiscPctInput = document.getElementById('line-disc-pct-input');
  if (lineDiscPctInput) {
    lineDiscPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyLineDisc(); }
    });
  }

  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath || '';
    if (path.indexOf('/cart/line-disc') !== -1) {
      const barcodeInput = document.getElementById('barcode-input');
      if (barcodeInput) { barcodeInput.focus(); }
    }
  });

  // ---------------------------------------------------------------------------
  // Transaction Subtotal Discount Modal (F4)
  // ---------------------------------------------------------------------------
  // Initialise from server-rendered state so it survives page reload
  var pendingTransDisc = (typeof INITIAL_TRANS_DISC !== 'undefined')
    ? { pct: INITIAL_TRANS_DISC.pct, type: INITIAL_TRANS_DISC.type, label: INITIAL_TRANS_DISC.label }
    : { pct: 0, type: '', label: '' };

  window.openTransDiscModal = function () {
    const modal = document.getElementById('trans-disc-modal');
    const input = document.getElementById('trans-disc-pct-input');
    if (!modal) { return; }
    modal.classList.add('open');
    if (input) { input.value = pendingTransDisc.pct || 0; }
    refreshTransDiscBtns(pendingTransDisc.type);
    setTimeout(function () { if (input) { input.focus(); input.select(); } }, 80);
  };

  window.closeTransDiscModal = function () {
    const modal = document.getElementById('trans-disc-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeTransDiscModalOutside = function (evt) {
    if (evt.target === document.getElementById('trans-disc-modal')) {
      window.closeTransDiscModal();
    }
  };

  window.selectTransDiscType = function (btn, code, label, defaultPct) {
    pendingTransDisc.type = code;
    pendingTransDisc.label = label;
    refreshTransDiscBtns(code);
    const input = document.getElementById('trans-disc-pct-input');
    if (input) {
      if (defaultPct > 0) { input.value = defaultPct; }
      input.focus(); input.select();
    }
  };

  function refreshTransDiscBtns(selectedCode) {
    document.querySelectorAll('#trans-disc-modal .disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-tdcode') === selectedCode);
    });
  }

  window.applyTransDisc = function () {
    const input = document.getElementById('trans-disc-pct-input');
    const pct = parseFloat(input ? input.value : 0) || 0;
    if (pct <= 0) { window.removeTransDiscAndClose(); return; }
    pendingTransDisc.pct = pct;
    if (!pendingTransDisc.type) { pendingTransDisc.type = 'REG'; pendingTransDisc.label = 'Regular'; }
    submitTransDisc();
    window.closeTransDiscModal();
  };

  window.removeTransDiscAndClose = function () {
    pendingTransDisc = { pct: 0, type: '', label: '' };
    submitTransDisc();
    window.closeTransDiscModal();
  };

  function submitTransDisc() {
    const form = document.getElementById('trans-disc-form');
    if (!form) { return; }
    document.getElementById('trans-disc-pct-hidden').value   = pendingTransDisc.pct;
    document.getElementById('trans-disc-type-hidden').value  = pendingTransDisc.type;
    document.getElementById('trans-disc-label-hidden').value = pendingTransDisc.label;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  }

  // Enter in trans-disc % input applies immediately
  const tdPctInput = document.getElementById('trans-disc-pct-input');
  if (tdPctInput) {
    tdPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyTransDisc(); }
    });
  }

  // ---------------------------------------------------------------------------
  // Item Search Modal
  // ---------------------------------------------------------------------------
  let searchTimer = null;

  window.openSearchModal = function (prefill) {
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('modal-search-input');
    modal.classList.add('open');
    setTimeout(function () {
      input.focus();
      if (prefill && prefill.length >= 1) {
        input.value = prefill;
        // Fire input event so the live-search debounce triggers
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, 80);
  };

  window.closeSearchModal = function () {
    document.getElementById('search-modal').classList.remove('open');
    document.getElementById('modal-search-input').value = '';
    document.getElementById('modal-results').innerHTML =
      '<p class="search-hint">Type at least 2 characters to search</p>';
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeSearchModalOutside = function (evt) {
    if (evt.target === document.getElementById('search-modal')) {
      window.closeSearchModal();
    }
  };

  // ---------------------------------------------------------------------------
  // Pay Modal (tender floating window)
  // ---------------------------------------------------------------------------
  window.closePayModal = function () {
    const modal = document.getElementById('pay-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closePayModalOutside = function (evt) {
    if (evt.target === document.getElementById('pay-modal')) {
      window.closePayModal();
    }
  };

  window.openPayModal = function () {
    const btn = document.getElementById('pay-trigger-btn');
    if (btn) { btn.click(); }
  };

  // Close modal on Escape
  document.addEventListener('keydown', function (evt) {
    if (evt.key === 'Escape') {
      const modal = document.getElementById('search-modal');
      if (modal && modal.classList.contains('open')) {
        window.closeSearchModal();
      }
    }
  });

  // Live search as user types
  const modalInput = document.getElementById('modal-search-input');
  if (modalInput) {
    modalInput.addEventListener('input', function () {
      clearTimeout(searchTimer);
      const q = modalInput.value.trim();
      if (q.length < 2) {
        document.getElementById('modal-results').innerHTML =
          '<p class="search-hint">Type at least 2 characters to search</p>';
        return;
      }
      searchTimer = setTimeout(function () { doSearch(q); }, 250);
    });
  }

  function doSearch(q) {
    const resultsEl = document.getElementById('modal-results');
    resultsEl.innerHTML = '<p class="search-hint">Searching…</p>';

    fetch(ITEM_SEARCH_URL + '?q=' + encodeURIComponent(q), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { renderResults(data.results); })
      .catch(function () {
        resultsEl.innerHTML = '<p class="search-empty">Search failed. Please try again.</p>';
      });
  }

  function renderResults(results) {
    const resultsEl = document.getElementById('modal-results');
    if (!results || results.length === 0) {
      resultsEl.innerHTML = '<p class="search-empty">No items found.</p>';
      return;
    }

    const rows = results.map(function (item) {
      const variant = [item.size, item.color].filter(Boolean).join('/');
      const variantHtml = variant ? '<span class="search-result-variant">(' + variant + ')</span>' : '';
      return '<div class="search-result" onclick="selectSearchResult(\'' +
        escHtml(item.barcode) + '\')" title="Click to add to cart">' +
        '<span class="search-result-desc">' + escHtml(item.description) +
        ' ' + variantHtml + '</span>' +
        '<span class="search-result-code">' + escHtml(item.code) + '</span>' +
        '<span class="search-result-variant">' + escHtml(item.barcode) + '</span>' +
        '<span class="search-result-price">₱' + parseFloat(item.price).toLocaleString('en-PH', {minimumFractionDigits: 2}) + '</span>' +
        '</div>';
    });
    resultsEl.innerHTML = rows.join('');
  }

  window.selectSearchResult = function (barcode) {
    window.closeSearchModal();

    // Put barcode into input and submit via HTMX
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) {
      barcodeInput.value = barcode;
      document.getElementById('barcode-form').dispatchEvent(new Event('submit', { bubbles: true }));
    }
  };

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

})();
