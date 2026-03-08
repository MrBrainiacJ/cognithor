interface CanvasProps {
  html: string;
  onClose: () => void;
}

/**
 * Sanitize HTML using DOMParser instead of regex to avoid
 * incomplete multi-character sanitization and regex bypass attacks.
 */
function sanitizeHtml(raw: string): string {
  const doc = new DOMParser().parseFromString(raw, 'text/html');

  // Remove all <script>, <style>, <iframe>, <object>, <embed>, <link> elements
  const dangerous = doc.querySelectorAll(
    'script, style, iframe, object, embed, link, base, form'
  );
  dangerous.forEach(el => el.remove());

  // Walk all elements and strip event handlers + javascript: URIs
  const allElements = doc.body.querySelectorAll('*');
  allElements.forEach(el => {
    const attrs = Array.from(el.attributes);
    for (const attr of attrs) {
      // Remove all on* event handlers
      if (attr.name.startsWith('on')) {
        el.removeAttribute(attr.name);
      }
      // Remove javascript: URIs from href, src, action, etc.
      if (['href', 'src', 'action', 'formaction', 'xlink:href', 'data'].includes(attr.name)) {
        if (/^\s*javascript\s*:/i.test(attr.value)) {
          el.removeAttribute(attr.name);
        }
      }
    }
  });

  return doc.body.innerHTML;
}

export function Canvas({ html, onClose }: CanvasProps) {
  const sanitizedHtml = sanitizeHtml(html);

  const srcdoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      padding: 16px;
      line-height: 1.6;
    }
    pre, code {
      background: #0f0f23;
      border-radius: 6px;
      padding: 2px 6px;
      font-size: 13px;
    }
    pre { padding: 12px; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #333; padding: 8px 12px; text-align: left; }
    th { background: #0f0f23; }
    img { max-width: 100%; height: auto; }
    a { color: #00d4ff; }
  </style>
</head>
<body>${sanitizedHtml}</body>
</html>`;

  return (
    <div class="canvas-container" role="complementary" aria-label="Canvas">
      <div class="canvas-header">
        <span class="canvas-title">Canvas</span>
        <button
          onClick={onClose}
          class="canvas-close-btn"
          aria-label="Canvas schließen"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <iframe
        class="canvas-iframe"
        sandbox=""
        srcdoc={srcdoc}
        title="Jarvis Canvas"
      />
    </div>
  );
}
