/* ==================================================================
   WC —— 轻量词云渲染器（零依赖 / 纯 Canvas / 阿基米德螺旋 + 网格碰撞）
   用途：替代项目 static/ 下的静态词云 JPEG，让词云随数据更新且可交互
   接口：WC.render(box, data, opt) -> 控制器
     box  : 容器元素（会用它的 clientWidth/clientHeight）
     data : [[词, 频次], ...]                 —— 旧格式，按排名着色（向后兼容）
            [[词, 频次, 组名, 色], ...]        —— 新格式，自带分组与颜色
            [{name, value, g, c}, ...]        —— 同上，对象形态
            需按频次降序
     opt  : { maxFs, minFs, pal, noiseOn, tipW,
              gloss,        词条释义表 { 词: {def, field, note} }
              layerNote,    分层读法说明 { 层名: 文本 }
              noiseNote,    噪声词判定说明
              emptyNote,    空态说明
              meta,         本图口径元信息 { unit, total, source }
              onClick(item) }              —— 点击某个词时回调（item 含 t/v/g/c/rank）

   解释体系（2026-10-06 新增）
     悬停 = 一行速览（词 · 读数 · 层级）
     点击/回车 = 固定「解释卡」，含四段：
       ① 词条释义（人工写，准确）；② 读图提示（口径陷阱）；
       ③ 统计口径（出现篇数 DF、占本图比重、排名、所属簇）；④ 分层读法。
     查不到释义时**不编造**，退到「分层读法 + 统计口径」并显式说明。
     度量口径用词统一：词云的数值是**出现篇数（文档频率 DF）**，
     不是原始词频 TF —— 二者在长文档语料里差异很大，混称会误导读者。

   可访问性：Canvas 本身对读屏器是黑盒，故
     · 容器 tabindex=0 + role="application"，方向键在词间移动、Enter 展开、Esc 关闭；
     · 提供隐藏的 ARIA 实况区（aria-live=polite）播报当前词与解释摘要；
     · 触摸端 tap 等价于 click（解释卡不依赖 hover）；
     · 解释卡是真 DOM（可选中文字、可复制），不画在 canvas 上。

   注：`g` 是分组名（事件簇名或「公文套话 / 议题概念词 / 泛义实义词」等层名），
       `c` 是该组颜色。二者由后端 event_clusters.py 决定，渲染器不参与语义判断。
   ================================================================== */
