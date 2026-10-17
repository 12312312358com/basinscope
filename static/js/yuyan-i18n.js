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

  const PHRASES = Object.entries(EXACT).sort((a, b) => b[0].length - a[0].length);

  function replaceKnown(value) {
    let out = String(value);
    for (const pair of PHRASES) out = out.split(pair[0]).join(pair[1]);
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
    if (["lead", "t", "s", "k", "l", "x", "name", "short", "group", "badge"].includes(key)) {
      return replaceKnown(value);
    }
    return value;
  }

  window.YUYAN_I18N = { t: trText, geo: geoName };

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
    if (!parent || parent.closest("script,style,canvas,svg,.raw,.txt,.srcbox,.foot")) return;
    const raw = node.nodeValue;
    const trimmed = raw.trim();
    if (!trimmed) return;
    /* Only translate visible interface chrome. Source posts, comments and data
       tables remain untouched so that evidence is not rewritten. */
    const isUi = !!parent.closest(".top,.side,.vtitle,.lead,.kpis,.card > h3,.card > .sub,.ruler,.toolbar,.grp,.seg,.tblwrap th,.evpanel,button");
    if (!isUi) return;
    const translated = EXACT[trimmed] || replaceKnown(trimmed);
    if (translated !== trimmed) node.nodeValue = raw.replace(trimmed, translated);
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
    button.textContent = "EN";
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

