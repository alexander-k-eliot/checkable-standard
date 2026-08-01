// Receipts Standard renderer (Priority Goal 1B, Phase 0, 2026-07-31).
// Embeddable, no build step, no framework. Any site can drop this in:
//   <div id="receipts"></div>
//   <script src="https://receipts.clickcoded.com/renderer/render.js"></script>
//   <script>renderReceipts('receipts', 'https://example.com/receipts.json');</script>
// Fetches a receipts.json, renders a human-readable page in-place. Read-only -- never sends
// the manifest anywhere, never modifies it. If the manifest doesn't parse or is missing
// required fields, renders an honest error, not a blank div or a fake-looking success state.
(function (global) {
  'use strict';

  var CATEGORY_LABELS = {
    revenue: 'Revenue', delivery: 'Delivery', send: 'Send', correction: 'Correction',
    grant: 'Grant', infrastructure: 'Infrastructure', disclosure: 'Disclosure', challenge: 'Challenge'
  };
  var INDEPENDENCE_LABELS = {
    'third-party': 'third-party evidence', 'payment-processor': 'payment-processor evidence',
    'own-site': 'own-site evidence'
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (html != null) e.innerHTML = html;
    return e;
  }

  function renderError(container, message) {
    container.innerHTML = '';
    container.appendChild(el('div', { style: 'border:1px solid #e86a5a;border-left:4px solid #e86a5a;border-radius:8px;padding:14px 16px;font-family:system-ui,sans-serif;font-size:.92rem;color:#e86a5a' },
      esc(message)));
  }

  function claimRow(claim, byId) {
    var correctsNote = '';
    if (claim.corrects && byId[claim.corrects]) {
      correctsNote = '<div style="font-size:.8rem;opacity:.7;margin-top:4px">&#8618; corrects <code>' + esc(claim.corrects) + '</code></div>';
    }
    var correctedByIds = Object.keys(byId).filter(function (id) { return byId[id].corrects === claim.id; });
    var correctedByNote = correctedByIds.length
      ? '<div style="font-size:.8rem;color:#e8863f;margin-top:4px">&#9888; corrected later by ' + correctedByIds.map(function (id) { return '<code>' + esc(id) + '</code>'; }).join(', ') + '</div>'
      : '';
    var ev = claim.evidence || {};
    var indep = ev.independence ? ' &middot; ' + esc(INDEPENDENCE_LABELS[ev.independence] || ev.independence) : '';
    var conf = claim.confidence
      ? '<div style="font-size:.8rem;opacity:.75;margin-top:4px">confidence: ' + esc(claim.confidence.level) + (claim.confidence.caveat ? ' &mdash; ' + esc(claim.confidence.caveat) : '') + '</div>'
      : '';
    var evLink = ev.ref && /^https?:\/\//.test(ev.ref)
      ? '<a href="' + esc(ev.ref) + '" style="color:inherit">evidence</a>'
      : esc(ev.ref || 'evidence disclosed on request');
    return '<div style="border:1px solid rgba(128,128,128,.25);border-radius:8px;padding:12px 14px;margin:10px 0">' +
      '<div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;opacity:.6;font-family:monospace">' +
      esc(claim.id) + ' &middot; ' + esc(claim.date) + ' &middot; ' + esc(CATEGORY_LABELS[claim.category] || claim.category) + '</div>' +
      '<div style="margin-top:6px">' + esc(claim.claim) + '</div>' +
      '<div style="font-size:.8rem;opacity:.75;margin-top:6px">' + esc(claim.verifiability) + indep + ' &middot; ' + evLink + '</div>' +
      conf + correctsNote + correctedByNote +
      '</div>';
  }

  function renderManifest(container, data, sourceUrl) {
    var required = ['operator', 'generated', 'rules', 'claims'];
    var missing = required.filter(function (k) { return !(k in data); });
    if (missing.length) {
      renderError(container, 'This doesn\'t look like a conforming manifest -- missing: ' + missing.join(', '));
      return;
    }
    var op = data.operator || {};
    var claims = (data.claims || []).slice().sort(function (a, b) { return (a.date || '') < (b.date || '') ? 1 : -1; });
    var byId = {};
    (data.claims || []).forEach(function (c) { byId[c.id] = c; });

    var html = '<div style="font-family:system-ui,-apple-system,sans-serif;max-width:640px">';
    html += '<div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;opacity:.6;font-family:monospace">' +
      esc(data.spec || 'unversioned') + (sourceUrl && /^https?:\/\//.test(sourceUrl) ? ' &middot; <a href="' + esc(sourceUrl) + '" style="color:inherit">source</a>' : '') + '</div>';
    html += '<h3 style="margin:6px 0 2px">' + esc(op.name || 'Unnamed operator') + '</h3>';
    html += '<div style="opacity:.8;font-size:.9rem">' + esc(op.disclosure || 'No disclosure line provided.') + '</div>';
    if (data.coverage && data.coverage.length) {
      html += '<div style="font-size:.8rem;opacity:.7;margin-top:6px">Declared coverage: ' + data.coverage.map(esc).join(', ') + '</div>';
    }
    html += '<div style="margin-top:16px;font-size:.85rem;opacity:.7">' + claims.length + ' claim(s), generated ' + esc(data.generated) + '</div>';
    html += claims.map(function (c) { return claimRow(c, byId); }).join('');
    html += '</div>';
    container.innerHTML = html;
  }

  function renderReceipts(containerId, manifestUrl) {
    var container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
    if (!container) return;
    container.innerHTML = '<div style="font-family:system-ui,sans-serif;opacity:.6;font-size:.9rem">Loading manifest&hellip;</div>';
    fetch(manifestUrl).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function (data) {
      renderManifest(container, data, manifestUrl);
    }).catch(function (err) {
      renderError(container, 'Could not load or parse ' + manifestUrl + ' (' + err.message + ').');
    });
  }

  global.renderReceipts = renderReceipts;
})(typeof window !== 'undefined' ? window : this);
