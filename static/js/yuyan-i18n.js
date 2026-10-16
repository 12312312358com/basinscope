(function () {
  "use strict";
  const query = new URLSearchParams(window.location.search);
  const isEnglish = query.get("lang") === "en";
  window.YUYAN_EN_MODE = isEnglish;
  if (isEnglish) {
    document.documentElement.lang = "en";
    document.body.classList.add("lang-en");
  }

  const EXACT = {
    "舆眼": "Yuyan",
    "黄河流域舆情": "Yellow River Public Opinion",
    "黄河流域": "Yellow River",
    "18 项": "18 views",
    "数据源": "Data source",
    "快照": "Snapshot",
    "上次采集": "Last collection",
    "更新数据": "Update data",
    "全部渲染": "Render all",
    "打印 / 导出 PDF": "Print / Export PDF",
    "单文件离线 · 零外链": "Offline single-file - No external links",
    "总览": "Overview",
    "议题与词频": "Topics and Word Frequency",
    "内容与评论": "Content and Comments",
    "传播与扩散": "Propagation and Diffusion",
    "事件与预警": "Events and Warning",
    "口径与方法": "Methodology and Data Conventions",
    "智能问答": "Question Answering",
    "黄河流域总览": "Yellow River Overview",
    "IP 属地地图": "Author-IP Location Map",
    "议题专题": "Topic Profiles",
    "词频与词云": "Word Frequency and Word Cloud",
    "高影响力内容": "High-Impact Content",
    "评论洞察": "Comment Insights",
    "短视频智能分析": "Short-Video Analysis",
    "评论观点聚类": "Opinion Clustering",
    "发布渠道与话语主体": "Speaker Classification",
    "互动结构与扩散效率": "Interaction and Diffusion",
    "关键传播节点": "Key Propagation Nodes",
    "传播趋势与节奏": "Temporal Trends",
    "事件监测": "Event Monitoring",
    "事件传播强度": "Event-Province Propagation Intensity",
    "风险分级预警": "Risk Screening",
    "情感模型校准": "Sentiment Model Calibration",
    "真实": "Data",
    "真实 · 三源": "Data - Three sources",
    "AI": "AI",
    "说明": "Method",
    "L2 · 真实": "L2 - Data",
    "L3 · 实测": "L3 - Measured",
    "L4 · 缺口": "L4 - Gap",
    "实时 · 本流域限定": "Live - Basin constrained",
    "生态治理": "Ecological Governance",
    "生态环境治理": "Ecological Governance",
    "文旅": "Cultural Tourism",
    "医患矛盾": "Healthcare Disputes",
    "社会治理": "Social Governance",
    "正面": "Positive",
    "中性": "Neutral",
    "负面": "Negative",
    "微博": "Weibo",
    "小红书": "Xiaohongshu",
    "知乎": "Zhihu",
    "抖音": "Douyin",
    "平台": "Platform",
    "点赞": "Likes",
    "评论": "Comments",
    "转发": "Reposts",
    "分享": "Shares",
    "收藏": "Favourites",
    "作者": "Authors",
    "样本": "Sample",
    "样本微博": "Sample posts",
    "样本闸门": "Sample gate",
    "评论样本": "Comment sample",
    "评论议题": "Comment topics",
    "评论年份": "Comment years",
    "参与作者": "Unique authors",
    "目标省份": "Target provinces",
    "目标省份声量": "Target-Province Volume",
    "省份": "Province",
    "属地省份": "Author-IP provinces",
    "覆盖省级行政区": "Covered provincial regions",
    "数据范围": "Data scope",
    "数据来源": "Data sources",
    "生成时间": "Generated at",
    "采集截止": "Collection end",
    "知识来源": "Knowledge sources",
    "可选平台": "Available platforms",
    "合计": "Total",
    "占比": "Share",
    "条数": "Count",
    "篇数": "Articles",
    "文章": "Articles",
    "评论条数": "Comment count",
    "累计点赞": "Total likes",
    "累计评论": "Total comments",
    "累计转发": "Total reposts",
    "单篇点赞": "Likes per post",
    "单篇转发": "Reposts per post",
    "转赞比": "Repost-like ratio",
    "评论/点赞": "Comments/likes",
    "事件": "Events",
    "事件类型": "Event type",
    "事件簇": "Event clusters",
    "事件簇分布": "Event cluster distribution",
    "入级事件": "Graded events",
    "未入级线索": "Ungraded clues",
    "最高分": "Highest score",
    "红 / 橙": "Red / Orange",
    "分值区间": "Score range",
    "总分": "Total score",
    "权重": "Weight",
    "因子": "Factor",
    "敏感度": "Sensitivity",
    "声量归一": "Volume normalized",
    "扩散归一": "Diffusion normalized",
    "负面占比": "Negative share",
    "情感模型": "Sentiment model",
    "中性段占比": "Neutral share",
    "极端分占比": "Extreme-score share",
    "词典法": "Dictionary method",
    "词典法一致率": "Dictionary agreement",
    "正面词/负面词": "Positive/negative terms",
    "不一致样本": "Disagreement sample",
    "观点簇数": "Opinion clusters",
    "轮廓系数": "Silhouette coefficient",
    "合并评论": "Merged comments",
    "微博单源": "Weibo-only",
    "头部词": "Top terms",
    "词云词量": "Cloud terms",
    "簇覆盖率": "Cluster coverage",
    "官方": "Official",
    "媒体": "Media",
    "个人": "Individual",
    "终端标识": "Device label",
    "未归类": "Unclassified",
    "可判定率": "Classifiable rate",
    "一次作者": "One-post authors",
    "爆发型节点": "Burst nodes",
    "常态型节点": "Regular nodes",
    "头部 10 位占比": "Top-10 share",
    "峰值月": "Peak month",
    "近 12 个月": "Last 12 months",
    "有样本月份": "Months with data",
    "2026 占比": "2026 share",
    "最大事件": "Largest event",
    "最高强度格": "Highest-intensity cell",
    "多省合并串": "Multi-province merged keyword",
    "矩阵格数": "Matrix cells",
    "命中关键词": "Matched keyword",
    "命中篇数": "Matched articles",
    "活跃作者": "Active authors",
    "人均点赞": "Likes per author",
    "单条最高转发": "Maximum reposts per post",
    "最高单条赞": "Maximum likes per post",
    "缺失": "Missing",
    "状态": "Status",
    "步骤": "Step",
    "做法": "Method",
    "就绪度": "Readiness",
    "用途": "Purpose",
    "字段": "Field",
    "读法": "Interpretation",
    "口径": "Definition",
    "口径要点": "Definition notes",
    "类型": "Type",
    "形态": "Pattern",
    "级别": "Level",
    "处置口径": "Recommended action",
    "本页现状": "Current view",
    "缺口": "Gap",
    "模块": "Module",
    "分组": "Group",
    "指标": "Metric",
    "模型": "Model",
    "极性": "Polarity",
    "词表": "Vocabulary",
    "词数": "Term count",
    "概念": "Concept",
    "表": "Table",
    "说明": "Notes",
    "长江": "Yangtze River",
    "黄河": "Yellow River",
    "山东": "Shandong",
    "河南": "Henan",
    "山西": "Shanxi",
    "陕西": "Shaanxi",
    "甘肃": "Gansu",
    "青海": "Qinghai",
    "宁夏": "Ningxia",
    "内蒙古": "Inner Mongolia"
  };

  Object.assign(EXACT, {
    "流域专属地图 · 黄河流域": "Basin-Specific Map - Yellow River",
    "山东省 · 16 地市提及分布（自动聚焦）": "Shandong Province - Mention Distribution across 16 Prefecture-Level Cities (Auto Focus)",
    "目标省份声量 Top 12": "Target-Province Volume Top 12",
    "议题占比参照（三大主题 + 兜底层）": "Topic Share Reference (Three Focal Topics + Fallback)",
    "情感 × 议题（结构对照 %）": "Sentiment x Topic (Structural Comparison %)",
    "跨平台议题结构（生态治理 / 医患矛盾）": "Cross-Platform Topic Structure (Ecological Governance / Healthcare Disputes)",
    "跨平台 · 生态治理热词 Top 15": "Cross-Platform - Ecological Governance Top Terms Top 15",
    "跨平台 · 生态治理情感构成（SnowNLP 样本）": "Cross-Platform - Ecological Governance Sentiment Composition (SnowNLP Sample)",
    "跨平台 · 医患矛盾热词 Top 15": "Cross-Platform - Healthcare Dispute Top Terms Top 15",
    "跨平台 · 医患矛盾情感构成（SnowNLP 样本）": "Cross-Platform - Healthcare Dispute Sentiment Composition (SnowNLP Sample)",
    "本流域 vs 对照流域 · 六项画像对照": "Yellow River vs Reference Basin - Six-Profile Comparison",
    "因子贡献分解（各事件 × 四因子）": "Factor Contribution Decomposition (All Events x Four Factors)",
    "权重表与归一区间（口径全公开）": "Weight and Normalization Table (Full Definitions Disclosed)",
    "逐事件计分明细（每一分都能查）": "Event-Level Score Details (Traceable Score Components)"
  });

  Object.assign(EXACT, {
    "议题构成": "Topic Composition",
    "情感构成": "Sentiment Composition",
    "样本年份分布": "Sample-Year Distribution",
    "事件风险得分": "Event Risk Score",
    "分级处置口径对照": "Risk-Level Action Guide",
    "正文热词": "Post Top Terms",
    "议题速览": "Topic Overview",
    "主要事件": "Main Events",
    "情感构成": "Sentiment Composition",
    "话语主体构成": "Speaker Composition",
    "跨平台明细": "Cross-Platform Details",
    "正文词云": "Post Word Cloud",
    "事件簇释义与证据": "Event-Cluster Definitions and Evidence",
    "同义归并": "Synonym Merging",
    "黄河词云解读": "Yellow River Word-Cloud Interpretation",
    "评论年份分布": "Comment-Year Distribution",
    "评论性别构成": "Comment Gender Composition",
    "高赞评论 Top 10": "Top-10 Liked Comments",
    "评论时段分布（24 小时）": "Comment Hour Distribution (24 Hours)",
    "评论长度分段": "Comment-Length Bins",
    "评论情感构成": "Comment Sentiment Composition",
    "评论者集中度（Top 10 用户）": "Commenter Concentration (Top 10 Users)",
    "跨平台评论样本量": "Cross-Platform Comment Sample Size",
    "对比流域": "Reference basin",
    "本流域": "Yellow River",
    "画面主色调分布": "Frame Color Distribution",
    "画幅构成": "Aspect-Ratio Composition",
    "高互动短视频 Top 12": "Top-12 High-Engagement Short Videos",
    "短视频智能分析卡片墙": "Short-Video Analysis Card Wall",
    "各观点簇规模": "Opinion-Cluster Sizes",
    "观点簇一览（区分词 / 构成）": "Opinion-Cluster Overview (Distinctive Terms / Composition)",
    "各簇代表评论（簇内按点赞 Top 3）": "Representative Comments per Cluster (Top 3 by Likes)",
    "读这张表之前必须知道的两件事": "Two Important Notes Before Reading This Table",
    "互动三指标结构（占比 %）": "Interaction Structure (Share %)",
    "事件台账 · 概览": "Event Ledger - Overview",
    "事件台账 · 全量清单（点行看详情）": "Event Ledger - Full List (Click for Details)",
    "事件 × 月份（近 24 个月）": "Events x Month (Last 24 Months)",
    "事件明细（可逐格复核）": "Event Details (Cell-Level Verification)",
    "事件代表原文（每事件取最高互动 1 条）": "Representative Post per Event (Highest Interaction)",
    "事件类型 × 省份 · 传播强度矩阵（去极值均值）": "Event Type x Province - Propagation-Intensity Matrix (Winsorized Mean)",
    "传播强度逐格复核（可复算）": "Propagation-Intensity Verification (Recalculable)"
  });
  Object.assign(EXACT, {
    "黄河流域风险分级预警": "Yellow River Risk Screening",
    "事件风险得分（0–100）": "Event Risk Score (0-100)",
    "事件风险得分（0-100）": "Event Risk Score (0-100)"
  });

  Object.assign(EXACT, {
    "事件风险评分": "Event Risk Score",
    "事件聚类和核心观点提取": "Event Clustering and Key-Opinion Extraction",
    "中文分词": "Chinese Tokenization",
    "词云": "Word Cloud",
    "高频词汇": "High-Frequency Terms",
    "中央生态环保督察": "Central Ecological Inspection",
    "督察整改与问责": "Inspection Rectification and Accountability",
    "景区宰客与消费纠纷": "Scenic-Area Overcharging and Consumer Disputes",
    "游客体验与出行": "Visitor Experience and Travel",
    "景区供给与门票": "Scenic Supply and Tickets",
    "文旅融合与非遗": "Cultural Tourism Integration and Intangible Heritage",
    "水污染与排污": "Water Pollution and Discharge",
    "生态修复与湿地": "Ecological Restoration and Wetlands",
    "医疗纠纷与责任认定": "Medical Disputes and Liability Determination",
    "官方回应与调解": "Official Response and Mediation",
    "诊疗过程与手术风险": "Treatment Process and Surgical Risk",
    "法律维权与诉讼": "Legal Redress and Litigation",
    "伤医与医闹": "Violence against Clinicians and Medical Disturbances"
  });

  Object.assign(EXACT, {
    "英文概述": "English Overview",
    "事件总数": "Total Events",
    "议题类别": "Topic Categories",
    "高风险事件": "High-Risk Events",
    "事件词云图": "Event Word Cloud",
    "点击过滤词云以过滤": "Click a cloud term to filter",
    "高频词:": "High-Frequency Terms:",
    "低频词:": "Low-Frequency Terms:",
    "词云排序方式:": "Cloud Term Sorting:",
    "事件聚类定义与证据": "Event-Cluster Definitions and Evidence",
    "聚类数量:": "Cluster Count:",
    "风险筛查": "Risk Screening",
    "总风险事件": "Total Risk Events",
    "新增风险": "New Risks",
    "已处理": "Handled",
    "未处理": "Unhandled",
    "风险筛查设置": "Risk-Screening Settings",
    "筛选条件": "Filter Conditions"
  });

  const LEADS = {
    "hh-overview": "Overview of the three focal topics, source coverage, geographic distribution, sentiment structure, and cross-platform composition.",
    "hh-geo": "Author-IP location map and comparison with the province discussed in the content.",
    "hh-topic": "Side-by-side profiles of ecological governance, cultural tourism, and healthcare disputes.",
    "hh-words": "Word frequency and event-cluster-aware word cloud for Yellow River posts.",
    "hh-content": "High-impact content ranked by likes, comments, and reposts.",
    "hh-comment": "Comment distributions, sentiment, user concentration, and cross-platform sample coverage.",
    "hh-video": "Metadata, keyframes, visual understanding, ASR, and evidence-linked recommendations for short videos.",
    "hh-clust": "Exploratory comment clustering based on TF-IDF and K-means.",
    "hh-channel": "Controlled classification of official, media, individual, device-label, and unclassified speakers.",
    "hh-interact": "Interaction structure, diffusion ratios, and high-diffusion content.",
    "hh-nodes": "Propagation nodes, burst accounts, and cross-platform head patterns.",
    "hh-trend": "Monthly and annual posting patterns with explicit acquisition-bias notes.",
    "hh-events": "Event ledger, event clusters, temporal distribution, and representative posts.",
    "hh-evprov": "Event-type by province propagation-strength matrix using winsorized mean reposts.",
    "hh-risk": "Transparent four-factor risk screening, factor contributions, score levels, and review guidance.",
    "hh-method": "Data sources, definitions, sample gates, data gaps, and recalculable indicators.",
    "hh-calib": "Measured SnowNLP bias and comparison with a domain polarity dictionary.",
    "hh-qa": "Question answering constrained to the Yellow River data scope and retrieved evidence."
  };

  const PHRASES = Object.entries(EXACT).sort((a, b) => b[0].length - a[0].length);

  function trText(value, key) {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (EXACT[trimmed]) return EXACT[trimmed];
    if (["lead", "t", "s", "k", "l", "x", "name", "short", "group", "badge"].includes(key)) {
      let out = value;
      for (const pair of PHRASES) out = out.split(pair[0]).join(pair[1]);
      out = out.replace(/聚类\s*(\d+)/g, 'Cluster $1')
        .replace(/(\d+(?:\.\d+)?)\s*分/g, '$1 points')
        .replace(/(\d+)\s*位/g, '$1 authors')
        .replace(/(\d+)\s*条/g, '$1 records')
        .replace(/(\d+)\s*篇/g, '$1 articles');
      return out;
    }
    return value;
  }

  function exactWalk(value) {
    if (Array.isArray(value)) return value.map(exactWalk);
    if (value && typeof value === "object") {
      const out = {};
      Object.keys(value).forEach(k => { out[k] = exactWalk(value[k]); });
      return out;
    }
    if (typeof value === "string" && EXACT[value.trim()]) return EXACT[value.trim()];
    return value;
  }

  function walk(value, key) {
    if (Array.isArray(value)) return value.map(item => walk(item, key));
    if (value && typeof value === "object") {
      const out = {};
      Object.keys(value).forEach(k => { out[k] = walk(value[k], k); });
      return out;
    }
    return trText(value, key);
  }

  if (isEnglish && window.U) window.U = exactWalk(window.U);

  if (isEnglish && Array.isArray(window.VIEWS)) {
    window.VIEWS = window.VIEWS.map(view => {
      const translated = walk(view, "");
      if (LEADS[view.id]) translated.lead = LEADS[view.id];
      if (Array.isArray(translated.notes)) {
        translated.notes = translated.notes.map(note => Object.assign({}, note, {
          x: "See the methodology view for source notes and limitations."
        }));
      }
      return translated;
    });
  }

  function translateTextNode(node) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script,style,canvas")) return;
    const raw = node.nodeValue;
    const trimmed = raw.trim();
    if (!trimmed || !EXACT[trimmed]) return;
    const translated = EXACT[trimmed] || trimmed
      .replace(/(\d+(?:\.\d+)?)\s*分/g, '$1 points')
      .replace(/(\d+)\s*位/g, '$1 authors')
      .replace(/(\d+)\s*条/g, '$1 records')
      .replace(/(\d+)\s*篇/g, '$1 articles');
    node.nodeValue = raw.replace(trimmed, translated);
  }

  function translateSubtree(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      translateTextNode(root);
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) translateTextNode(node);
  }

  function addToggle() {
    if (document.getElementById("langSwitch")) return;
    const tools = document.querySelector(".tools-top");
    if (!tools) return;
    const button = document.createElement("button");
    button.className = "act";
    button.id = "langSwitch";
    button.textContent = isEnglish ? "中文": "EN";
    button.title = isEnglish ? "Switch to Chinese": "Switch to English";
    button.onclick = function () {
      const url = new URL(window.location.href);
      url.searchParams.set("lang", isEnglish ? "zh": "en");
      window.location.href = url.toString();
    };
    tools.prepend(button);
  }

  function applyEnglish() {
    const brand = document.querySelector(".brand");
    if (brand) {
      brand.innerHTML = "Yuyan<small>Yellow River Public Opinion Analysis System - Ecological Governance | Cultural Tourism | Healthcare Disputes</small>";
    }
    document.title = "Yuyan - Yellow River Public Opinion Analysis";
    const style = document.createElement("style");
    style.id = "en-mode-style";
    style.textContent = ".lang-en .lead,.lang-en .note{display:none!important}";
    document.head.appendChild(style);
    translateSubtree(document.body);
  }

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) { translateSubtree(node); });
    });
  });

  document.addEventListener("DOMContentLoaded", function () {
    addToggle();
    if (!isEnglish) return;
    applyEnglish();
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();