(function (global) {
  var NOISE = /^(https?|http|www|cn|com|net|org|html|##|#|\d+|[a-z]{1,4})$/i;

  /* 噪声判定：URL/域名/短英文/纯符号/URL 残留片段（如 "?q="、"a=1"、"3/4"）
     ⚠ 判定规则必须与 build_unified_page.py 的 _NZ_RX 逐条一致：
     两边不同步就会出现「后端说 30 个噪声词、前端只压暗了 28 个」的对不上账。 */
  function isNoise(t) {
    if (NOISE.test(t)) return true;
    if (/[?&=#/\\]|:\/\//.test(t)) return true;             // URL 语法残留
    if (!/[0-9A-Za-z一-鿿]/.test(t)) return true;    // 纯符号
    return false;
  }

  var FONT = '700 {S}px "Microsoft YaHei","PingFang SC","Hiragino Sans GB",-apple-system,sans-serif';

  /* 词条最长显示字数：超长词（如 URL 残留、被切碎的短语）在画布上会挤掉邻词，
     这里统一截断并保留释义里的完整写法提示。 */
  var MAX_CHARS = 12;
  function trunc(t) {
    var s = String(t == null ? '' : t);
    /* 按「字」计宽：CJK 记 1，ASCII 记 0.5，阈值取 12 个汉字宽 */
    var w = 0, out = '';
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      w += (c > 0x2e80) ? 1 : 0.5;
      if (w > MAX_CHARS) return out + '…';
      out += s.charAt(i);
    }
    return out;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  /* 文案里用 <em> 显式标注需强调的片段（HTML 标签，非 Markdown 记号）。
     为什么不用 Markdown 的 **…**：星号在窄列换行时会被拆到两行，正则随即失配 ——
     要么星号裸露给读者、要么整段碎裂成「每行都加粗」（两种都实测踩过）。
     <em> 是显式标签，没有这种歧义。
     释义文案由 word_glossary.py 提供、属可信常量，但仍先整体转义 ——
     只放行我们自己的 <em>，其余标签一律转义掉。 */
  function rich(s) {
    return esc(s).replace(/&lt;em&gt;([\s\S]+?)&lt;\/em&gt;/g, '<em>$1</em>');
  }

  function norm(data) {
    var out = [], seen = {};
    for (var i = 0; i < data.length; i++) {
      var d = data[i], t, v, g, c;
      if (d && d.name != null) { t = d.name; v = d.value; g = d.g; c = d.c; }
      else { t = d[0]; v = d[1]; g = d[2]; c = d[3]; }
      t = String(t == null ? '' : t).trim();
      if (!t || !(v > 0)) continue;          /* 空词 / 零频 / 非法值直接剔除 */
      /* 重复词去重：同名条目只保留**第一个**。
         为什么不能合并频次：词云的数值是「出现篇数（DF）」，同一篇微博里
         「景区」出现 3 次仍只计 1 篇，所以两份 DF 相加会**重复计数**，
         凭空造出比实际更高的篇数。取首条 = 信任上游已按篇去重。
         （若上游给的是原始词频 TF，相加才对 —— 但那不是本项目的口径。） */
      if (seen[t]) continue;
      seen[t] = 1;
      out.push({ t: t, v: +v, rank: out.length + 1, noise: isNoise(t),
                 g: g || '', c: c || '' });
    }
    return out;
  }

  function render(box, data, opt) {
    opt = opt || {};
    var host = box;
    host.innerHTML = '';
    host.style.position = 'relative';

    var GLOSS = opt.gloss || {};
    var LAYER = opt.layerNote || {};
    var META = opt.meta || {};

    var items = norm(data);
    if (!items.length) {
      /* 空态要说明「为什么空」，否则读者会误读成「该议题没有讨论」 */
      host.innerHTML = '<div class="wc-empty">'
        + '<b>暂无可展示的词频数据</b>'
        + (opt.emptyNote ? '<span>' + rich(opt.emptyNote) + '</span>' : '')
        + '</div>';
      host.setAttribute('role', 'status');
      return null;
    }

    var W = host.clientWidth || 400, H = host.clientHeight || 320;
    var DPR = Math.min(global.devicePixelRatio || 1, 2);
    var pal = opt.pal || ['#4a9dff', '#2fd6d0', '#a97bff', '#ffb44d', '#7fb2ff', '#3ddc97'];

    var cv = document.createElement('canvas');
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    cv.style.display = 'block'; cv.style.cursor = 'default';
    /* Canvas 对读屏器是黑盒：给它一个可聚焦的应用角色 + 明确的无障碍名 */
    cv.setAttribute('tabindex', '0');
    cv.setAttribute('role', 'application');
    cv.setAttribute('aria-label',
      '词云，共 ' + items.length + ' 个词条。' +
      (opt.onClick ? '使用左右方向键在词条间移动，按回车展开该词的解释，按 Esc 关闭。'
                   : '使用左右方向键在词条间移动。'));
    host.appendChild(cv);
    var ctx = cv.getContext('2d');

    /* ---- 1. 布局：按频次降序，逐个用螺旋寻找空位 ---- */
    var CELL = 3;
    var GW = Math.ceil(W / CELL) + 2, GH = Math.ceil(H / CELL) + 2;
    var occ = new Uint8Array(GW * GH);
    var PAD = 1;                       // 词间最小留白(px)
    var maxFs = opt.maxFs || Math.max(22, Math.min(H * 0.32, 64));
    var minFs = opt.minFs || 11;

    function free(x0, y0, x1, y1) {
      var i0 = Math.floor(x0 / CELL), i1 = Math.floor(x1 / CELL);
      var j0 = Math.floor(y0 / CELL), j1 = Math.floor(y1 / CELL);
      if (i0 < 0 || j0 < 0 || i1 >= GW || j1 >= GH) return false;
      for (var j = j0; j <= j1; j++) {
        var b = j * GW;
        for (var i = i0; i <= i1; i++) if (occ[b + i]) return false;
      }
      return true;
    }
    function mark(x0, y0, x1, y1) {
      var i0 = Math.max(0, Math.floor(x0 / CELL)), i1 = Math.min(GW - 1, Math.floor(x1 / CELL));
      var j0 = Math.max(0, Math.floor(y0 / CELL)), j1 = Math.min(GH - 1, Math.floor(y1 / CELL));
      for (var j = j0; j <= j1; j++) { var b = j * GW; for (var i = i0; i <= i1; i++) occ[b + i] = 1; }
    }

    var cx = W / 2, cy = H / 2;
    var placed = [], hidden = 0, vmax = items[0].v, vmin = items[items.length - 1].v;

    /* 布局优先序：非噪声词先占位（有意义的大词靠近中心），噪声词最后补位。
       否则 http/cn/## 这类频次最高的垃圾词会把真正有信息量的词挤出画面。 */
    var order = items.slice().sort(function (a, b) {
      if (a.noise !== b.noise) return a.noise ? 1 : -1;
      return b.v - a.v;
    });

    for (var k = 0; k < order.length; k++) {
      var it = order[k];
      if (opt.noiseOn === false && it.noise) { it.skipped = true; hidden++; continue; }
      var t01 = (it.v - vmin) / Math.max(1, vmax - vmin);
      var fs0 = minFs + (maxFs - minFs) * Math.sqrt(t01);
      // 噪声词：字号压制到 34% 档位，避免喧宾夺主
      if (it.noise) fs0 = Math.min(fs0, minFs + (maxFs - minFs) * 0.34);
      var w, h, x, y, ok = false, fs = fs0;
      var label = trunc(it.t);           /* 画布上用截断后的写法 */

      // 放不下就逐步缩小字号（最少降到 88% 基准，保证可读性）
      for (var attempt = 0; attempt < 4 && !ok; attempt++) {
        ctx.font = FONT.replace('{S}', fs.toFixed(1));
        w = ctx.measureText(label).width + 3;   // +3 余量：中英混排/全角符号实测宽度会略大于测量值
        h = fs * 1.08;
        var step = 0, maxStep = 2600;
        for (; step < maxStep; step++) {
          var ang = step * 0.30;
          var rad = 0.95 * ang;
          x = cx + rad * Math.cos(ang) - w / 2;
          y = cy + rad * Math.sin(ang) * 0.60 - h / 2;
          if (x < 2 || y < 2 || x + w > W - 2 || y + h > H - 2) {
            if (rad > Math.max(W, H)) break;
            continue;
          }
          if (free(x - PAD, y - PAD, x + w + PAD, y + h + PAD)) { ok = true; break; }
        }
        if (!ok) fs *= 0.90;
      }
      if (!ok) { it.skipped = true; hidden++; continue; }

      mark(x - PAD, y - PAD, x + w + PAD, y + h + PAD);
      it.fs = fs; it.w = w; it.h = h; it.x = x; it.y = y; it.shown = label;
      placed.push(it);
    }
    placed.sort(function (a, b) { return a.rank - b.rank; });   /* 命中/键盘按原始次序 */

    var VTOT = items.reduce(function (s, z) { return s + z.v; }, 0);

    /* ---- 2. 绘制 ---- */
    function colorOf(it, i) {
      if (it.c) return it.c;                    /* 分组自带色（事件簇 / 灰阶层） */
      if (it.noise) return '#5f6f8a';
      var n = pal.length;
      var idx = Math.min(n - 1, Math.floor((i / Math.max(1, placed.length - 1)) * n));
      return pal[idx];
    }

    var hoverIdx = -1, kbIdx = -1, focus = null;

    function draw() {
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.textBaseline = 'top';
      for (var i = 0; i < placed.length; i++) {
        var it = placed[i];
        var outFocus = focus && it.g !== focus;  /* 联动：非当前簇的词压暗 */
        var act = hoverIdx === i || kbIdx === i;
        var dim = (hoverIdx >= 0 && hoverIdx !== i) || outFocus;
        ctx.globalAlpha = outFocus ? 0.15 : (dim ? 0.22 : (it.noise ? 0.72 : 1));
        ctx.font = FONT.replace('{S}', it.fs.toFixed(1));
        var col = colorOf(it, i);
        if (act) {
          /* 键盘选中项给一圈白色描边：仅靠阴影在浅色舞台上会看不见 */
          ctx.lineWidth = Math.max(1.5, it.fs / 14);
          ctx.strokeStyle = 'rgba(255,255,255,.95)';
          ctx.lineJoin = 'round';
          ctx.strokeText(it.shown, it.x, it.y);
          ctx.shadowColor = col; ctx.shadowBlur = 14;
        } else { ctx.shadowBlur = 0; }
        ctx.fillStyle = col;
        ctx.fillText(it.shown, it.x, it.y);
        ctx.shadowBlur = 0;
      }
      ctx.globalAlpha = 1;
    }
    draw();

    /* ---- 3. 解释文案：查表 → 分层兜底，绝不编造 ---- */
    function statLine(it) {
      var rows = [];
      rows.push(['出现篇数（DF）', it.v.toLocaleString('en-US') + ' 篇']);
      rows.push(['占本图比重', (it.v / VTOT * 100).toFixed(1) + '%（分母＝本图 ' + items.length
                 + ' 词合计 ' + VTOT.toLocaleString('en-US') + ' 篇）']);
      rows.push(['本图排名', '#' + it.rank + ' / ' + items.length]);
      if (it.g) rows.push(['所属分组', it.g]);
      if (META.unit) rows.push(['度量口径', META.unit]);
      if (META.source) rows.push(['数据来源', META.source]);
      return rows;
    }

    /* 返回 {def, note, field, hasDef} —— def 为空表示词表未收，靠分层兜底 */
    function glossOf(it) {
      var g = GLOSS[it.t];
      if (g) return { def: g.def || '', note: g.note || '', field: g.field || '', hasDef: !!g.def };
      return { def: '', note: '', field: '', hasDef: false };
    }

    function explainHTML(it) {
      var gl = glossOf(it);
      var h = '';
      h += '<div class="wc-x-top"><span class="wc-x-term">' + esc(it.t) + '</span>'
         + (it.g ? '<span class="wc-x-layer" style="--lc:' + (it.c || '#8a93a3') + '">'
                 + esc(it.g) + '</span>' : '')
         + (gl.field ? '<span class="wc-x-field">' + esc(gl.field) + '</span>' : '')
         + '</div>';

      h += '<div class="wc-x-body">';
      /* ① 词条释义 */
      if (gl.hasDef) {
        h += '<p class="wc-x-def">' + rich(gl.def) + '</p>';
      } else {
        /* 查不到就说查不到，并给分层读法，不写"这是重要话题"这类空话 */
        var ln = LAYER[it.g] || '';
        h += '<p class="wc-x-def wc-x-nodict">本词未收入释义库'
           + (it.g ? '，其读法取决于所属分层「' + esc(it.g) + '」' : '')
           + '。下方按分层给出读法与统计口径，<b>不作词义推断</b>。</p>';
        if (ln) h += '<p class="wc-x-def">' + rich(ln) + '</p>';
      }
      /* ② 读图提示 */
      if (gl.note) h += '<p class="wc-x-note"><b>读图提示</b>' + rich(gl.note) + '</p>';
      if (it.noise && opt.noiseNote) h += '<p class="wc-x-note wc-x-warn"><b>噪声词</b>' + rich(opt.noiseNote) + '</p>';
      /* ③ 统计口径 */
      h += '<dl class="wc-x-stat">';
      statLine(it).forEach(function (r) {
        h += '<dt>' + esc(r[0]) + '</dt><dd>' + esc(r[1]) + '</dd>';
      });
      h += '</dl>';
      h += '</div>';
      return h;
    }

    /* 速览（一行）—— 给悬停与读屏播报用 */
    function briefText(it) {
      var gl = glossOf(it);
      return it.t + '，出现 ' + it.v + ' 篇，本图第 ' + it.rank + ' 位'
           + (it.g ? '，属' + it.g : '')
           + '。' + (gl.hasDef ? gl.def : (LAYER[it.g] || '未收入释义库，仅给出统计口径。'));
    }

    /* ---- 4. 悬停速览（跟随指针，自动避让边界） ---- */
    var tipEl = document.createElement('div');
    tipEl.className = 'wc-tip';
    tipEl.setAttribute('aria-hidden', 'true');
    host.appendChild(tipEl);

    function placeTip(mx, my) {
      var tw = tipEl.offsetWidth, th = tipEl.offsetHeight;
      /* 贴近容器边缘时翻到另一侧，避免被卡片裁掉 */
      var tx = mx + 14;
      if (tx + tw > W - 4) tx = Math.max(4, mx - tw - 14);
      var ty = my - th - 10;
      if (ty < 4) ty = Math.min(H - th - 4, my + 16);
      tipEl.style.left = tx + 'px'; tipEl.style.top = ty + 'px';
    }

    function showTip(it) {
      tipEl.innerHTML = '<b>' + esc(it.t) + '</b>'
        + '<span class="wc-tip-v">' + it.v.toLocaleString('en-US') + ' 篇</span>'
        + (it.g ? '<span class="wc-tip-l" style="--lc:' + (it.c || '#8a93a3') + '">'
                + esc(it.g) + '</span>' : '')
        + '<span class="wc-tip-hint">点击看解释</span>';
      /* 顺序要求：先写内容、再置 opacity=1、最后量尺寸定位。
         反过来（先量后写）会按上一段文字的宽高定位。 */
      tipEl.style.opacity = 1;
      placeTip(it._mx || 0, it._my || 0);
    }
    function hideTip() { tipEl.style.opacity = 0; }

    /* ---- 5. 解释卡（点击/回车固定；真 DOM，可选中可复制） ---- */
    var cardEl = document.createElement('div');
    cardEl.className = 'wc-x-card';
    cardEl.setAttribute('role', 'dialog');
    cardEl.setAttribute('aria-label', '词条解释');
    cardEl.setAttribute('aria-modal', 'false');
    cardEl.hidden = true;
    host.appendChild(cardEl);

    var liveEl = document.createElement('div');
    liveEl.className = 'wc-a11y';
    liveEl.setAttribute('aria-live', 'polite');
    liveEl.setAttribute('role', 'status');
    host.appendChild(liveEl);

    function openCard(it) {
      cardEl.innerHTML = '<button class="wc-x-close" type="button" aria-label="关闭解释">×</button>'
        + explainHTML(it);
      cardEl.hidden = false;
      cardEl.querySelector('.wc-x-close').focus();
      if (opt.onClick) opt.onClick(it);     /* 点词联动事件簇面板（保持旧行为） */
    }
    function closeCard() {
      cardEl.hidden = true; cardEl.innerHTML = '';
      cv.focus();
    }
    cardEl.addEventListener('click', function (e) {
      if (e.target.classList.contains('wc-x-close')) { closeCard(); e.stopPropagation(); }
    });

    /* ---- 6. 命中检测 ---- */
    function hit(mx, my) {
      for (var i = 0; i < placed.length; i++) {
        var it = placed[i];
        if (mx >= it.x && mx <= it.x + it.w && my >= it.y && my <= it.y + it.h) return i;
      }
      return -1;
    }

    cv.addEventListener('mousemove', function (e) {
      var r = cv.getBoundingClientRect();
      var mx = e.clientX - r.left, my = e.clientY - r.top;
      var idx = hit(mx, my);
      if (idx !== hoverIdx) { hoverIdx = idx; draw(); }
      if (idx >= 0) {
        var it = placed[idx]; it._mx = mx; it._my = my;
        showTip(it);
        cv.style.cursor = 'pointer';
      } else { hideTip(); cv.style.cursor = 'default'; }
    });
    cv.addEventListener('mouseleave', function () { hoverIdx = -1; draw(); hideTip(); });

    /* 触摸端：tap 走同一套命中检测（解释卡不依赖 hover） */
    cv.addEventListener('touchend', function (e) {
      var t0 = e.changedTouches && e.changedTouches[0];
      if (!t0) return;
      var r = cv.getBoundingClientRect();
      var idx = hit(t0.clientX - r.left, t0.clientY - r.top);
      if (idx >= 0) { e.preventDefault(); openCard(placed[idx]); }
    }, { passive: false });

    /* 鼠标点击：总是能开解释卡（无论有没有配置 onClick 联动） */
    cv.addEventListener('click', function (e) {
      var r = cv.getBoundingClientRect();
      var idx = hit(e.clientX - r.left, e.clientY - r.top);
      if (idx >= 0) { openCard(placed[idx]); hideTip(); }
    });

    /* ---- 7. 键盘：←/→ 移动，Enter/Space 展开，Esc 关闭 ---- */
    cv.addEventListener('keydown', function (e) {
      var n = placed.length;
      if (!n) return;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        kbIdx = (kbIdx + 1) % n; e.preventDefault();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        kbIdx = (kbIdx - 1 + n) % n; e.preventDefault();
      } else if (e.key === 'Home') { kbIdx = 0; e.preventDefault(); }
      else if (e.key === 'End') { kbIdx = n - 1; e.preventDefault(); }
      else if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        if (kbIdx < 0) kbIdx = 0;
        openCard(placed[kbIdx]); e.preventDefault(); return;
      } else if (e.key === 'Escape') {
        if (!cardEl.hidden) { closeCard(); e.preventDefault(); }
        kbIdx = -1;
      } else return;
      hoverIdx = -1; hideTip(); draw();
      var it = placed[kbIdx];
      it._mx = it.x + it.w / 2; it._my = it.y;      /* 键盘没有指针，落在词上方 */
      showTip(it);
      liveEl.textContent = briefText(it);
    });
    cv.addEventListener('blur', function () { hideTip(); });

    return {
      placed: placed.length, hidden: hidden, items: items.length,
      hoverIdx: function () { return hoverIdx; },
      /* 聚焦某个组：非该组的词压暗到 15%，返回命中的词数（0 表示本图没有该组） */
      setFocus: function (g) {
        focus = g || null;
        draw();
        var n = 0;
        for (var i = 0; i < placed.length; i++) if (focus && placed[i].g === focus) n++;
        return n;
      },
      focus: function () { return focus; },
      explain: function (t) {           /* 供外部（如词频表、事件簇面板）复用同一套解释 */
        var it = null;
        for (var i = 0; i < items.length; i++) if (items[i].t === t) { it = items[i]; break; }
        return it ? explainHTML(it) : '';
      },
      close: closeCard,
      /* 落子明细（t 词 / x,y 位置 / g 分组 / v 频次）—— 供自动化自检做点击命中测试，
         页面本身不用它。 */
      placedItems: function () { return placed; }
    };
  }

  global.WC = { render: render, NOISE: NOISE, trunc: trunc, esc: esc, isNoise: isNoise };
})(window);
