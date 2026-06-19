(function () {
  const log = document.getElementById('log');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  if (!log || !form) return;

  let threadId = log.dataset.thread || null;

  // Minimal, safe markdown-ish rendering (bold, italic, lists, blockquote, paragraphs).
  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function render(md) {
    const lines = esc(md).split('\n');
    let html = '', inUl = false;
    const inline = (t) => t
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>');
    for (let line of lines) {
      if (/^\s*[-*]\s+/.test(line)) {
        if (!inUl) { html += '<ul>'; inUl = true; }
        html += '<li>' + inline(line.replace(/^\s*[-*]\s+/, '')) + '</li>';
        continue;
      }
      if (inUl) { html += '</ul>'; inUl = false; }
      if (/^\s*>\s?/.test(line)) { html += '<blockquote>' + inline(line.replace(/^\s*>\s?/, '')) + '</blockquote>'; continue; }
      if (line.trim() === '') { html += ''; continue; }
      html += '<p>' + inline(line) + '</p>';
    }
    if (inUl) html += '</ul>';
    return html;
  }

  function bubble(role, contentHtml, citations) {
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + (role === 'user' ? 'user' : 'coach');
    let cites = '';
    if (citations && citations.length) {
      cites = '<div class="cites">' + citations.map(c => '<span>📎 ' + esc(c.title) + '</span>').join('') + '</div>';
    }
    wrap.innerHTML = (role === 'user' ? '' : '<div class="mini-ava">AM</div>') +
      '<div class="bubble">' + contentHtml + cites + '</div>';
    return wrap;
  }

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function citesHtml(citations) {
    if (!citations || !citations.length) return '';
    return '<div class="cites">' + citations.map(c => '<span>📎 ' + esc(c.title) + '</span>').join('') + '</div>';
  }

  function ratingHtml(mid, rating) {
    rating = rating || 0;
    return '<div class="rate" data-mid="' + mid + '">' +
      '<button class="rate-btn up' + (rating === 1 ? ' on' : '') + '" data-v="1" title="Good answer">&#128077;</button>' +
      '<button class="rate-btn down' + (rating === -1 ? ' on' : '') + '" data-v="-1" title="Not how she would say it - flags for Anne-Marie\'s review">&#128078;</button>' +
      '</div>';
  }

  async function sendMessage(text) {
    log.appendChild(bubble('user', render(text)));
    scrollDown();
    const typing = bubble('coach', '<span class="typing"><span></span><span></span><span></span></span>');
    log.appendChild(typing); scrollDown();
    send.disabled = true; input.disabled = true;

    try {
      const res = await fetch('/app/coach/api/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId }),
      });
      if (!res.ok || !res.body) throw new Error('stream unavailable');
      typing.remove();
      const wrap = bubble('coach', '');
      log.appendChild(wrap);
      const bd = wrap.querySelector('.bubble');
      let acc = '', buf = '';
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, i); buf = buf.slice(i + 2);
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));
          if (data.t === 'delta') {
            acc += data.text;
            bd.innerHTML = render(acc);
            scrollDown();
          } else if (data.t === 'done') {
            threadId = data.thread_id;
            if (data.corrected_text) acc = data.corrected_text;
            bd.innerHTML = render(acc) + citesHtml(data.citations);
            if (data.message_id) bd.insertAdjacentHTML('afterend', ratingHtml(data.message_id, 0));
            scrollDown();
          }
        }
      }
    } catch (e) {
      typing.remove();
      // Fallback: the original non-streaming endpoint.
      try {
        const res = await fetch('/app/coach/api/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, thread_id: threadId }),
        });
        const data = await res.json();
        if (data.error) log.appendChild(bubble('coach', '<p>Sorry - something went wrong. Try again.</p>'));
        else { threadId = data.thread_id; log.appendChild(bubble('coach', render(data.reply), data.citations)); }
      } catch (e2) {
        log.appendChild(bubble('coach', '<p>Network error - please try again.</p>'));
      }
    } finally {
      send.disabled = false; input.disabled = false; input.focus(); scrollDown();
    }
  }

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.rate-btn');
    if (!btn) return;
    const holder = btn.closest('.rate');
    const v = parseInt(btn.dataset.v, 10);
    const newV = btn.classList.contains('on') ? 0 : v;
    try {
      await fetch('/app/coach/api/rate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: parseInt(holder.dataset.mid, 10), rating: newV }),
      });
      holder.querySelectorAll('.rate-btn').forEach(b => b.classList.remove('on'));
      if (newV !== 0) btn.classList.add('on');
    } catch (err) { /* non-blocking */ }
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    input.style.height = 'auto';
    sendMessage(text);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  document.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (chip && chip.dataset.q) sendMessage(chip.dataset.q);
  });

  // Load-earlier pagination: prepend older messages above the current view.
  const earlier = document.getElementById('loadEarlier');
  if (earlier) {
    earlier.addEventListener('click', async () => {
      earlier.disabled = true;
      try {
        const res = await fetch('/app/coach/api/history?thread_id=' + (threadId || '') +
                                '&before_id=' + earlier.dataset.before);
        const data = await res.json();
        const anchor = earlier.parentElement;
        for (const m of data.messages.slice().reverse()) {
          const w = bubble(m.role === 'user' ? 'user' : 'coach', render(m.content));
          if (m.role !== 'user') {
            w.insertAdjacentHTML('beforeend', ratingHtml(m.id, m.rating));
          }
          anchor.insertAdjacentElement('afterend', w);
        }
        if (data.messages.length) earlier.dataset.before = data.messages[0].id;
        if (!data.has_earlier) anchor.remove();
      } finally {
        earlier.disabled = false;
      }
    });
  }

  // Deep links from Today ("?q=Walk me through today's map") start the conversation.
  const preset = new URLSearchParams(window.location.search).get('q');
  if (preset) {
    window.history.replaceState({}, '', window.location.pathname);
    sendMessage(preset);
  }
})();
