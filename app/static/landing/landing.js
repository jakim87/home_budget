/* Ile mam kasy — animacje i interakcje strony-wizytówki. Bez zależności. */
(function () {
  'use strict';
  var root = document.getElementById('landing');
  if (!root) return;

  var E = 'cubic-bezier(.2,.7,.2,1)';
  var reduce = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  var one = function (s) { return root.querySelector(s); };
  var all = function (s) { return Array.prototype.slice.call(root.querySelectorAll(s)); };
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var txt = function (el) { return el ? Array.prototype.find.call(el.childNodes, function (n) { return n.nodeType === 3; }) : null; };
  // Redukcja ruchu: zostaje przenikanie, wpisywanie i liczniki; wypada wszystko, co przesuwa lub skaluje.
  var mv = function (t) { return reduce ? 'none' : t; };
  var fmtInt = function (n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0'); };

  var el = {
    progress: one('[data-progress]'), runway: one('[data-runway]'), rail: one('[data-rail]'), frame: one('[data-frame]'),
    nums: all('[data-num]'), words: all('[data-w]'), wordsBox: one('[data-words]'),
    items: all('[data-qa]'), bars: all('[data-qa-bar]'),
    caps: all('[data-shot]'), shots: all('[data-shot-layer]')
  };

  /* ---------- liczby ---------- */
  function parseNum(node0) {
    var node = Array.prototype.find.call(node0.childNodes, function (n) { return n.nodeType === 3 && /\d/.test(n.nodeValue); });
    if (!node) return null;
    var full = node.nodeValue;
    var m = full.match(/[-−]?\d+(?:[ \u00a0\u202f]\d{3})*(?:,\d+)?/);
    if (!m) return null;
    var s = m[0], neg = /^[-−]/.test(s);
    var sep = (s.match(/[ \u00a0\u202f]/) || ['\u00a0'])[0];
    var dec = s.indexOf(',') > -1 ? s.split(',')[1].length : 0;
    var target = parseFloat(s.replace(/[-− \u00a0\u202f]/g, '').replace(',', '.')) * (neg ? -1 : 1);
    var pre = full.slice(0, m.index), post = full.slice(m.index + s.length);
    var fmt = function (v) {
      var p = Math.abs(v).toFixed(dec).split('.');
      return pre + (v < 0 ? '−' : '') + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, sep) + (p[1] ? ',' + p[1] : '') + post;
    };
    return { node: node, full: full, target: target, fmt: fmt };
  }

  function countUp(node0, dur, delay) {
    var P = parseNum(node0);
    if (!P) return null;
    var job = { done: false, finish: function () { if (!job.done) { job.done = true; P.node.nodeValue = P.full; } } };
    P.node.nodeValue = P.fmt(0);
    var t0 = performance.now() + delay;
    (function tick(now) {
      if (job.done) return;
      var t = (now - t0) / dur;
      if (t >= 1) return job.finish();
      if (t > 0) P.node.nodeValue = P.fmt(P.target * (1 - Math.pow(1 - t, 4)));
      requestAnimationFrame(tick);
    })(performance.now());
    return job;
  }

  function runningTotal(g, totalEl) {
    var P = parseNum(totalEl);
    if (!P) return;
    var vals = Array.prototype.map.call(g.querySelectorAll('[data-row] [data-amt]'), function (x) { var p = parseNum(x); return p ? p.target : 0; });
    P.node.nodeValue = P.fmt(0);
    var acc = 0;
    vals.forEach(function (v, i) {
      var from = acc, to = (acc += v), last = i === vals.length - 1;
      setTimeout(function () {
        var t0 = performance.now();
        (function tick(now) {
          var p = Math.min(1, (now - t0) / 160);
          P.node.nodeValue = last && p >= 1 ? P.full : P.fmt(from + (to - from) * (1 - Math.pow(1 - p, 3)));
          if (p < 1) requestAnimationFrame(tick);
        })(t0);
      }, 700 + i * 170);
    });
  }

  /* ---------- wejścia sekcji ---------- */
  function setupReveals() {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        var g = en.target;
        (g.__anims || []).forEach(function (a) { a.play(); });
        g.querySelectorAll('[data-count]').forEach(function (x) { countUp(x, 1600, +x.getAttribute('data-count') || 250); });
        var tot = g.querySelector('[data-total]');
        if (tot) runningTotal(g, tot);
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -6% 0px' });

    all('[data-io]').forEach(function (g) {
      var list = [];
      var mk = function (sel, frames, dur, easing, delayFn) {
        g.querySelectorAll(sel).forEach(function (x, i) {
          var a = x.animate(frames, { duration: dur, easing: easing, fill: 'backwards', delay: delayFn(x, i) });
          a.pause(); list.push(a);
        });
      };
      var dv = function (k) { return function (x) { return +x.getAttribute(k) || 0; }; };
      mk('[data-reveal]', [{ opacity: 0, transform: mv('translate3d(0,32px,0)') }, { opacity: 1, transform: 'none' }], 1000, E, dv('data-reveal'));
      mk('[data-draw]', [{ strokeDashoffset: '1' }, { strokeDashoffset: '0' }], 1800, 'cubic-bezier(.5,0,.2,1)', dv('data-draw'));
      mk('[data-pop]', [{ opacity: 0, transform: mv('scale(0)') }, { opacity: 1, transform: 'scale(1)' }], 520, 'cubic-bezier(.3,1.7,.5,1)', dv('data-pop'));
      mk('[data-bar]', [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], 1300, E, dv('data-bar'));
      mk('[data-line]', [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], 1000, E, dv('data-line'));
      mk('[data-row]', [{ opacity: 0, transform: mv('translate3d(20px,0,0)') }, { opacity: 1, transform: 'none' }], 700, E, function (x, i) { return 350 + i * 170; });
      g.__anims = list;
      io.observe(g);
    });
  }

  /* ---------- pasek pytań ---------- */
  var mq = null, mqHover = false, boost = 0, decaying = false, lastY = null;
  function setupMarquee() {
    var t = one('[data-marquee]');
    if (!t) return;
    mq = t.animate([{ transform: 'translate3d(0,0,0)' }, { transform: 'translate3d(-50%,0,0)' }], { duration: 60000, iterations: Infinity });
    t.addEventListener('mouseenter', function () { mqHover = true; mq.playbackRate = 0.2; });
    t.addEventListener('mouseleave', function () { mqHover = false; mq.playbackRate = 1 + boost; });
  }
  function decay() {
    if (decaying) return;
    decaying = true;
    (function step() {
      boost = boost > 0.02 ? boost * 0.94 : 0;
      if (!mqHover) mq.playbackRate = 1 + boost;
      if (boost) requestAnimationFrame(step); else decaying = false;
    })();
  }

  /* ---------- hero ---------- */
  function heroIntro() {
    all('[data-in]').forEach(function (x) {
      x.animate([{ opacity: 0, transform: mv('translate3d(0,16px,0)') }, { opacity: 1, transform: 'none' }], { duration: 900, delay: +x.getAttribute('data-in') || 0, easing: E, fill: 'backwards' });
    });
    var hz = one('[data-horizon]'), dot = one('[data-horizon-dot]'), pulse = one('[data-pulse]');
    if (hz) hz.animate([{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0% 0 0)' }], { duration: 2800, delay: 500, easing: 'cubic-bezier(.5,0,.2,1)', fill: 'backwards' });
    if (dot) dot.animate([{ opacity: 0, transform: mv('scale(0)') }, { opacity: 1, transform: 'scale(1)' }], { duration: 520, delay: 3200, easing: 'cubic-bezier(.3,1.7,.5,1)', fill: 'backwards' });
    if (pulse && !reduce) pulse.animate([{ opacity: 0.8, transform: 'scale(1)' }, { opacity: 0, transform: 'scale(3.2)' }], { duration: 2400, delay: 3600, iterations: Infinity, easing: E });
  }

  var heroToken = null, heroJobs = [];
  function resetHero() {
    heroJobs.forEach(function (j) { j.finish(); });
    heroJobs = [];
    el.items.forEach(function (it, k) {
      it.getAnimations({ subtree: true }).forEach(function (a) { a.cancel(); });
      var n = txt(it.querySelector('[data-q]'));
      if (n && n.__full != null) n.nodeValue = n.__full;
      it.style.visibility = k ? 'hidden' : '';
    });
    el.bars.forEach(function (b) { var f = b.querySelector('[data-fill]'); if (f) f.getAnimations().forEach(function (a) { a.cancel(); }); });
  }
  function startHero(i, lead) {
    var token = heroToken = {};
    resetHero();
    if (!el.items.length) return;
    el.items.forEach(function (it) { it.style.visibility = 'hidden'; });
    (async function () {
      var k = i, first = true;
      while (token === heroToken) {
        await playQA(k, token, first ? lead : 150);
        first = false;
        k = (k + 1) % el.items.length;
      }
    })();
  }
  async function playQA(i, token, lead) {
    var ok = function () { return token === heroToken; };
    var it = el.items[i];
    var a = it.querySelector('[data-a]'), c = it.querySelector('[data-c]'), caret = it.querySelector('[data-caret]');
    var qn = txt(it.querySelector('[data-q]'));
    if (qn && qn.__full == null) qn.__full = qn.nodeValue;
    var full = qn ? qn.__full : '';
    var dur = lead + full.length * 58 + 5600;
    el.bars.forEach(function (b, k) {
      var f = b.querySelector('[data-fill]');
      if (!f) return;
      f.getAnimations().forEach(function (x) { x.cancel(); });
      f.style.transform = 'scaleX(' + (k < i ? 1 : 0) + ')';
      if (k === i) f.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: dur, easing: 'linear', fill: 'forwards' });
    });
    it.getAnimations({ subtree: true }).forEach(function (x) { x.cancel(); });
    it.style.visibility = 'visible';
    if (qn) qn.nodeValue = '';
    var aIn = a.animate([{ opacity: 0, transform: mv('translate3d(0,24px,0)'), filter: reduce ? 'none' : 'blur(8px)' }, { opacity: 1, transform: 'none', filter: reduce ? 'none' : 'blur(0px)' }], { duration: 900, easing: E, fill: 'both' });
    aIn.pause();
    var cIn = c.animate([{ opacity: 0, transform: mv('translate3d(0,10px,0)') }, { opacity: 1, transform: 'none' }], { duration: 700, easing: E, fill: 'both' });
    cIn.pause();
    if (caret) caret.animate([{ opacity: 1 }, { opacity: 1, offset: 0.5 }, { opacity: 0, offset: 0.5 }, { opacity: 0 }], { duration: 1000, iterations: Infinity });
    await wait(lead); if (!ok()) return;
    for (var k = 1; k <= full.length; k++) {
      if (qn) qn.nodeValue = full.slice(0, k);
      await wait(30 + Math.random() * 50); if (!ok()) return;
    }
    await wait(240); if (!ok()) return;
    aIn.play();
    var j = countUp(a, 1400, 0);
    if (j) heroJobs.push(j);
    await wait(450); if (!ok()) return;
    cIn.play();
    await wait(4300); if (!ok()) return;
    it.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: mv('translate3d(0,-18px,0)') }], { duration: 500, easing: 'cubic-bezier(.4,0,.6,1)', fill: 'forwards' });
    await wait(520); if (!ok()) return;
    it.style.visibility = 'hidden';
    it.getAnimations({ subtree: true }).forEach(function (x) { x.cancel(); });
    if (qn) qn.nodeValue = full;
  }

  /* ---------- zrzuty (przypięta sekcja) ---------- */
  var shot = -1;
  function setShot(k) {
    if (k === shot) return;
    shot = k;
    el.caps.forEach(function (b, i) { b.style.opacity = i === k ? '1' : '0.45'; b.setAttribute('aria-current', i === k ? 'true' : 'false'); });
    el.shots.forEach(function (s, i) {
      s.style.opacity = i === k ? '1' : '0';
      s.style.pointerEvents = i === k ? 'auto' : 'none';
      s.style.transform = i === k ? 'none' : mv(i < k ? 'translate3d(0,-4%,0) scale(.97)' : 'translate3d(0,4%,0) scale(.97)');
    });
  }
  el.caps.forEach(function (b) {
    b.addEventListener('click', function () {
      var k = +b.getAttribute('data-shot');
      if (!el.runway) return;
      var r = el.runway.getBoundingClientRect(), total = r.height - innerHeight;
      scrollTo({ top: scrollY + r.top + total * (k + 0.5) / 3, behavior: reduce ? 'auto' : 'smooth' });
    });
  });

  /* ---------- wykres: podgląd miesiąca ---------- */
  (function chart() {
    var svg = one('[data-chart]'), g = one('[data-hi]');
    if (!svg || !g) return;
    var m = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz'];
    var v = [164100, 165900, 165200, 168400, 170100, 171800, 175300, 179900, 184260];
    var y = [90.8, 84.9, 87.2, 76.9, 71.4, 65.9, 54.6, 39.7, 25.6];
    var line = g.querySelector('line'), dot = g.querySelector('circle'), label = g.querySelector('text');
    var cur = -1;
    svg.addEventListener('mousemove', function (e) {
      var r = svg.getBoundingClientRect();
      var i = Math.max(0, Math.min(8, Math.round(((e.clientX - r.left) / r.width * 320 - 12) / 37)));
      if (i === cur) return;
      cur = i;
      var x = 12 + i * 37;
      line.setAttribute('x1', x); line.setAttribute('x2', x);
      dot.setAttribute('cx', x); dot.setAttribute('cy', y[i]);
      label.setAttribute('x', x);
      label.setAttribute('text-anchor', i <= 1 ? 'start' : i >= 7 ? 'end' : 'middle');
      label.textContent = m[i] + ' · ' + fmtInt(v[i]) + ' zł';
      g.style.opacity = '1';
    });
    svg.addEventListener('mouseleave', function () { cur = -1; g.style.opacity = '0'; });
  })();

  /* ---------- suwak oszczędzania ---------- */
  (function saver() {
    var input = one('[data-save]'), out = one('[data-save-text]'), months = one('[data-months]');
    if (!input) return;
    var missing = +input.getAttribute('data-missing') || 2800;
    var render = function () {
      var save = +input.value, n = Math.ceil(missing / save);
      var unit = n === 1 ? 'miesiąc' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) ? 'miesiące' : 'miesięcy';
      if (out) out.textContent = fmtInt(save);
      if (months) months.textContent = n === 1 ? 'miesiąc' : n + '\u00a0' + unit;
    };
    input.addEventListener('input', render);
    render();
  })();

  /* ---------- przewijanie ---------- */
  var ticking = false, lit = null;
  function update() {
    ticking = false;
    var vh = innerHeight, sy = scrollY, max = document.documentElement.scrollHeight - vh;
    if (el.progress) el.progress.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, sy / max).toFixed(4) : 0) + ')';
    var rr = null;
    if (el.runway) {
      rr = el.runway.getBoundingClientRect();
      var total = rr.height - vh, p = total > 0 ? Math.min(1, Math.max(0, -rr.top / total)) : 0;
      if (el.rail) el.rail.style.transform = 'scaleY(' + p.toFixed(4) + ')';
      setShot(Math.min(2, Math.floor(p * 3)));
    }
    if (!reduce) el.nums.forEach(function (n) {
      var r = n.parentElement.getBoundingClientRect();
      var d = Math.max(-1, Math.min(1, (r.top + r.height / 2) / vh - 0.5));
      n.style.transform = 'translate3d(0,' + (-Math.abs(d) * 18 - d * 6).toFixed(1) + 'px,0)';
    });
    if (el.wordsBox && el.words.length) {
      var wr = el.wordsBox.getBoundingClientRect();
      var wp = Math.min(1, Math.max(0, (vh * 0.85 - wr.top) / (wr.height + vh * 0.3)));
      var l = Math.round(wp * el.words.length);
      if (l !== lit) {
        lit = l;
        el.words.forEach(function (w, i) { w.style.color = i < l ? '' : 'var(--color-neutral-300)'; });
      }
    }
    if (el.frame && rr && !reduce) {
      var ap = Math.min(1, Math.max(0, (vh - rr.top) / vh)), e = 1 - (1 - ap) * (1 - ap);
      el.frame.style.transform = 'translate3d(0,' + ((1 - e) * 48).toFixed(1) + 'px,0) rotateX(' + ((1 - e) * 18).toFixed(2) + 'deg) scale(' + (0.9 + 0.1 * e).toFixed(4) + ')';
    }
    if (mq) {
      var dy = Math.abs(sy - (lastY == null ? sy : lastY));
      lastY = sy;
      if (dy) { boost = Math.min(6, boost + dy * 0.04); decay(); }
    }
  }
  var onScroll = function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll);

  /* ---------- 04: kalkulator kredytu ---------- */
  // Liczy harmonogram() z kalkulator_kredytu.js — ten sam model co /kalkulator-kredytu.
  var kk = one('[data-kk]');
  if (kk && typeof harmonogram === 'function') {
    var pole = function (k) { return kk.querySelector('[data-kk-' + k + ']'); };
    var liczKredyt = function () {
      var K = parseFloat(pole('kwota').value.replace(/\s/g, '')) || 0;
      var M = Math.round((parseFloat(pole('lata').value.replace(',', '.')) || 0) * 12);
      var R = parseFloat(pole('opr').value.replace(',', '.'));
      var ok = K > 0 && M > 0 && M <= 600 && R >= 0;
      var w = ok && harmonogram({ kwota: K, miesiace: M, oprocentowanie: R });
      var w2 = ok && harmonogram({ kwota: K, miesiace: M, oprocentowanie: zaokr(R + 2) });
      pole('rata').textContent = ok ? zl(w.raty[0].rata) : '—';
      pole('odsetki').textContent = ok ? zl(w.sumaOdsetek) : '—';
      pole('do-oddania').textContent = ok ? zl(zaokr(K + w.sumaOdsetek)) : '—';
      pole('stres').textContent = ok ? zl(w2.raty[0].rata) + ' (+' + zl(zaokr(w2.raty[0].rata - w.raty[0].rata)) + ')' : '—';
    };
    pole('kwota').addEventListener('input', function () { formatujPoleKwoty(pole('kwota')); });
    kk.addEventListener('input', liczKredyt);
    liczKredyt();
  }

  el.words.forEach(function (w) { w.style.transition = 'color .4s ease'; });
  setupReveals();
  if (!reduce) setupMarquee();
  heroIntro();
  el.bars.forEach(function (b, k) { b.addEventListener('click', function () { startHero(k, 0); }); });
  startHero(0, 400);
  update();
})();
