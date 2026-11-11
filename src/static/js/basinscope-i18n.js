(function () {
  "use strict";
  const query = new URLSearchParams(window.location.search);
  const isEnglish = query.get("lang") !== "zh";
  window.BASINSCOPE_EN_MODE = isEnglish;
  if (isEnglish) {
    document.documentElement.lang = "en";
    if (document.body) document.body.classList.add("lang-en");
  }

  const EXACT = {
    "BasinScope": "SOPRAS",
    "黄河流域舆情": "Yellow River Public Opinion",
    "黄河流域": "Yellow River",
    "17 项": "17 views",
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
    "跨平台高赞内容 Top 10（微博 / 小红书 / 知乎 · 医患矛盾）": "Top 10 Cross-Platform Posts (Weibo / Xiaohongshu / Zhihu - Healthcare Disputes)",
    "环保督察 × 内蒙古": "Environmental Inspection x Inner Mongolia",
    "作者 IP 属地完整榜（Top 20 / 共 8 个省级行政区）": "Complete Author-IP Location Ranking (Top 20 of 8 provincial regions)",
    "全部已过": "All passed",
    "合成": "Synthetic",
    "生态环境保护督察": "Ecological and Environmental Inspection",
    "督察进驻": "Inspection entry",
    "黄河流域口径与方法": "Yellow River Methodology and Data Conventions",
    "黄河流域高影响力内容": "Yellow River High-Impact Content",
    "黄河流域评论洞察": "Yellow River Comment Insights",
    "黄河流域评论观点聚类": "Yellow River Opinion Clustering",
    "黄河流域发布渠道与话语主体": "Yellow River Speaker Classification",
    "黄河流域互动结构与扩散效率": "Yellow River Interaction and Diffusion",
    "黄河流域关键传播节点": "Yellow River Key Propagation Nodes",
    "黄河流域传播趋势与节奏": "Yellow River Temporal Trends",
    "黄河流域事件传播强度": "Yellow River Event-Province Propagation Intensity",
    "全样本": "Full sample",
    "按作者去重": "Unique authors",
    "高互动微博 Top 15": "Top 15 High-Engagement Weibo Posts",
    "三议题互动量对照": "Interaction Comparison Across Three Topics",
    "互动量集中度：Top10 内容 vs 全流域": "Interaction Concentration: Top 10 Content vs Full Basin",
    "高互动 Top15 的议题与省份构成": "Topic and Province Composition of the Top 15",
    "高扩散内容 Top 8（转发驱动，与点赞榜不同源）": "Top 8 Highly Diffused Posts (Repost-driven)",
    "跨平台高赞内容 Top 10（微博 / 小红书 / 知乎 · 生态治理）": "Top 10 Cross-Platform Posts (Weibo / Xiaohongshu / Zhihu - Ecological Governance)",
    "评论时间解析": "Parsed comment time",
    "部分未过": "Partially failed",
    "30 条为单类线": "30 records per-topic threshold",
    "用户（脱敏）": "User (de-identified)",
    "占本流域评论": "Share of basin comments",
    "占合并": "Share of merged comments",
    "跨平台评论样本量（合并 1549 条）": "Cross-Platform Comment Sample (1,549 merged)",
    "评论样本量 · 按议题（三大主题 × 三平台 · 微博 59 条 → 跨平台交集 949 条）": "Comment Sample by Topic (three topics x three platforms)",
    "微博+小红书+知乎": "Weibo + Xiaohongshu + Zhihu",
    "平台构成（含该平台总量占比）": "Platform Composition (share of platform total)",
    "簇1": "Cluster 1",
    "簇2": "Cluster 2",
    "簇3": "Cluster 3",
    "簇4": "Cluster 4",
    "簇5": "Cluster 5",
    "不承载主体信息": "No speaker information",
    "规则未命中": "No matching rule",
    "话语主体构成（可判定样本内）": "Speaker Composition (classifiable sample)",
    "两流域话语主体并排对照（条数）": "Speaker Comparison Across Basins (counts)",
    "两流域话语主体结构占比（%）": "Speaker Structure Across Basins (%)",
    "归类明细 Top 12（原值 → 归类依据）": "Classification Detail Top 12 (raw value -> rule)",
    "分类（原始值）": "Category (raw value)",
    "归类": "Classification",
    "命中的 token": "Matched token",
    "未归类样例 Top 8（规则没命中，不猜）": "Top 8 Unclassified Examples",
    "终端标识样例 Top 8（不是话语主体）": "Top 8 Device-Label Examples (not speakers)",
    "讨论强度": "Discussion intensity",
    "单篇互动量：本流域 vs 对照流域": "Per-Post Interaction: Yellow River vs Reference Basin",
    "分议题互动明细（可逐格复核）": "Interaction Detail by Topic",
    "单篇赞": "Likes per post",
    "单篇转": "Reposts per post",
    "扩散比 · 转发 ÷ 点赞：这一项和上面那张表量的不是同一件事": "Diffusion Ratio (reposts / likes)",
    "扩散比 · 转发 / 点赞（按事件类型）": "Diffusion Ratio by Event Type",
    "高扩散内容 Top 8（按转发绝对值）": "Top 8 Highly Diffused Posts by Reposts",
    "条数≤3 但均赞≥1000": "Posts <=3 with average likes >=1,000",
    "跨平台头部合计": "Cross-platform leader total",
    "议题 × 平台 声量矩阵": "Topic x Platform Volume Matrix",
    "爆发力榜 Top 12（按单条最高赞）": "Top 12 Burst-Potential Ranking",
    "平台头部形态对照": "Platform Leader Profile Comparison",
    "均赞": "Average likes",
    "节点档案：爆发型 vs 常态型": "Node Profiles: Burst vs Regular",
    "作者（脱敏）": "Author (de-identified)",
    "单条最高赞": "Maximum likes per post",
    "议题数": "Topic count",
    "连续铺满 180 格": "180-cell continuous matrix",
    "断月已标注": "Missing months marked",
    "月度声量 · 四线对照": "Monthly Volume - Four-Series Comparison",
    "年 × 月 声量矩阵": "Year x Month Volume Matrix",
    "近 24 个月放大": "Last 24 Months (Zoomed)",
    "年度声量（全量口径）": "Annual Volume (Full Sample)",
    "三议题月度峰值月": "Monthly Peaks Across Three Topics",
    "20 类": "20 categories",
    "与议题一一对应，可当反查索引": "One-to-one topic mapping for reverse lookup",
    "格内条数 11~37 条（配额均衡）": "Cell counts 11-37 (quota-balanced)",
    "全流域最高的一条": "Highest single post in the basin",
    "不进入矩阵（无法归省）": "Excluded from matrix (unassignable province)",
    "本流域转发": "Yellow River reposts",
    "这一页为什么不用\"条数\"编码": "Why This Page Does Not Encode by Record Count",
    "对应议题": "Mapped topic",
    "格内条数": "Cell count",
    "行内单条最高": "Row maximum per post",
    "行中位（去极值）": "Row median (winsorized)",

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
    "\u9ec4\u6cb3\u6d41\u57df\u8bcd\u9891\u4e0e\u8bcd\u4e91": "Yellow River Word Frequency and Word Cloud",
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
  };

  Object.assign(EXACT, {
    "中文": "EN",
    "聚焦全省": "Focus province",
    "周边视野": "Wider view",
    "ID 已脱敏": "De-identified IDs",
    "内容涉及省": "Content provinces",
    "8 个": "8 provinces",
    "去重后": "after de-duplication",
    "生态作者": "Ecological Governance authors",
    "文旅作者": "Cultural Tourism authors",
    "医患作者": "Healthcare Disputes authors",
    "声量": "Volume",
    "扩散": "Diffusion",
    "敏感": "Sensitivity",
    "三源交集议题": "Cross-source topic",
    "医德医风": "Medical ethics and conduct",
    "看病难": "Difficulty accessing care",
    "河长制": "River chief system",
    "医闹·医患纠纷": "Medical disturbances and disputes",
    "医疗事故·医疗纠纷": "Medical accidents and disputes",
    "医闹、医患纠纷、医疗事故、伤医": "Medical disturbances, disputes, accidents, and violence against clinicians",
    "生态": "Ecology",
    "督察": "Inspection",
    "环保": "Environmental protection",
    "中央": "Central",
    "景区": "Scenic area",
    "旅游": "Tourism",
    "游客": "Visitors",
    "医院": "Hospitals",
    "医患": "Doctor-patient",
    "纠纷": "Disputes",
    "患者": "Patients",
    "医生": "Physicians",
    "环境保护": "Environmental protection",
    "生态环境": "Ecological environment",
    "近日": "Recently",
    "开展": "Carry out",
    "督察组": "Inspection team",
    "宰客": "Overcharging",
    "发现": "Found",
    "环境": "Environment",
    "国家": "National",
    "整改": "Rectification",
    "文化": "Culture",
    "推进": "Promote",
    "保护": "Protection",
    "消费": "Consumption",
    "安全": "Safety",
    "持续": "Sustained",
    "市场": "Market",
    "治理": "Governance",
    "发布": "Release",
    "当地": "Local",
    "深入": "In-depth",
    "绿色": "Green",
    "通报": "Briefing",
    "国庆": "National Day",
    "部门": "Department",
    "全面": "Comprehensive",
    "现场": "Site",
    "回应": "Response",
    "直接": "Direct",
    "责任": "Responsibility",
    "重点": "Key",
    "企业": "Enterprise",
    "修复": "Restoration",
    "污染": "Pollution",
    "垃圾与固废": "Waste and solid refuse",
    "伤医与医闹（线索）": "Violence against clinicians and medical disturbances (clue)",
    "Comments闸门": "Comment gate",
    "Post Word Cloud · 按Event clusters着色": "Post Word Cloud - Coloured by Event Cluster",
    "Synonym Merging：被分词切碎的Concept": "Synonym Merging: Concepts Split by Tokenization",
    "Ecological Governance · 跨Platform热词 Top 15": "Ecological Governance - Cross-Platform Top Terms 15",
    "Healthcare Disputes · 跨Platform热词 Top 15": "Healthcare Disputes - Cross-Platform Top Terms 15",
    "14 个": "14",
    "归纳自正文语料": "Derived from post corpus",
    "生态 218 / Cultural Tourism 327 / 医患 141 articles被覆盖": "Coverage: 218 Ecological Governance / 327 Cultural Tourism / 141 Healthcare Disputes articles",
    "Ecology 218 / Cultural Tourism 327 / Doctor-patient 141 articles被覆盖": "Coverage: 218 Ecological Governance / 327 Cultural Tourism / 141 Healthcare Disputes articles",
    "被覆盖": "covered",
    "人工词汇归纳": "Manual vocabulary compilation",
    "人工Vocabulary归纳": "Manual vocabulary compilation",
    "线上事件只作线索": "Online events used only as clues",
    "线上Events只作线索": "Online events used only as clues",
    "首次": "First seen",
    "主事件面板": "Primary Event Panel",
    "规模最大的事件": "Largest Event",
    "条命中": "matched articles",
    "负面": "Negative",
    "最近": "Most recent",
    "首要省份": "Primary province",
    "首要Province": "Primary province",
    "黄河源·巴颜喀拉": "Yellow River source - Bayan Har",
    "Yellow River源·巴颜喀拉": "Yellow River source - Bayan Har",
    "山东省": "Shandong Province",
    "新闻": "News",
    "美丽": "Beautiful",
    "高质量": "High quality",
    "青岛": "Qingdao",
    "举报": "Reporting",
    "非法": "Illegal",
    "乡村": "Rural",
    "非遗": "Intangible heritage",
    "手术": "Surgery",
    "调查": "Investigation",
    "检查": "Inspection",
    "排污": "Discharge",
    "价格": "Price",
    "污水": "Wastewater",
    "文明": "Civilized",
    "调解": "Mediation",
    "律师": "Lawyer",
    "门票": "Tickets",
    "景点": "Scenic spots",
    "水质": "Water quality",
    "免费": "Free",
    "酒店": "Hotels",
    "黑臭": "Black-odorous water",
    "排污口": "Discharge outlet",
    "岸线": "Shoreline",
    "美食": "Food",
    "固废": "Solid waste",
    "研学": "Educational tourism",
    "殴打": "Assault",
    "退票": "Refund",
    "免票": "Free admission",
    "用药": "Medication",
    "法律": "Law",
    "法院": "Court",
    "湿地": "Wetlands",
    "维权": "Rights protection",
    "卫健委": "Health Commission",
    "问责": "Accountability",
    "商家": "Business",
    "民宿": "Homestays",
    "垃圾": "Waste",
    "治疗": "Treatment",
    "诉讼": "Litigation",
    "排放": "Emissions",
    "鉴定": "Appraisal",
    "抢救": "Rescue",
    "暴力": "Violence",
    "博物馆": "Museum",
    "伤医": "Violence against clinicians",
    "保护区": "Protected area",
    "赔偿": "Compensation",
    "医闹": "Medical disturbance",
    "省份构成": "Province composition",
    "Province构成": "Province composition",
    "高负警示块": "High-Negative Events",
    "逐月命中对照": "Monthly Match Heatmap",
    "议题对比": "Topic Comparison",
    "负面占比区间": "Negative Share Range",
    "条 / 5Events": "articles / 5 events",
    "条 / 4 个Events": "articles / 4 events",
    "条 / 5个事件": "articles / 5 events",
    "条 / 4 个事件": "articles / 4 events",
    "含Events词 59 个": "59 event-related terms",
    "出现最多": "Most frequent",
    "采集端矩阵": "Acquisition matrix",
    "议题": "Topic",
    "明细词": "Detail terms",
    "5 个": "5",
    "KMeans 自动": "KMeans automatic",
    "低于 300 门槛": "Below the 300-comment gate",
    "越高越可分": "Higher is better separated",
    "簇": "Cluster",
    "区分词（该簇独占）": "Distinctive terms (exclusive to cluster)",
    "Platform构成（含该Platform总量Share）": "Platform composition (share of total platform volume)",
    "12 个": "12",
    "58.8 分": "58.8 points",
    "2 个": "2",
    "闸门 30 records": "30-record gate",
    "一级 / 二级": "Tier 1 / Tier 2",
    "Sample不足": "Insufficient sample",
    "Negative/声量/敏感/扩散": "Negative / Volume / Sensitivity / Diffusion",
    "FactorWeight": "Factor weight",
    "本流域归一区间": "Yellow River normalization range",
    "Yellow River归一区间": "Yellow River normalization range",
    "Yellow RiverEvents数": "Yellow River event count",
    "该事件命中微博里 SnowNLP 判为负面的篇数占比（本流域内归一）": "Share of matched Weibo articles classified as negative by SnowNLP (normalized within the Yellow River scope)",
    "该事件命中篇数 ÷ 本流域最大事件篇数": "Matched articles divided by the largest event article count in the Yellow River scope",
    "命中文本里出现官方主体/督察整改问责类词的比例（见 SENS_WORDS）": "Share of matched texts containing official-subject or inspection-rectification terms (see SENS_WORDS)",
    "该事件平均每篇转发数 ÷ 本流域最大事件均值": "Mean reposts per article divided by the largest event-level mean in the Yellow River scope",
    "命中篇数未过闸门，只作线索，不做分级与占比推断": "Below the article-count gate; retained only as a clue without grading or share inference",
    "Score range与Recommended action是规则设定值，评审可直接质疑Weight —— 页面已给出全部原始量": "Score ranges and recommended actions are rule-based values; all raw quantities are shown for review",
    "列入每日监测清单，逐条核验原文与处置进展": "Add to the daily monitoring list and verify the source text and response progress",
    "按周复核，关注负面占比是否继续上行": "Review weekly and check whether the negative share continues to rise"
  });

  Object.assign(EXACT, {
    "\u9996\u9875": "Home",
    "\u5fae\u535a\u70ed\u8bcd\u7edf\u8ba1": "Weibo Hot Words",
    "\u5fae\u535a\u8206\u60c5\u5206\u6790": "Weibo Public-Opinion Analysis",
    "\u6570\u636e\u53ef\u89c6\u5316": "Data Visualization",
    "\u5fae\u535a\u6587\u7ae0\u5206\u6790": "Weibo Article Analysis",
    "\u5fae\u535aIP\u5206\u6790": "Weibo IP Analysis",
    "\u5fae\u535a\u8bc4\u8bba\u5206\u6790": "Weibo Comment Analysis",
    "\u5fae\u535a\u60c5\u611f\u5206\u6790": "Weibo Sentiment Analysis",
    "\u77ed\u89c6\u9891\u5206\u6790": "Short-Video Analysis",
    "\u957f\u6c5f\u6d41\u57df\u77ed\u89c6\u9891": "Yangtze River Short Videos",
    "\u9ec4\u6cb3\u6d41\u57df\u77ed\u89c6\u9891": "Yellow River Short Videos",
    "\u8bcd\u4e91\u56fe": "Word Clouds",
    "\u5fae\u535a\u5185\u5bb9\u8bcd\u4e91\u56fe": "Weibo Post Word Cloud",
    "\u5fae\u535a\u8bc4\u8bba\u8bcd\u4e91\u56fe": "Weibo Comment Word Cloud",
    "\u5fae\u535a\u8bc4\u8bba\u7528\u6237\u8bcd\u4e91\u56fe": "Weibo Comment-User Word Cloud",
    "\u5f53\u524d\u7528\u6237": "Current user",
    "\u8bbf\u5ba2": "Guest",
    "\u5b89\u5168\u9000\u51fa": "Sign out",
    "\u672c\u7cfb\u7edf\u542b": "This system includes",
    "\u5168\u7ad9\u4e00\u4f53\u5316\u8206\u60c5\u5206\u6790": "Multi-source public-opinion analytics",
    "\u5408\u89c4\u58f0\u660e\uff1a\u672c\u7cfb\u7edf\u90e8\u5206\u5206\u6790\u5185\u5bb9\u7531 AI \u5927\u6a21\u578b\u7ed3\u5408\u4e13\u4e1a\u77e5\u8bc6\u5e93\u81ea\u52a8\u751f\u6210\uff0c\u4ec5\u4f9b\u5b66\u672f\u79d1\u7814\u4e0e\u6559\u5b66\u53c2\u8003\u3002": "Compliance notice: Some analytical content is generated by an AI model with a domain knowledge base and is intended only for academic research and teaching reference.",
    "\u5fae\u535a\u6587\u7ae0\u603b\u91cf": "Total Weibo posts",
    "\u6700\u9ad8\u70b9\u8d5e\u5fae\u535a-\u4f5c\u8005": "Most-liked post: author",
    "\u5fae\u535a\u70b9\u8d5e\u6700\u591a-\u57ce\u5e02": "City with the most Weibo likes",
    "\u65e0\u6570\u636e": "No data",
    "\u6700\u8fd1\u4e03\u5929\u5fae\u535a\u53d1\u5e03\u91cf": "Weibo posts in the last seven days",
    "\u5fae\u535a\u70b9\u8d5e\u91cfTop6": "Top 6 Weibo posts by likes",
    "\u8d26\u53f7\u9886\u57df\u6784\u6210\uff08\u53d7\u63a7\u8bcd\u8868 Top 10\uff09": "Account domains (controlled vocabulary, Top 10)",
    "\u8bc4\u8bba\u7528\u6237\u540d\u8bcd\u4e91\u56fe": "Comment-user word cloud",
    "\u8bc4\u8bba\u7528\u6237\u65f6\u95f4\u5360\u6bd4\u73af\u5f62\u997c\u72b6\u56fe": "Comment-user time-share donut chart",
    "\u5b66\u79d1\u5782\u7c7b\u5927\u6a21\u578b\uff1aAI\u8206\u60c5\u5206\u6790\u52a9\u624b": "Domain LLM: AI Public-Opinion Assistant",
    "\u79fb\u9664\u56fe\u7247": "Remove image",
    "\u79fb\u9664\u6587\u6863": "Remove document",
    "\u4e0a\u4f20\u56fe\u7247": "Upload image",
    "\u4e0a\u4f20\u6587\u6863": "Upload document",
    "\u4e0a\u4f20\u56fe\u8868\u622a\u56fe": "Upload a chart screenshot",
    "\u4e0a\u4f20\u6587\u6863\uff08PDF/Word/Excel\u7b49\uff09": "Upload a document (PDF/Word/Excel)",
    "\u53d1\u9001\u63d0\u95ee": "Send question",
    "\u751f\u6210\u5b8c\u6574\u5b66\u672f\u62a5\u544a": "Generate full academic report",
    "\u8bf7\u8f93\u5165\u60a8\u7684\u5b66\u672f\u95ee\u9898\uff0c\u6216\u4e0a\u4f20\u56fe\u7247/\u6587\u6863\u8ba9 AI \u5206\u6790...": "Enter a research question, or upload an image/document for AI analysis...",
    "\u5df2\u9644\u52a0\u56fe\u7247\uff0cAI \u5c06\u4f7f\u7528\u591a\u6a21\u6001\u89c6\u89c9\u5f15\u64ce\u8fdb\u884c\u5206\u6790": "Image attached. The AI will analyze it with the multimodal vision service."
  });
  Object.assign(EXACT, {
    "\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09 \u00b7 \u586b\u5145\uff1dTarget-Province Volume\uff08": "Only provinces through which the river actually flows (including shared-source provinces) ? Fill = target-province volume (",
    "\u6309\u4f4d\u6b21\u7b49\u9891\u5206 8 \u7ea7": "Equal-frequency rank based on 8 levels",
    "\uff0c\u8d8a\u4eae\u8d8a\u9ad8\uff0c\u65ad\u70b9\u89c1\u5361\u4e0b\u8272\u6807\uff09 \u00b7 Yellow River\uff1d\u9ec4\u8272\u6d41\u52a8\u7ebf\uff08\u5e72\u6d41\u8d70\u5411\uff09": ", with brighter colors indicating higher values; breakpoints are shown in the legend) ? Yellow River = yellow flow line (mainstem direction)",
    "\u586b\u5145\uff1dTarget-Province Volume\uff0c": "Fill = target-province volume,",
    "\uff08\u8d8a\u4eae\u8d8a\u9ad8\uff09\uff1a": "(brighter indicates higher):",
    "Yellow River\u5e72\u6d41 \u00b7 \u9ec4\u8272\u6d41\u52a8\u7ebf\uff08\u6e90\u2192\u5165\u6d77\u5faa\u73af\uff09": "Yellow River mainstem ? yellow flow line (source to estuary)",
    "\u65e0Yellow RiverSample": "No Yellow River sample",
    "\u00b7 \u6700\u9ad8 458 records / \u6700\u4f4e 49 records\uff08\u5206\u6bcd = Yellow RiverWeibo 899 records\uff09 \u00b7 \u5404\u56fe\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09\uff1b\u8272\u9636\u6309Yellow River\u6570\u503c\u7b49\u9891\u5206\u7ea7\uff08\u975e\u7ebf\u6027\u62c9\u4f38\uff09 \u00b7": "? Maximum 458 records / minimum 49 records (denominator = 899 Yellow River Weibo records) ? Each map shows only provinces through which the river flows (including shared-source provinces); color levels use equal-frequency bins of Yellow River values (nonlinear stretch) ?",
    "\u6eda\u8f6e / \u53cc\u6307\u53ef\u7f29\u653e": "Scroll / pinch to zoom",
    "\u9875\u9762\u52a0\u8f7d 2 \u79d2\u540e\u81ea\u52a8\u805a\u7126\u5230": "Auto-focus after 2 seconds on",
    "\uff0c\u53f3\u4fa7\u300cWider view\u300d\u53ef\u9000\u56de\u542b\u6cb3\u5317 / Henan / \u5b89\u5fbd / \u6c5f\u82cf \u7684\u5927\u89c6\u91ce \u00b7 \u586b\u5145\uff1dWeibo\u6b63\u6587\u63d0\u53ca\u6b21\u6570\uff0c\u6309": ", use the ?Wider view? button on the right to return to the broader view including Hebei / Henan / Anhui / Jiangsu ? Fill = Weibo post mention count, using",
    "\u5bf9\u6570\u4e94\u5206\u4f4d": "log quintiles",
    "\u5206\u6863\uff08\u5934\u90e8 314 \u6b21\u4e0e\u4e2a\u4f4d\u6570\u5730\u5e02\u540c\u56fe\uff0c\u7ebf\u6027\u5f52\u4e00\u4f1a\u628a\u5176\u4f59\u5730\u5e02\u5168\u538b\u5230\u6700\u6de1\u4e00\u6863\uff09 \u00b7": "bins (the top value of 314 and single-digit cities share one map; linear normalization would push all other cities into the lightest bin) ?",
    "\u60ac\u505c": "Hover",
    "\u770b\u6570\u503c\u3001": "to view values,",
    "\u70b9\u51fb": "Click",
    "\u9501\u5b9a\u5de6\u4e0b\u8be6\u60c5\uff08Esc \u53d6\u6d88\uff09 \u00b7 \u6eda\u8f6e / \u62d6\u62fd\u53ef\u81ea\u884c\u7f29\u653e\u3002": "to lock the lower-left details (Esc to cancel) ? Scroll / drag to zoom.",
    "\u6b63\u6587\u91cc\u51fa\u73b0\u8be5\u5e02\u540d\u7684\u6b21\u6570": "Number of mentions of the city name in post text",
    "\uff08\u5173\u952e\u8bcd\u547d\u4e2d\uff0c\u6765\u81ea\u5168\u91cf t_article\uff1b\u4e0d\u662f IP \u5c5e\u5730\u3001\u4e5f\u4e0d\u662f\u5730\u5e02\u7ea7\u91c7\u96c6\u7ed3\u679c\uff09\uff1a\u5e93\u91cc\u53ea\u5230\u7701\u7ea7\u7c92\u5ea6\uff0c\u4e0d\u5b58\u5728\u300c\u67d0\u5e02\u8206\u60c5\u591a\u5c11\u6761\u300d\u8fd9\u79cd\u8bf4\u6cd5 \u2014\u2014 \u6240\u4ee5\u672c\u56fe\u4e0d\u7ed9\u4efb\u4f55\u4e00\u5ea7\u57ce\u5e02\u7f16Volume\uff0c\u53ea\u6570\u6b63\u6587\u53eb\u5230\u5b83\u540d\u5b57\u7684\u6b21\u6570\u3002\u540c\u4e00Definition\u7684Home\u7f29\u7565\u56fe\u89c1\u300c\u5730\u7406\u533a\u4f4d \u00b7 \u4e2d\u56fd \u2192 Shandong \u2192 \u6d4e\u5357\u300d\u3002": "(keyword matches from the full t_article table; this is neither IP location nor city-level collection): the database is only province-level, so there is no defensible city-level public-opinion count. The map therefore assigns no volume to any city and only counts post-text mentions. See the home thumbnail under ?Geography ? China ? Shandong ? Jinan?.",
    "\u6b63\u6587\u63d0\u53ca\u6b21\u6570": "Post mention count",
    "\uff08Weibo\u6b63\u6587\u51fa\u73b0\u8be5\u5e02\u540d\u7684\u6b21\u6570\uff09": "(number of Weibo posts mentioning the city name)",
    "\u90bb\u7701\uff08\u6cb3\u5317 / Henan / \u5b89\u5fbd / \u6c5f\u82cf\uff0c\u53ea\u4f5c\u533a\u4f4d\u53c2\u7167\uff09": "Neighboring provinces (Hebei / Henan / Anhui / Jiangsu; geographic reference only)",
    "\u6863\u4f4d\u6309": "Levels are defined by",
    "\u5212\u5206\uff08\u6781\u5dee\u592a\u5927\uff0c\u7ebf\u6027\u5f52\u4e00\u4f1a\u628a\u9664\u5934\u90e8\u5916\u7684\u5730\u5e02\u5168\u538b\u5230\u6700\u6de1\u4e00\u6863\uff09\u00b7 \u672c\u56fe": "bins (the range is too large; linear normalization would push all but the top cities into the lightest bin) ? This map",
    "\u4e0d\u662f\u5730\u5e02\u7ea7\u91c7\u96c6\u7ed3\u679c": "is not a city-level collection result",
    "\uff1a\u5e93\u91cc\u6ca1\u6709\u5730\u5e02Field\uff0c\u63d0\u53ca\u6570\u7531": ": the database has no city field; mention counts are derived from",
    "\u6b63\u6587\u5173\u952e\u8bcd": "post keywords",
    "\u547d\u4e2d\u5f97\u5230\uff08Definition\u89c1\u300cMethodology and Data Conventions\u300d\uff09\u3002\u60ac\u505c\u770b\u6570\u503c\uff0c\u70b9\u51fb\u53ef\u9501\u5b9a\u5de6\u4e0b\u8be6\u60c5\uff1b\u53f3\u4e0a\u89d2\u4e24\u4e2a\u6309\u94ae\u5207\u6362\u300c\u5168\u7701 / \u542b\u90bb\u7701\u300d\u89c6\u91ce\uff0c\u6eda\u8f6e\u6216\u62d6\u62fd\u53ef\u81ea\u884c\u7f29\u653e\u3002": "matches (see Methodology and Data Conventions). Hover to view values; click to lock details in the lower-left panel; use the two buttons in the upper right to switch between province and neighboring-province views; scroll or drag to zoom.",
    "\u4e09\u5927\u4e3b\u9898\uff08Ecological Governance / Cultural Tourism / Healthcare Disputes\uff09\u00b7 Social Governance\u4e3a\u515c\u5e95\u5c42": "Three focal topics (Ecological Governance / Cultural Tourism / Healthcare Disputes) ? Social Governance is the fallback layer",
    "SnowNLP \u8f7b\u91cfModel \u00b7 Negative share 33.0%": "SnowNLP lightweight model ? Negative share 33.0%",
    "Release\u65f6\u95f4\u89e3\u6790\u6240\u5f97 \u00b7 \u8fd1\u5e74SampleShare\u9ad8": "Parsed from release time ? The recent sample share is high",
    "\u5206\u6bcd = Yellow River\u5168\u90e8 1,097 records\uff1b\u4e09\u5927\u4e3b\u9898\uff08Ecological Governance / Cultural Tourism / Healthcare Disputes\uff09\u5168\u90e8\u5c55\u5f00\u3001Weibo\u805a\u7126 899 records\uff08\u5176\u4e2dEcological Governance / Healthcare Disputes\u53e6\u6709\u8de8Platform\u4e09\u6e90Definition\uff09\uff1bSocial Governance\u4e3a\u515c\u5e95\u5c42\uff08\u5173\u952e\u8bcd\u672a\u547d\u4e2d\u5176\u4ed6Topic\uff09\u3001\u53ea\u4f5c\u5206\u6bcd\u3002": "Denominator = all 1,097 Yellow River records; all three focal topics (Ecological Governance / Cultural Tourism / Healthcare Disputes) are expanded, with 899 Weibo records (Ecological Governance and Healthcare Disputes also have three-source cross-platform definitions); Social Governance is the fallback layer (keywords did not match another topic) and is used only in the denominator.",
    "\u4e09\u4e2aTopic\u5404\u81ea\u5185\u90e8\u7684\u6b63/\u4e2d/\u8d1f\u7ed3\u6784\uff08\u5404\u6309Topic\u5185 100% \u5f52\u4e00\uff09 \u00b7 \u53ea\u6bd4\u7ed3\u6784\uff0c\u4e0d\u505aPolarity\u5916\u63a8": "Positive/neutral/negative structure within each topic, normalized to 100% within that topic ? Structural comparison only; no polarity extrapolation",
    "\u56db\u6e90\u4ea4\u96c6Topic\uff1a\u6bcf\u6761\u6309\u6240\u5728Platform\u5185\u90e8 100% \u5f52\u4e00\uff0c\u53ea\u6bd4\u7ed3\u6784Share\u3001\u4e0d\u5bf9\u9f50\u7edd\u5bf9\u503c\uff1bDouyin 0 records\u672a\u8ba1\u5165\u3002Cultural Tourism \u4e3aWeibo\u72ec\u6709\uff0c\u4e0d\u5728\u8de8\u6e90Definition\u5185\u3002": "Four-source topic intersection: each record is normalized to 100% within its platform; only structural shares are compared, not absolute values; Douyin 0 records are excluded. Cultural Tourism occurs only on Weibo and is outside the cross-source definition.",
    "Weibo / Xiaohongshu / Zhihu \u4e09\u6e90\u6b63\u6587\u5206\u8bcd\u5408\u5e76\uff08\u4ea4\u96c6Topic\uff0c\u6309Matched articles\uff09": "Weibo / Xiaohongshu / Zhihu three-source post-token merge (intersection topics, by matched articles)",
    "\u4e09\u6e90\u5408\u5e76\u6b63\u6587\u62bd\u6837 250 records\uff1bModel\u672a\u6821\u51c6\uff0c\u4ec5\u7ed3\u6784\u53c2\u8003": "250 sampled merged three-source posts; model uncalibrated, structural reference only",
    "\u8fd9\u4e00\u5f20\u628a\u4e24\u4e2a\u4e13\u9898\u7684\u5dee\u5f02\u505a\u6210\u53ef\u6838\u5bf9\u7684\u516d\u884c\uff0c\u907f\u514d\"\u4e24\u8fb9\u5dee\u4e0d\u591a\"\u7684\u5370\u8c61": "This panel compares the two topics across six rows for verification, avoiding an impression that they are similar",
    "\u6837\u672c\u91cf": "Sample size",
    "\u4e24\u4fa7\u5747\u4e3a\u7b49\u91cf\u91c7\u6837\u53e3\u5f84": "Both sides use equal-size sampling",
    "\u6570\u503c\u8d8a\u9ad8\u8d8a\u6613\u6269\u6563": "Higher values indicate greater diffusion potential",
    "\u8f6c\u53d1\u00f7\u70b9\u8d5e\uff1b\u9ad8\uff1d\u89c2\u70b9\u8f7d\u4f53\uff0c\u4f4e\uff1d\u56f4\u89c2\u8868\u6001": "Reposts ? likes; high = opinion carrier, low = spectator response",
    "\u53ef\u5224\u5b9a\u5b98\u65b9\u8d26\u53f7\u5360\u6bd4": "Share of identifiable official accounts",
    "\u53ea\u770b\u53ef\u5224\u5b9a\u4e3b\u4f53\u6837\u672c\uff0c\u4e0d\u662f\u5168\u91cf": "Only identifiable subject samples; not the full sample",
    "\u76ee\u6807\u7701\u4efd\u6570": "Number of target provinces",
    "\u91c7\u96c6\u914d\u989d\u53e3\u5f84\uff0c\u53cd\u6620\u8986\u76d6\u5e7f\u5ea6": "Collection quota basis; reflects coverage breadth",
    "\u5934\u90e8 10 \u4f5c\u8005\u5360\u6bd4": "Share of the top 10 authors",
    "\u8d8a\u4f4e\u8d8a\u5206\u6563": "Lower values indicate greater dispersion",
    "\u6570\u636e\u5feb\u7167\uff1a2026-10-15 21:44 \u00b7 \u53e3\u5f84\u7edf\u4e00\u7531 unified_data.json \u63d0\u4f9b\uff0c\u9875\u9762\u5185\u6240\u6709\u6570\u5b57\u4e0e\u56fe\u8868\u540c\u6e90\uff1b\u6807\u6ce8": "Data snapshot: 2026-10-15 21:44 ? conventions are provided by unified_data.json; all numbers and charts on this page share the same source; labels",
    "\u771f\u5b9e": "Real",
    "\u4e3a\u5e93/\u6587\u4ef6\u5b9e\u6d4b\uff0c": "are measured from databases/files,",
    "\u6f14\u793a": "Demo",
    "\u4e3a\u754c\u9762\u539f\u578b\u3002": "are interface prototypes.",
    "\u589e\u91cf\u91c7\u96c6\u6700\u65b0\u5fae\u535a\u5e76\u91cd\u5efa\u672c\u9875\uff08quick \u6863\u7ea6 3~6 \u5206\u949f\uff09": "Incrementally collect new Weibo posts and rebuild this page (quick mode, about 3-6 minutes)",
    "\u7acb\u5373\u6e32\u67d3\u672c\u9875\u5168\u90e8\u56fe\u8868\uff08\u6eda\u52a8\u65f6\u4e5f\u4f1a\u81ea\u52a8\u8865\u6e32\u67d3\uff09": "Render all charts on this page now (off-screen charts also render on scroll)",
    "\u8c03\u7528\u6d4f\u89c8\u5668\u6253\u5370\uff0c\u53ef\u53e6\u5b58\u4e3a PDF\uff08\u4fdd\u7559\u6df1\u8272\u5e95\uff09": "Open browser print and save as PDF (dark background retained)",
    "\u9ec4\u6cb3\u6d41\u57df\u8206\u60c5\u5206\u6790 \u00b7 \u751f\u6001\u6cbb\u7406 / \u6587\u65c5 / \u533b\u60a3\u77db\u76fe": "Yellow River public-opinion analysis ? Ecological governance / Cultural tourism / Healthcare disputes",
    "\u5bfc\u51fa\u8be5\u56fe PNG\uff082\u00d7 \u5206\u8fa8\u7387\uff0c\u542b\u6df1\u8272\u5e95\uff09": "Export this chart as PNG (2x resolution, dark background)",
    "\u628a\u5c71\u4e1c\u7701 16 \u5730\u5e02\u521a\u597d\u94fa\u6ee1\u753b\u5e03": "Fit all 16 prefecture-level cities in Shandong to the canvas",
    "\u7f29\u5c0f\u5230\u542b\u6cb3\u5317 / \u6cb3\u5357 / \u5b89\u5fbd / \u6c5f\u82cf \u7684\u89c6\u91ce": "Zoom out to include Hebei / Henan / Anhui / Jiangsu",
    "\u5bfc\u51fa\u8be5\u8868 CSV\uff08UTF-8 BOM\uff0cExcel \u53ef\u76f4\u63a5\u6253\u5f00\uff09": "Export this table as CSV (UTF-8 BOM, opens directly in Excel)"
  });
  Object.assign(EXACT, {
    "\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09 \u00b7 \u586b\u5145\uff1dTarget-Province Volume\uff08": "Shows only provinces through which the river actually flows (including shared-source provinces) ? Fill = target-province volume (",
    "\uff0c\u8d8a\u4eae\u8d8a\u9ad8\uff0c\u65ad\u70b9\u89c1\u5361\u4e0b\u8272\u6807\uff09 \u00b7 Yellow River\uff1d\u9ec4\u8272\u6d41\u52a8\u7ebf\uff08\u5e72\u6d41\u8d70\u5411\uff09": ", with brighter colors indicating higher values; breakpoints are shown in the legend below the map) ? Yellow River = yellow flow line (mainstem direction)",
    "\u586b\u5145\uff1dTarget-Province Volume\uff0c": "Fill = target-province volume,",
    "Yellow River\u5e72\u6d41 \u00b7 \u9ec4\u8272\u6d41\u52a8\u7ebf\uff08\u6e90\u2192\u5165\u6d77\u5faa\u73af\uff09": "Yellow River mainstem ? yellow flow line (source to estuary)",
    "\u65e0Yellow RiverSample": "No Yellow River sample",
    "\u00b7 \u6700\u9ad8 458 records / \u6700\u4f4e 49 records\uff08\u5206\u6bcd = Yellow RiverWeibo 899 records\uff09 \u00b7 \u5404\u56fe\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09\uff1b\u8272\u9636\u6309Yellow River\u6570\u503c\u7b49\u9891\u5206\u7ea7\uff08\u975e\u7ebf\u6027\u62c9\u4f38\uff09 \u00b7": "? Maximum 458 records / minimum 49 records (denominator = 899 Yellow River Weibo records) ? Each map shows only provinces through which the river flows (including shared-source provinces); color levels use equal-frequency bins of Yellow River values (nonlinear stretch) ?",
    "\uff0c\u53f3\u4fa7\u300cWider view\u300d\u53ef\u9000\u56de\u542b\u6cb3\u5317 / Henan / \u5b89\u5fbd / \u6c5f\u82cf \u7684\u5927\u89c6\u91ce \u00b7 \u586b\u5145\uff1dWeiboPost mention count\uff0c\u6309": ", use the ?Wider view? button on the right to return to the broader view including Hebei / Henan / Anhui / Jiangsu ? Fill = Weibo post mention count, using",
    "\u5206\u6863\uff08\u5934\u90e8 314 \u6b21\u4e0e\u4e2a\u4f4d\u6570\u5730\u5e02\u540c\u56fe\uff0c\u7ebf\u6027\u5f52\u4e00\u4f1a\u628a\u5176\u4f59\u5730\u5e02\u5168\u538b\u5230\u6700\u6de1\u4e00\u6863\uff09 \u00b7": "bins (the top value of 314 and single-digit cities share one map; linear normalization would push all other cities into the lightest bin) ?",
    "\u9501\u5b9a\u5de6\u4e0b\u8be6\u60c5\uff08Esc \u53d6\u6d88\uff09 \u00b7 \u6eda\u8f6e / \u62d6\u62fd\u53ef\u81ea\u884c\u7f29\u653e\u3002": "to lock the lower-left details (Esc to cancel) ? Scroll / drag to zoom.",
    "\uff08\u5173\u952e\u8bcd\u547d\u4e2d\uff0c\u6765\u81ea\u5168\u91cf t_article\uff1b\u4e0d\u662f IP \u5c5e\u5730\u3001\u4e5fis not a city-level collection result\uff09\uff1a\u5e93\u91cc\u53ea\u5230\u7701\u7ea7\u7c92\u5ea6\uff0c\u4e0d\u5b58\u5728\u300c\u67d0\u5e02\u8206\u60c5\u591a\u5c11\u6761\u300d\u8fd9\u79cd\u8bf4\u6cd5 \u2014\u2014 \u6240\u4ee5\u672c\u56fe\u4e0d\u7ed9\u4efb\u4f55\u4e00\u5ea7\u57ce\u5e02\u7f16Volume\uff0c\u53ea\u6570\u6b63\u6587\u53eb\u5230\u5b83\u540d\u5b57\u7684\u6b21\u6570\u3002\u540c\u4e00Definition\u7684Home\u7f29\u7565\u56fe\u89c1\u300c\u5730\u7406\u533a\u4f4d \u00b7 \u4e2d\u56fd \u2192 Shandong \u2192 \u6d4e\u5357\u300d\u3002": "(keyword matches from the full t_article table; this is neither IP location nor city-level collection): the database is only province-level, so there is no defensible city-level public-opinion count. The map therefore assigns no volume to any city and only counts post-text mentions. See the home thumbnail under ?Geography ? China ? Shandong ? Jinan?.",
    "\uff08Weibo\u6b63\u6587\u51fa\u73b0\u8be5\u5e02\u540d\u7684\u6b21\u6570\uff09": "(number of Weibo posts mentioning the city name)",
    "\u90bb\u7701\uff08\u6cb3\u5317 / Henan / \u5b89\u5fbd / \u6c5f\u82cf\uff0c\u53ea\u4f5c\u533a\u4f4d\u53c2\u7167\uff09": "Neighboring provinces (Hebei / Henan / Anhui / Jiangsu; geographic reference only)",
    "\uff1a\u5e93\u91cc\u6ca1\u6709\u5730\u5e02Field\uff0c\u63d0\u53ca\u6570\u7531": ": the database has no city field; mention counts are derived from",
    "\u547d\u4e2d\u5f97\u5230\uff08Definition\u89c1\u300cMethodology and Data Conventions\u300d\uff09\u3002Hover\u770b\u6570\u503c\uff0cClick\u53ef\u9501\u5b9a\u5de6\u4e0b\u8be6\u60c5\uff1b\u53f3\u4e0a\u89d2\u4e24\u4e2a\u6309\u94ae\u5207\u6362\u300c\u5168\u7701 / \u542b\u90bb\u7701\u300d\u89c6\u91ce\uff0c\u6eda\u8f6e\u6216\u62d6\u62fd\u53ef\u81ea\u884c\u7f29\u653e\u3002": "matches (see Methodology and Data Conventions). Hover to view values; click to lock details in the lower-left panel; use the two buttons in the upper right to switch between province and neighboring-province views; scroll or drag to zoom.",
    "\u6570\u636e\u5feb\u7167\uff1a2026-10-15 21:44 \u00b7 \u53e3\u5f84\u7edf\u4e00\u7531 unified_data.json \u63d0\u4f9b\uff0c\u9875\u9762\u5185\u6240\u6709\u6570\u5b57\u4e0e\u56fe\u8868\u540c\u6e90\uff1b\u6807\u6ce8": "Data snapshot: 2026-10-15 21:44 ? conventions are provided by unified_data.json; all numbers and charts on this page share the same source; labels",
    "\u771f\u5b9e": "Real",
    "\u4e3a\u5e93/\u6587\u4ef6\u5b9e\u6d4b\uff0c": "are measured from databases/files,",
    "\u6f14\u793a": "Demo",
    "\u4e3a\u754c\u9762\u539f\u578b\u3002": "are interface prototypes."
  });
  Object.assign(EXACT, {
    "\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09 \u00b7 \u586b\u5145\uff1dTarget-Province Volume\uff08": "Shows only provinces through which the river actually flows (including shared-source provinces) ? Fill = target-province volume (",
    "\uff0c\u8d8a\u4eae\u8d8a\u9ad8\uff0c\u65ad\u70b9\u89c1\u5361\u4e0b\u8272\u6807\uff09 \u00b7 Yellow River\uff1d\u9ec4\u8272\u6d41\u52a8\u7ebf\uff08\u5e72\u6d41\u8d70\u5411\uff09": ", with brighter colors indicating higher values; breakpoints are shown in the legend below the map) ? Yellow River = yellow flow line (mainstem direction)",
    "\u00b7 \u6700\u9ad8 458 records / \u6700\u4f4e 49 records\uff08\u5206\u6bcd = Yellow RiverWeibo 899 records\uff09 \u00b7 \u5404\u56fe\u4ec5\u7ed8\u8be5\u6cb3\u6d41\u5b9e\u9645\u6d41\u7ecf\u7684\u7701\u7ea7\u884c\u653f\u533a\uff08\u542b\u5171\u6e90\u7701\uff09\uff1b\u8272\u9636\u6309Yellow River\u6570\u503c\u7b49\u9891\u5206\u7ea7\uff08\u975e\u7ebf\u6027\u62c9\u4f38\uff09 \u00b7": "? Maximum 458 records / minimum 49 records (denominator = 899 Yellow River Weibo records) ? Each map shows only provinces through which the river flows (including shared-source provinces); color levels use equal-frequency bins of Yellow River values (nonlinear stretch) ?",
    "\uff0c\u53f3\u4fa7\u300cWider view\u300d\u53ef\u9000\u56de\u542b\u6cb3\u5317 / Henan / \u5b89\u5fbd / \u6c5f\u82cf \u7684\u5927\u89c6\u91ce \u00b7 \u586b\u5145\uff1dWeiboPost mention count\uff0c\u6309": ", use the ?Wider view? button on the right to return to the broader view including Hebei / Henan / Anhui / Jiangsu ? Fill = Weibo post mention count, using",
    "\u5206\u6863\uff08\u5934\u90e8 314 \u6b21\u4e0e\u4e2a\u4f4d\u6570\u5730\u5e02\u540c\u56fe\uff0c\u7ebf\u6027\u5f52\u4e00\u4f1a\u628a\u5176\u4f59\u5730\u5e02\u5168\u538b\u5230\u6700\u6de1\u4e00\u6863\uff09 \u00b7": "bins (the top value of 314 and single-digit cities share one map; linear normalization would push all other cities into the lightest bin) ?",
    "\u9501\u5b9a\u5de6\u4e0b\u8be6\u60c5\uff08Esc \u53d6\u6d88\uff09 \u00b7 \u6eda\u8f6e / \u62d6\u62fd\u53ef\u81ea\u884c\u7f29\u653e\u3002": "to lock the lower-left details (Esc to cancel) ? Scroll / drag to zoom.",
    "\u6570\u636eSnapshot\uff1a2026-10-15 21:44 \u00b7 Definition\u7edf\u4e00\u7531 unified_data.json \u63d0\u4f9b\uff0c\u9875\u9762\u5185\u6240\u6709\u6570\u5b57\u4e0e\u56feTable\u540c\u6e90\uff1b\u6807\u6ce8": "Data snapshot: 2026-10-15 21:44 ? conventions are provided by unified_data.json; all numbers and charts on this page share the same source; labels"
  });
  Object.assign(EXACT, {
    "\u5168\u90e8": "All",
    "139 articles \u00b7 \u8fc7 30 articles\u95f8\u95e8": "139 articles ? above the 30-article gate",
    "\u540c\u4e00\u5236\u5ea6\u6846\u67b6\u3002\u9ec4\u6cb3\u6d41\u57df\u8ba8\u8bba\u8d77\u70b9\u66f4\u65e9\uff082017-01\uff09\uff0c\u9996\u8f6e\u7763\u5bdf\u4e0e\u300c\u56de\u5934\u770b\u300d\u662f\u672c\u7c07\u7684\u4e3b\u8981\u8f7d\u4f53\u3002": "Both clusters use the same institutional framework. Discussion in the Yellow River Basin begins earlier, in January 2017, and the first inspection round and its follow-up review are the main carriers of this cluster.",
    "\u547d\u4e2d\u7bc7\u6570\uff08\u53bb\u91cd\u5fae\u535a ID\uff09": "Matched articles (deduplicated Weibo IDs)",
    "\u65f6\u95f4\u8de8\u5ea6": "Time span",
    "\u4e92\u52a8\u5408\u8ba1\uff08\u8f6c+\u8bc4+\u8d5e\uff09": "Total interactions (reposts + comments + likes)",
    "\u8bcd\u4e91\u53ef\u89c1\u8bcd": "Visible cloud terms",
    "\u53c2\u8003\u7701\u4efd\uff08\u76ee\u6807\u7701\u4efd\u53e3\u5f84\uff09\uff1aShandong 21 \u00b7 Shanxi 21 \u00b7 Gansu 18 \u00b7 Inner Mongolia 17": "Reference provinces (target-province basis): Shandong 21 ? Shanxi 21 ? Gansu 18 ? Inner Mongolia 17",
    "\u8bcd\u8868\uff1aCentral Ecological Inspection / \u751f\u6001\u73af\u5883\u4fdd\u62a4\u7763\u5bdf / Inspection team / \u7763\u5bdf\u8fdb\u9a7b / Inspection \u00b7 \u5176\u4e2d 3 \u4e2a\u8bcd\u672a\u88ab\u5206\u8bcd\u5668\u5207\u51fa\uff08\u77ed\u8bed\u88ab\u5207\u788e\uff0c\u6216\u5355\u5b57\u88ab\u505c\u7528\u8bcd\u8868\u6ee4\u6389\uff09\uff0c\u56e0\u6b64\u8bcd\u4e91\u91cc\u770b\u4e0d\u5230": "Lexicon: Central Ecological Inspection / ecological environmental protection inspection / inspection team / inspection entry / inspection. Three terms were not produced by the tokenizer because phrases were split or single characters were removed by the stop-word list, so they do not appear in the cloud.",
    "\u8bed\u6599\u91cc\u6307\u540c\u4e00\u4e2a\u6cbb\u7406\u6982\u5ff5\uff0c\u88ab\u5206\u8bcd\u5207\u6210 5 \u4e2a\u8bcd\u5404\u5360\u4e00\u5e2d": "The corpus uses these expressions for the same governance concept, but tokenization splits the concept into five separate terms.",
    "\u540c\u4e00\u5236\u5ea6\u4e3b\u4f53\u7684\u5168\u79f0\u4e0e\u7b80\u79f0": "The full and abbreviated names refer to the same institutional actor.",
    "\u672c\u8bcd\u4e91\u53d6\u81ea\u9ec4\u6cb3\u6d41\u57df 899 \u6761\u5fae\u535a\u6b63\u6587\uff1a\u5206\u8bcd\u540e\u6309": "This word cloud is built from 899 Yellow River Weibo posts. After tokenization, terms are ordered by",
    "\u51fa\u73b0\u7bc7\u6570": "document frequency",
    "\u6392\u5e8f\uff08\u540c\u4e00\u7bc7\u5fae\u535a\u5185\u91cd\u590d\u51fa\u73b0\u7684\u8bcd\u53ea\u8ba1\u4e00\u6b21\uff09\uff0c\u5254\u9664\u505c\u7528\u8bcd\u3001\u5355\u5b57\u4e0e\u4e0d\u542b\u6c49\u5b57\u7684\u788e\u7247\u540e\u53d6\u5934\u90e8 105 \u8bcd\uff0c\u5b57\u53f7\u8d8a\u5927\u4ee3\u8868\u8be5\u8bcd\u51fa\u73b0\u7684\u6b63\u6587\u8d8a\u591a\u3002\u5176\u4e2d 59 \u4e2a\u5f69\u8272\u8bcd\u6309\u4eba\u5de5\u5f52\u7eb3\u7684\u4e8b\u4ef6\u7c07\u8bcd\u8868\u7740\u8272\uff0c\u70b9\u51fb\u53ef\u8054\u52a8\u4e0b\u65b9\u9762\u677f\u67e5\u770b\u91ca\u4e49\u4e0e\u539f\u6587\uff1b\u5176\u4f59 46 \u4e2a\u7070\u9636\u8bcd\u662f\u8bae\u9898\u6982\u5ff5\u8bcd\uff08\"\u751f\u6001\"\"\u73af\u4fdd\"\uff09\u3001\u653f\u6cbb\u4e3b\u4f53\u8bcd\uff08\"\u4e2d\u592e\"\uff09\u3001\u516c\u6587\u5957\u8bdd\uff08\"\u8fd1\u65e5\"\"\u5f00\u5c55\"\uff09\u4e0e\u884c\u653f\u533a\u5212\u540d\uff0c\u4ec5\u63d0\u4f9b\u8bed\u5883\u3001\u4e0d\u53c2\u4e0e\u4e8b\u4ef6\u5f52\u5c5e\u3002\u6309\u8bcd\u8868\u8ba1\uff0c\u751f\u6001\u6cbb\u7406 / \u6587\u65c5 / \u533b\u60a3\u77db\u76fe\u5206\u522b\u6709 58.8%\u300191.1%\u300183.4% \u7684\u805a\u7126\u6b63\u6587\u53ef\u5f52\u5c5e\u5230\u5177\u4f53\u4e8b\u4ef6\u7c07\uff08\u53e3\u5f84\u89c1\u300c\u4e8b\u4ef6\u76d1\u6d4b\u300d\u9875\uff09\u3002": "The same term appearing multiple times in one post is counted once. Stop words, single characters, and non-Chinese fragments are removed, and the top 105 terms are retained. Larger text indicates that a term appears in more posts. Fifty-nine coloured terms are assigned to manually defined event clusters; click a term to view its definition and source posts. The remaining 46 grey terms are broad topic concepts, political actors, official boilerplate, or administrative place names. They provide context but are not assigned to event clusters. By dictionary matching, 58.8%, 91.1%, and 83.4% of ecological-governance, cultural-tourism, and healthcare-dispute posts can be assigned to specific event clusters, respectively.",
    "\u5f69\u8272\u9ad8\u9891\u8bcd\u52fe\u52d2\u51fa\u4e09\u5927\u4e3b\u9898\u5404\u81ea\u7684\u53d9\u4e8b\u9aa8\u67b6\u3002\u751f\u6001\u6cbb\u7406\u4e00\u4fa7\uff0c\u300c\u7763\u5bdf\u300d\uff08128 \u7bc7\uff09\u3001\u300c\u7763\u5bdf\u7ec4\u300d\uff0877 \u7bc7\uff09\u3001\u300c\u6574\u6539\u300d\uff0851 \u7bc7\uff09\u4e0e\u4e3b\u4f53\u8bcd\u300c\u4e2d\u592e\u300d\uff08106 \u7bc7\uff09\u540c\u73b0\uff0c\u5bf9\u5e94\"\u7763\u5bdf\u8fdb\u9a7b\u2014\u53cd\u9988\u2014\u6574\u6539\u95ee\u8d23\"\u7684\u5b8c\u6574\u94fe\u6761\uff1b\u88ab\u5206\u8bcd\u5207\u788e\u7684\u6982\u5ff5\u5f52\u5e76\u540e\u66f4\u4e3a\u53ef\u89c2\uff1a\u300c\u7763\u5bdf / \u7763\u5bdf\u7ec4\u300d\u5408\u8ba1 139 \u7bc7\u3001\u300c\u751f\u6001 / \u73af\u4fdd\u300d\u5408\u8ba1 278 \u7bc7\uff08\u89c1\u4e0a\u65b9\u5f52\u5e76\u8868\uff09\u3002\u6587\u65c5\u4e00\u4fa7\uff0c\u300c\u5bb0\u5ba2\u300d\uff0869 \u7bc7\uff09\u3001\u300c\u666f\u533a\u300d\uff08125 \u7bc7\uff09\u3001\u300c\u6e38\u5ba2\u300d\uff0887 \u7bc7\uff09\u5206\u5c5e\u6d88\u8d39\u7ea0\u7eb7\u3001\u4f9b\u7ed9\u95e8\u7968\u3001\u4f53\u9a8c\u51fa\u884c\u4e09\u4e2a\u4e8b\u4ef6\u7c07\uff0c\u7528\u8bcd\u6700\u8d34\u8fd1\u65e5\u5e38\u6d88\u8d39\u573a\u666f\u3002\u533b\u60a3\u4e00\u4fa7\uff0c\u7070\u9636\u9ad8\u9891\u8bcd\u300c\u533b\u9662\u300d\uff0877 \u7bc7\uff09\u3001\u300c\u533b\u751f\u300d\uff080 \u7bc7\uff09\u867d\u4e0d\u5f52\u5c5e\u4e8b\u4ef6\u7c07\uff0c\u4f46\u4e0e\u5f69\u8272\u8bcd\u300c\u7ea0\u7eb7\u300d\uff0855 \u7bc7\uff09\u3001\u300c\u901a\u62a5\u300d\uff0840 \u7bc7\uff09\u3001\u300c\u624b\u672f\u300d\uff0827 \u7bc7\uff09\u3001\u300c\u5f8b\u5e08\u300d\uff0813 \u7bc7\uff09\u5171\u540c\u6784\u6210\"\u4e2a\u6848\u53d1\u751f\u2014\u5b98\u65b9\u56de\u5e94\u2014\u8d23\u4efb\u8ba4\u5b9a\u2014\u6cd5\u5f8b\u7ef4\u6743\"\u7684\u53d9\u8ff0\u94fe\u3002": "Coloured high-frequency terms outline the main narratives of the three topics. For ecological governance, inspection (128 articles), inspection team (77), rectification (51), and central (106) co-occur, corresponding to the full inspection, feedback, rectification, and accountability chain. After merging split concepts, inspection and inspection team cover 139 articles, while ecology and environmental protection cover 278. For cultural tourism, overcharging (69), scenic area (125), and visitors (87) map to consumer disputes, supply and tickets, and visitor experience. For healthcare disputes, hospital (77) and physician (0) are unassigned broad terms, while dispute (55), briefing (40), surgery (27), and lawyer (13) correspond to case occurrence, official response, liability determination, and legal redress.",
    "\u5408\u5e76\u6765\u770b\uff0c\u8bcd\u4e91\u4f20\u9012\u4e09\u5c42\u4fe1\u606f\uff1a\u4e00\u662f\u751f\u6001\u6cbb\u7406\u8ba8\u8bba\u9ad8\u5ea6\u56f4\u7ed5\u4e2d\u592e\u751f\u6001\u73af\u4fdd\u7763\u5bdf\u8fd9\u4e00\u6743\u5a01\u4e8b\u4ef6\u5c55\u5f00\uff0c\"\u7763\u5bdf\u2014\u6574\u6539\u2014\u95ee\u8d23\"\u662f\u58f0\u91cf\u4e3b\u5e72\uff1b\u4e8c\u662f\u6587\u65c5\u8bae\u9898\u7684\u8bcd\u5f62\u6700\u751f\u6d3b\u5316\uff08\u5403\u3001\u4f4f\u3001\u884c\u3001\u95e8\u7968\uff09\uff0c\u6307\u5411\u53ef\u611f\u77e5\u7684\u6d88\u8d39\u4f53\u9a8c\u73af\u8282\uff1b\u4e09\u662f\u533b\u60a3\u8ba8\u8bba\u4ee5\u5177\u4f53\u4e2a\u6848\u7684\u5904\u7406\u8fc7\u7a0b\u4e3a\u4e3b\u7ebf\uff0c\u60c5\u7eea\u5f3a\u5ea6\u6700\u9ad8\u7684\u300c\u4f24\u533b\u300d\uff083 \u7bc7\uff09\u300c\u533b\u95f9\u300d\uff087 \u7bc7\uff09\u51fa\u73b0\u9891\u6b21\u5f88\u4f4e\uff0c\u5c5e\u7ebf\u7d22\u6027\u4fe1\u53f7\u800c\u975e\u666e\u904d\u73b0\u8c61\u3002\u7070\u9636\u884c\u653f\u533a\u5212\u540d\u5c71\u4e1c\u3001\u6cb3\u5357\u3001\u9655\u897f\u3001\u5c71\u897f\u3001\u5b81\u590f\u8fdb\u5165\u4e86\u5934\u90e8\u8bcd\u8868\uff08\u5360\u672c\u6d41\u57df\u6d41\u7ecf 9 \u4e2a\u7701\u533a\u7684 5 \u4e2a\uff09\uff1b\u5185\u8499\u53e4\u3001\u56db\u5ddd\u3001\u7518\u8083\u3001\u9752\u6d77\u672a\u8fdb\u5165\uff0c\u4e0e\u5927\u91cf\u516c\u6587\u5957\u8bdd\u540c\u73b0\u8fd8\u63d0\u793a\uff1a\u76f8\u5f53\u6bd4\u4f8b\u7684\u6b63\u6587\u662f\"\u5c5e\u5730 + \u4e8b\u4ef6\"\u53e5\u5f0f\u7684\u5b98\u65b9\u6216\u5a92\u4f53\u901a\u7a3f\uff0c\u9ec4\u6cb3\u6d41\u57df\u8206\u60c5\u5448\u660e\u663e\u7684\u5c5e\u5730\u5316\u5206\u5e03\u3002": "Overall, the word cloud conveys three points. Ecological-governance discussion centres on central environmental inspection, with inspection, rectification, and accountability forming the main volume. Cultural-tourism vocabulary is the most everyday, pointing to food, accommodation, travel, and tickets. Healthcare discussion follows case handling, and the low frequency of violence-related terms indicates clue-level signals rather than prevalent phenomena. Administrative names for Shandong, Henan, Shaanxi, Shanxi, and Ningxia appear among the top terms, while Inner Mongolia, Sichuan, Gansu, and Qinghai do not. The co-occurrence of place names and official boilerplate also suggests that many posts follow an official or media release structure."
  });
  Object.assign(EXACT, {
    "\u53c2\u8003Province\uff08Target provincesDefinition\uff09\uff1aShandong 21 \u00b7 Shanxi 21 \u00b7 Gansu 18 \u00b7 Inner Mongolia 17": "Reference provinces (target-province definition): Shandong 21 ? Shanxi 21 ? Gansu 18 ? Inner Mongolia 17",
    "Vocabulary\uff1aCentral Ecological Inspection / EcologyEnvironmental protectionInspection / Inspection team / Inspection\u8fdb\u9a7b / Inspection \u00b7 \u5176\u4e2d 3 \u4e2a\u8bcd\u672a\u88ab\u5206\u8bcd\u5668\u5207\u51fa\uff08\u77ed\u8bed\u88ab\u5207\u788e\uff0c\u6216\u5355\u5b57\u88ab\u505c\u7528Vocabulary\u6ee4\u6389\uff09\uff0c\u56e0\u6b64Word Cloud\u91cc\u770b\u4e0d\u5230": "Lexicon: Central Ecological Inspection / ecological environmental protection inspection / inspection team / inspection entry / inspection. Three terms were not produced by the tokenizer because phrases were split or single characters were removed by the stop-word list, so they do not appear in the cloud.",
    "\u8bcd\u4e91\uff0c\u5171 103 \u4e2a\u8bcd\u6761\u3002\u4f7f\u7528\u5de6\u53f3\u65b9\u5411\u952e\u5728\u8bcd\u6761\u95f4\u79fb\u52a8\uff0c\u6309\u56de\u8f66\u5c55\u5f00\u8be5\u8bcd\u7684\u89e3\u91ca\uff0c\u6309 Esc \u5173\u95ed\u3002": "Word cloud with 103 terms. Use the left and right arrow keys to move between terms, press Enter to open a definition, and press Esc to close it.",
    "\u8bcd\u6761\u89e3\u91ca": "Term definition"
  });
  Object.assign(EXACT, {
    "\u300c\u751f\u6001\u300d": "\u300c\u751f\u6001\u300d (Ecology)",
    "\u300c\u7763\u5bdf\u300d": "\u300c\u7763\u5bdf\u300d (Inspection)",
    "\u300c\u5c71\u4e1c\u300d": "\u300c\u5c71\u4e1c\u300d (Shandong)",
    "\u300c\u73af\u5883\u4fdd\u62a4\u300d": "\u300c\u73af\u5883\u4fdd\u62a4\u300d (Environmental protection)",
    "\u300c\u4e2d\u592e\u300d": "\u300c\u4e2d\u592e\u300d (Central)",
    "\u300c\u73af\u4fdd\u300d": "\u300c\u73af\u4fdd\u300d (Environmental protection)",
    "\u300c\u751f\u6001\u73af\u5883\u300d": "\u300c\u751f\u6001\u73af\u5883\u300d (Ecological environment)",
    "\u300c\u7763\u5bdf\u7ec4\u300d": "\u300c\u7763\u5bdf\u7ec4\u300d (Inspection team)",
    "\u300c\u5c71\u4e1c\u7701\u300d": "\u300c\u5c71\u4e1c\u7701\u300d (Shandong Province)",
    "\u300c\u7eff\u8272\u300d": "\u300c\u7eff\u8272\u300d (Green)",
    "\u300c\u6574\u6539\u300d": "\u300c\u6574\u6539\u300d (Rectification)",
    "\u300c\u5f00\u5c55\u300d": "\u300c\u5f00\u5c55\u300d (Carry out)",
    "\u300c\u4fdd\u62a4\u300d": "\u300c\u4fdd\u62a4\u300d (Protection)",
    "\u300c\u6392\u6c61\u300d": "\u300c\u6392\u6c61\u300d (Discharge)",
    "\u300c\u975e\u6cd5\u300d": "\u300c\u975e\u6cd5\u300d (Illegal)",
    "\u300c\u533b\u9662\u300d": "\u300c\u533b\u9662\u300d (Hospitals)",
    "\u300c\u533b\u751f\u300d": "\u300c\u533b\u751f\u300d (Physicians)",
    "\u300c\u533b\u7597\u300d": "\u300c\u533b\u7597\u300d (Healthcare)",
    "\u300c\u533b\u60a3\u300d": "\u300c\u533b\u60a3\u300d (Doctor-patient)",
    "\u300c\u60a3\u8005\u300d": "\u300c\u60a3\u8005\u300d (Patients)",
    "\u300c\u7ea0\u7eb7\u300d": "\u300c\u7ea0\u7eb7\u300d (Disputes)",
    "\u300c\u624b\u672f\u300d": "\u300c\u624b\u672f\u300d (Surgery)",
    "\u300c\u6b7b\u4ea1\u300d": "\u300c\u6b7b\u4ea1\u300d (Death)",
    "\u300c\u533b\u95f9\u300d": "\u300c\u533b\u95f9\u300d (Medical disturbance)",
    "\u300c\u533b\u7597\u7ea0\u7eb7\u300d": "\u300c\u533b\u7597\u7ea0\u7eb7\u300d (Medical disputes)",
    "\u300c\u533b\u4fdd\u300d": "\u300c\u533b\u4fdd\u300d (Health insurance)",
    "\u300c\u5bb6\u5c5e\u300d": "\u300c\u5bb6\u5c5e\u300d (Family members)",
    "\u300c\u533b\u7597\u4e8b\u6545\u300d": "\u300c\u533b\u7597\u4e8b\u6545\u300d (Medical accidents)"
  });
  Object.assign(EXACT, {
    "Ecology + Ecological environment + \u73af\u4fdd + Environmental protection + \u73af\u5883": "Ecology + ecological environment + environmental protection + environmental conservation + environment",
    "\u7763\u5bdf / Inspection team": "Inspection / inspection team",
    "\u7763\u5bdf + Inspection team": "Inspection + inspection team"
  });
  const PHRASES = Object.entries(EXACT).sort((a, b) => b[0].length - a[0].length);

  function replaceKnown(value) {
    let out = String(value);
    for (const pair of PHRASES) {
      if (pair[0] && out.includes(pair[0]) && !(pair[1] && out.includes(pair[1]))) {
        out = out.split(pair[0]).join(pair[1]);
      }
    }
    return out
      .replace(/生态(?=Authors|治理|环境)/g, 'Ecological')
      .replace(/医患(?=Authors|矛盾)/g, 'Healthcare')
      .replace(/(\d+(?:\.\d+)?)\s*分/g, '$1 points')
      .replace(/(\d+)\s*位/g, '$1 authors')
      .replace(/(\d+)\s*条/g, '$1 records')
      .replace(/(\d+)\s*篇/g, '$1 articles')
      .replace(/(\d+)\s*档/g, 'Level $1')
      .replace(/第\s*(\d+)\s*档/g, 'Level $1')
      .replace(/簇\s*(\d+)/g, 'Cluster $1')
      .replace(/覆盖\s*(\d+)\s*省/g, '$1 provinces covered')
      .replace(/首现\s*(\d{4}-\d{2}-\d{2})/g, 'First seen $1')
      .replace(/(\d+)\s*条\s*\/\s*(\d+)\s*个事件/g, '$1 articles / $2 events')
      .replace(/中位\s*([\d.]+%)/g, 'Median $1')
      .replace(/赞\s*([\d,]+)/g, 'Likes $1');
  }

  function geoName(value) {
    if (value == null) return value;
    var s = String(value);
    var geo = {"山东":"Shandong","河南":"Henan","山西":"Shanxi","陕西":"Shaanxi","甘肃":"Gansu","青海":"Qinghai","宁夏":"Ningxia","内蒙古":"Inner Mongolia","四川":"Sichuan","河北":"Hebei","安徽":"Anhui","江苏":"Jiangsu","济南":"Jinan","青岛":"Qingdao","淄博":"Zibo","枣庄":"Zaozhuang","东营":"Dongying","烟台":"Yantai","潍坊":"Weifang","济宁":"Jining","泰安":"Tai\u2019an","威海":"Weihai","日照":"Rizhao","临沂":"Linyi","德州":"Dezhou","聊城":"Liaocheng","滨州":"Binzhou","菏泽":"Heze","黄河源·巴颜喀拉":"Yellow River source - Bayan Har","入海口·东营":"Estuary - Dongying","巴颜喀拉":"Bayan Har"};
    if (s === "黄河源·巴颜喀拉" || s === "Yellow River源·巴颜喀拉") return "Yellow River source - Bayan Har";
    if (geo[s]) return geo[s];
    if (/市$/.test(s) && geo[s.slice(0, -1)]) return geo[s.slice(0, -1)];
    return s;
  }

  function trText(value, key) {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (EXACT[trimmed]) return EXACT[trimmed];
    if (["name", "province", "target_province", "source"].includes(key)) {
      return geoName(trimmed);
    }
    return value;
  }

  window.BASINSCOPE_I18N = { t: trText, geo: geoName };

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

  if (isEnglish && window.U) {
    const ipMeta = window.U.ip && window.U.ip.meta
      ? JSON.parse(JSON.stringify(window.U.ip.meta)) : null;
    window.U = exactWalk(window.U);
    if (ipMeta) window.U.ip.meta = ipMeta;
  }

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

  const UI_TEXT_SELECTOR = [
    ".top", ".side", ".vtitle", ".lead", ".kpis",
    ".card > h3", ".card > .sub", ".ruler", ".toolbar", ".grp", ".seg",
    ".tblwrap th", ".main h4", ".main h5", ".main .card-title",
    ".main .text-secondary", ".main label", ".main th", ".main .input-group input",
    ".foot", ".clupanel", ".chat-tips", ".chat-send", ".qa-suggest",
    ".evh", ".evpanel", ".evgl", ".evwarn", ".evlg", ".gate", ".vcbtn",
    ".tk2", ".kick", ".tag", ".u", "button", "summary"
  ].join(",");

  function translateTextNode(node) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script,style,canvas,svg,.raw,.txt,.srcbox,.cev,.card.w2 b,#langSwitch")) return;
    // Do not rewrite source posts, comments, evidence excerpts, table cells,
    // event titles, chat messages, or any text outside the UI chrome selector.
    if (!parent.closest(UI_TEXT_SELECTOR)) return;
    const raw = node.nodeValue;
    const trimmed = raw.trim();
    if (!trimmed || !/[\u4e00-\u9fff]/.test(trimmed)) return;
    // Exact matching is intentionally used here. Substring replacement changed
    // research evidence into mixed Chinese-English fragments in earlier builds.
    const translated = EXACT[trimmed];
    if (translated && translated !== trimmed) { node.nodeValue = raw.replace(trimmed, translated); return; }
    // Dynamic UI values keep the English mode consistent without rewriting source evidence.
    const dynamic = [
      [/^\u8d5e\s*([\d,]+)$/, 'Likes $1'],
      [/^\u8bc4\s*([\d,]+)$/, 'Comments $1'],
      [/^\u8f6c\s*([\d,]+)$/, 'Reposts $1'],
      [/^\u5206\u4eab\s*([\d,]+)$/, 'Shares $1'],
      [/^\u8bc4\u8bba\s*([\d.]+)$/, 'Comments $1'],
      [/^\u5bf9\u7167\s*([\d.]+)$/, 'Reference $1'],
      [/^\u751f\u6001\u6cbb\u7406\s+(\d+)\s*\/\s*\u6587\u65c5\s+(\d+)\s*\/\s*\u533b\u60a3\u77db\u76fe\s+(\d+)$/, 'Ecological Governance $1 / Cultural Tourism $2 / Healthcare Disputes $3'],
      [/^\u751f\u6001\s+(\d+)\s*\u7bc7\s*\/\s*\u6587\u65c5\s+(\d+)\s*\u7bc7\s*\/\s*\u533b\u60a3\s+(\d+)\s*\u7bc7$/, 'Ecological Governance $1 / Cultural Tourism $2 / Healthcare Disputes $3'],
      [/^([\d.]+)%\uff08\u53ef\u5224\u5b9a\u6837\u672c\u5185\uff09$/, '$1% (classifiable sample)'],
      [/^([\d.]+)%\s*\u53ea\u53d1\s*1\s*\u6761$/, '$1% posted only once'],
      [/^\u8fde\u7eed\u94fa\u6ee1\s*(\d+)\s*\u683c$/, '$1-cell continuous matrix'],
      [/^([\d,]+)\s*\u6761\s*\u00b7\s*([\d.]+)%$/, '$1 records ? $2%'],
      [/^(\d+)\s*\u7c7b$/, '$1 categories'],
      [/^\u683c\u5185\u6761\u6570\s*([\d~]+)\s*\u6761\uff08\u914d\u989d\u5747\u8861\uff09$/, 'Cell counts $1 (quota-balanced)'],
      [/^([\d.]+)\s*\u8f6c\/\u6761\uff08\u53bb\u6781\u503c\u5747\u503c\uff09$/, '$1 reposts/post (winsorized mean)'],
      [/^([\d.]+)\s*\u5206$/, '$1 points'],
      [/^\u5bf9\u7167\u6d41\u57df\s*([\d.]+)%$/, 'Reference basin $1%'],
      [/^(\d+)\s*\u4e2a\u4e8b\u4ef6\s*\u00b7\s*\u7d2f\u8ba1\s*(\d+)\s*\u6761\s*\u00b7\s*\u8d1f\u9762\s*([\d.]+)%~([\d.]+)%$/, '$1 events ? $2 records ? Negative $3%-$4%'],
      [/^(.*)\uff08(\d+)\s*\u6761\uff09$/, '$1 ($2 records)'],
      [/^\u8de8\u5e73\u53f0\u8bc4\u8bba\u6837\u672c\u91cf\uff08\u5408\u5e76\s*([\d,]+)\s*\u6761\uff09$/, 'Cross-platform comment sample ($1 merged)'],
      [/^\u8bc4\u8bba\u6837\u672c\u91cf\s*\u00b7\s*\u6309\u8bae\u9898.*$/, 'Comment sample by topic (three topics x three platforms)']
    ];
    for (const item of dynamic) {
      if (item[0].test(trimmed)) {
        node.nodeValue = raw.replace(trimmed, trimmed.replace(item[0], item[1]));
        return;
      }
    }
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

  function switchLanguage() {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", isEnglish ? "zh" : "en");
    window.location.href = url.toString();
  }

  function addToggle() {
    const existing = document.getElementById("langSwitch");
    if (existing) {
      existing.textContent = isEnglish ? "\u4e2d\u6587" : "EN";
      existing.title = isEnglish ? "Switch to Chinese" : "Switch to English";
      existing.onclick = function (event) {
        event.preventDefault();
        switchLanguage();
      };
      return;
    }
    const tools = document.querySelector(".tools-top");
    if (!tools) return;
    const button = document.createElement("button");
    button.className = "act";
    button.id = "langSwitch";
    button.textContent = isEnglish ? "\u4e2d\u6587" : "EN";
    button.title = isEnglish ? "Switch to Chinese" : "Switch to English";
    button.onclick = switchLanguage;
    tools.prepend(button);
  }

  function applyEnglish() {
    const brand = document.querySelector(".brand");
    if (brand) {
      brand.innerHTML = "SOPRAS<small>Multi-source Public-Opinion Analytics and Risk Screening System</small>";
    }
    document.title = "SOPRAS - Multi-source Public-Opinion Analytics";
    let style = document.getElementById("en-mode-style");
    if (!style) {
      style = document.createElement("style");
      style.id = "en-mode-style";
      document.head.appendChild(style);
    }
    // Keep explanatory text visible. Reserve vertical space for it and let the
    // title/description wrap without sitting on top of the ECharts canvas.
    style.textContent = [
      ".lang-en .lead,.lang-en .note,.lang-en .card>.sub,.lang-en .ruler{display:block!important;white-space:normal!important;overflow-wrap:anywhere;word-break:break-word;line-height:1.45}",
      ".lang-en .lead{margin:0 0 12px;max-width:none}",
      ".lang-en .card{height:auto!important;min-width:0;overflow:visible}",
      ".lang-en .card>h3{padding-right:72px;line-height:1.3;overflow-wrap:anywhere;word-break:break-word;min-height:0}",
      ".lang-en .card>.sub{font-size:10.5px;margin:2px 0 7px;max-width:100%}",
      ".lang-en .ruler{font-size:10.5px;margin:6px 0 4px;max-width:100%}",
      ".lang-en .ch{flex:0 0 auto;min-width:0;min-height:180px}",
      ".lang-en .kpi{height:auto!important;min-height:94px;overflow:visible}",
      ".lang-en .kpi .k,.lang-en .kpi .s{white-space:normal!important;overflow-wrap:anywhere;line-height:1.35}",
      ".lang-en .toolbar,.lang-en .tools-top{flex-wrap:wrap;min-width:0}",
      ".lang-en .toolbar button,.lang-en .act{max-width:280px;height:auto;white-space:normal;line-height:1.3}",
      ".lang-en .tblwrap{max-width:100%;overflow:auto}",
      ".lang-en table{table-layout:auto}",
      ".lang-en th,.lang-en td{white-space:normal!important;overflow-wrap:anywhere;word-break:break-word}",
      ".lang-en .chip,.lang-en .hint{white-space:normal;overflow-wrap:anywhere}",
      ".lang-en .foot{display:block!important;white-space:normal!important;overflow-wrap:anywhere;line-height:1.5}"
    ].join("\n");
    const runPass = function () {
      translateSubtree(document.body);
      translateAttributes(document.body);
      applyEnglishFallbacks();
      applyWordCloudTermGlosses();
      keepLanguageOnInternalLinks();
    };
    runPass();
    [200, 800, 1800, 3500, 6000, 9000, 12000, 15000, 18000].forEach(function (delay) {
      window.setTimeout(runPass, delay);
    });
    document.addEventListener("click", function () {
      window.setTimeout(runPass, 120);
    });
  }

  function translateAttributes(root) {
    if (!root || root.nodeType !== Node.ELEMENT_NODE) return;
    const nodes = [root, ...root.querySelectorAll("[placeholder],[title],[aria-label]")];
    nodes.forEach(function (el) {
      ["placeholder", "title", "aria-label"].forEach(function (attr) {
        const value = el.getAttribute && el.getAttribute(attr);
        if (value && EXACT[value.trim()]) el.setAttribute(attr, EXACT[value.trim()]);
      });
    });
  }

  function keepLanguageOnInternalLinks() {
    document.querySelectorAll(".side a[href], .top a[href]").forEach(function (link) {
      if (!link.id || link.id !== "langSwitch") {
        const url = new URL(link.getAttribute("href"), window.location.href);
        if (url.origin === window.location.origin) {
          url.searchParams.set("lang", isEnglish ? "en" : "zh");
          link.setAttribute("href", url.pathname + url.search + url.hash);
        }
      }
    });
  }

  function applyWordCloudTermGlosses() {
    const termMap = {
      "\u73af\u5883\u4fdd\u62a4": "Environmental protection",
      "\u751f\u6001\u73af\u5883": "Ecological environment",
      "\u533b\u7597\u7ea0\u7eb7": "Medical disputes",
      "\u533b\u7597\u4e8b\u6545": "Medical accidents",
      "\u7763\u5bdf\u7ec4": "Inspection team",
      "\u5c71\u4e1c\u7701": "Shandong Province",
      "\u751f\u6001": "Ecology",
      "\u7763\u5bdf": "Inspection",
      "\u5c71\u4e1c": "Shandong",
      "\u4e2d\u592e": "Central",
      "\u73af\u4fdd": "Environmental protection",
      "\u7eff\u8272": "Green",
      "\u6574\u6539": "Rectification",
      "\u5f00\u5c55": "Carry out",
      "\u4fdd\u62a4": "Protection",
      "\u6392\u6c61": "Discharge",
      "\u975e\u6cd5": "Illegal",
      "\u533b\u9662": "Hospitals",
      "\u533b\u751f": "Physicians",
      "\u533b\u7597": "Healthcare",
      "\u533b\u60a3": "Doctor-patient",
      "\u60a3\u8005": "Patients",
      "\u7ea0\u7eb7": "Disputes",
      "\u624b\u672f": "Surgery",
      "\u6b7b\u4ea1": "Death",
      "\u533b\u95f9": "Medical disturbance",
      "\u533b\u4fdd": "Health insurance",
      "\u5bb6\u5c5e": "Family members"
    };
    const keys = Object.keys(termMap).sort(function (a, b) { return b.length - a.length; });
    document.querySelectorAll(".card.w2 b").forEach(function (el) {
      if (el.dataset.enGloss === "1") return;
      const raw = el.textContent || "";
      const key = keys.find(function (k) { return raw.indexOf(k) !== -1; });
      if (key) {
        el.textContent = termMap[key] + " (" + key + ")";
        el.dataset.enGloss = "1";
      }
    });
  }

  function fixEventTopicComparisonNote() {
    const target = "Warning: topics cannot be ranked as a whole by negative intensity. No topic pairs overlap completely; only event-level comparison is valid, so statements that one topic is more negative than another are not supported in this snapshot.";
    document.querySelectorAll(".tk2").forEach(function (el) {
      const text = el.textContent || "";
      if (text.indexOf("Topics cannot be ranked as a whole by negative intensity") !== -1
          || text.indexOf("negative intensity") !== -1) {
        if (text !== target) el.textContent = target;
      }
    });
  }

  function applyEnglishFallbacks() {
    const specific = [
      [".bzmap .sub", "Shows only provinces through which the river flows (including shared-source provinces). Fill represents target-province volume; the color levels are defined by equal-frequency bins."],
      [".bzmap .ruler", "Fill represents target-province volume. Colour bins are computed from the current Yellow River sample using equal-frequency bins and a nonlinear stretch."],
      [".sdcity .sub", "Shows how often each Shandong city name appears in Weibo post text. The database is province-level, so this is not a city-level collection result."],
      [".sdcity .ruler", "Switch between the province and neighboring-province views. Scroll or drag to zoom; hover or click to inspect values."],
      [".cprov", "Reference provinces (target-province definition): Shandong 21 ? Shanxi 21 ? Gansu 18 ? Inner Mongolia 17"],
      [".cnote", "Lexicon: Central Ecological Inspection / ecological environmental protection inspection / inspection team / inspection entry / inspection. Stop words and fragmented single characters can prevent some phrases from appearing in the cloud."],
      [".foot", "Data snapshot: 2026-10-15 21:44 ? Conventions are provided by unified_data.json; all numbers and charts on this page share the same source. Real = measured from databases/files; Demo = interface prototype."]
    ];
    specific.forEach(function (item) {
      document.querySelectorAll(item[0]).forEach(function (el) {
        el.textContent = item[1];
      });
    });
    document.querySelectorAll(".sub,.ruler,.note,.figsub,.fignote").forEach(function (el) {
      if (/[\u4e00-\u9fff]/.test(el.textContent || "")) {
        el.textContent = "See the methodology view for source conventions and limitations.";
      }
    });
    document.querySelectorAll(".evwarn").forEach(function (el) {
      if (/[\u4e00-\u9fff]/.test(el.textContent || "")) {
        el.textContent = "Warning: temporal concentration may reflect collection timing; verify the source records before interpretation.";
      }
    });
    fixEventTopicComparisonNote();
  }

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        translateSubtree(node);
        translateAttributes(node);
      });
      window.setTimeout(fixEventTopicComparisonNote, 0);
      window.setTimeout(fixEventTopicComparisonNote, 300);
    });
  });

  document.addEventListener("DOMContentLoaded", function () {
    addToggle();
    if (!isEnglish) return;
    applyEnglish();
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", function () {
      document.querySelectorAll(".ch").forEach(function (el) {
        if (window.echarts && echarts.getInstanceByDom(el)) echarts.getInstanceByDom(el).resize();
      });
    });
  });
})();

