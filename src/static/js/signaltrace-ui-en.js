(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const english = params.get("lang") !== "zh";
  if (!english) return;

  const MAP = {
    "黄河流域舆情分析系统 · 生态治理 / 文旅 / 医患矛盾": "Ecological governance, cultural tourism, and healthcare disputes",
    "黄河流域舆情": "Yellow River Public Opinion",
    "17 项": "17 views",
    "数据源": "Data source",
    "· 快照": "· Snapshot",
    "全部渲染": "Render all",
    "打印 / 导出 PDF": "Print / Export PDF",
    "单文件离线 · 零外链": "Offline single file · No external links",
    "总览": "Overview",
    "IP 属地地图": "Author-IP Map",
    "议题与词频": "Topics and Word Frequency",
    "议题专题": "Topic Profiles",
    "词频与词云": "Word Frequency and Cloud",
    "内容与评论": "Content and Comments",
    "高影响力内容": "High-Impact Content",
    "评论洞察": "Comment Insights",
    "短视频智能分析": "Short-Video Analysis",
    "评论观点聚类": "Opinion Clustering",
    "传播与扩散": "Propagation and Diffusion",
    "发布渠道与话语主体": "Speaker Classification",
    "互动结构与扩散效率": "Interaction and Diffusion",
    "关键传播节点": "Key Propagation Nodes",
    "传播趋势与节奏": "Temporal Trends",
    "事件与预警": "Events and Warning",
    "事件监测": "Event Monitoring",
    "事件传播强度": "Event-Province Intensity",
    "风险分级预警": "Risk Screening",
    "口径与方法": "Methods and Conventions",
    "说明": "Method",
    "情感模型校准": "Sentiment Calibration",
    "实时 · 本流域限定": "Live · Basin-constrained",
    "真实": "Data",
    "真实 · 三源": "Data · Three sources",
    "L2 · 真实": "L2 · Data",
    "L3 · 实测": "L3 · Measured",
    "L4 · 缺口": "L4 · Gap",
    "可归属": "Attributable",
    "未知 / 境外 / 异常": "Unknown / overseas / anomalous",
    "出现即计": "Counted on occurrence",
    "属地第一": "Top author-IP province",
    "黄河流域IP 属地地图": "Yellow River Author-IP Location Map",
    "作者 IP 属地分布": "Author-IP location distribution",
    "属地省份 Top 12": "Top 12 author-IP provinces",
    "两种地域口径对照（属地 Top 8）": "Geographic definitions compared (top 8)",
    "内容涉及省（目标省份）": "Target province",
    "作者属地（IP 归属）": "Author-IP province",
    "属地集中度（作者 IP 属地口径）": "Concentration by author IP",
    "两种口径的差（属地 − 内容涉及省）": "Definition difference (author IP − target province)",
    "作者 IP 属地完整榜（Top 20 / 共 30 个省级行政区）": "Full author-IP ranking (top 20 of 30 regions)",
    "占可归属": "Share attributable",
    "内容涉及省条数": "Target-province records",
    "差": "Difference",
    "未识别": "Unidentified",
    "热力": "Heat",
    "冰蓝": "Ice blue",
    "高对比": "High contrast",
    "黄河流域议题专题": "Yellow River Topic Profiles",
    "生态治理 · 议题速览": "Ecological Governance · Topic Profile",
    "文旅 · 议题速览": "Cultural Tourism · Topic Profile",
    "医患矛盾 · 议题速览": "Healthcare Disputes · Topic Profile",
    "生态治理 · 正文热词 Top 5": "Ecological Governance · Top 5 Post Terms",
    "文旅 · 正文热词 Top 5": "Cultural Tourism · Top 5 Post Terms",
    "医患矛盾 · 正文热词 Top 5": "Healthcare Disputes · Top 5 Post Terms",
    "生态治理 · 主要事件 Top 5": "Ecological Governance · Top 5 Events",
    "文旅 · 主要事件 Top 4": "Cultural Tourism · Top 4 Events",
    "医患矛盾 · 主要事件 Top 5": "Healthcare Disputes · Top 5 Events",
    "生态治理 · 情感构成": "Ecological Governance · Sentiment",
    "文旅 · 情感构成": "Cultural Tourism · Sentiment",
    "医患矛盾 · 情感构成": "Healthcare Disputes · Sentiment",
    "生态治理 · 话语主体构成": "Ecological Governance · Speakers",
    "文旅 · 话语主体构成": "Cultural Tourism · Speakers",
    "医患矛盾 · 话语主体构成": "Healthcare Disputes · Speakers",
    "医患矛盾 · 跨平台明细（三源交集议题）": "Healthcare Disputes · Cross-Platform Detail",
    "评论闸门": "Comment gate",
    "正文词云 · 按事件簇着色": "Post word cloud · colored by event cluster",
    "同义归并：被分词切碎的概念": "Synonym merging for split concepts",
    "生态治理 · 跨平台热词 Top 15": "Ecological Governance · Cross-Platform Top 15",
    "医患矛盾 · 跨平台热词 Top 15": "Healthcare Disputes · Cross-Platform Top 15",
    "黄河流域情感模型校准": "Yellow River Sentiment Calibration",
    "对照流域 4.6%": "Comparison basin 4.6%",
    "≥0.9 或 ≤0.1": "≥0.9 or ≤0.1",
    "已抽样列示": "Sampled examples",
    "极性子词典": "Polarity lexicon",
    "极性分十档分布": "Polarity Distribution Across Ten Bins",
    "模型判定 vs 词典法判定（结构对照 %）": "Model vs Lexicon Classification (%)",
    "判定不一致样例（真实原文，可逐条核对）": "Disagreement Examples (Source Text)",
    "正/负词命中": "Positive/Negative Term Hits",
    "正文摘要": "Post Excerpt",
    "校准路径与当前状态": "Calibration Path and Current Status",
    "极性子词典（交叉验证基准，可增删复核）": "Polarity Lexicon (Cross-Validation Baseline)",
    "黄河流域事件监测": "Yellow River Event Monitoring",
    "人工词表归纳": "Manual lexicon induction",
    "主事件面板": "Main Event Panel",
    "规模最大的事件": "Largest event",
    "负面": "Negative",
    "高负警示块": "High-Negative Alerts",
    "逐月命中对照": "Monthly Match Comparison",
    "无命中": "No matches",
    "最深": "Darkest",
    "议题对比": "Topic Comparison",
    "全量事件清单": "Full Event List",
    "黄河流域短视频智能分析": "Yellow River Short-Video Analysis",
    "L2 关键帧统计": "L2 keyframe statistics",
    "竖屏 / 横屏": "Portrait / landscape",
    "按互动总量排序": "Sorted by total engagement",
    "点击卡片查看：画面读数 · 主题与核心信息 · 传播/情感/诉求 · 推荐结论与证据链；可播放原视频（卡片墙内可滚动）": "Click a card to inspect visual indicators, topic, core message, diffusion, sentiment, appeals, recommendation, and evidence chain. The original video can be played inside the card wall.",
    "导出本专题简报（Word）": "Export topic brief (Word)",
    "服务端强制过滤，无法绕过": "Server-side scope filtering cannot be bypassed",
    "追问时可指定平台": "Platform can be specified in follow-ups",
    "传播学教材 + 论文": "Communication textbooks + research papers",
    "理论解释附引用角标": "Theory explanations include citations",
    "可以这样问": "Suggested Questions",
    "每条都对应一个真实数据工具或知识库能力": "Each prompt maps to a real data tool or knowledge-base capability",
    "黄河流域口径与方法": "Yellow River Methods and Conventions",
    "议题口径": "Topic definition",
    "生态治理 / 文旅 / 医患矛盾": "Ecological governance / cultural tourism / healthcare disputes",
    "轻量 · 待校准": "Lightweight · pending calibration",
    "数据来源与范围": "Data Sources and Scope",
    "所有图表均为实时 SQL 聚合结果": "All charts are live SQL aggregations",
    "两个已知的局限": "Two Known Limitations",
    "这两条会在正式版中用分层重抓 + 语料校准消除": "Both limitations will be addressed through stratified recollection and corpus calibration",
    "口径红线": "Definition Red Lines",
    "用于避免评审层面的口径质疑": "Prevents definitional ambiguity during review",
    "字段字典（本页每个数字出自哪个字段）": "Field Dictionary",
    "评审若要复核任何一个数字，从这张表能定位到字段与口径": "Reviewers can trace every value to its field and definition",
    "模块清单与数据就绪度（16 个模块）": "Module Inventory and Data Readiness (16 Modules)",
    "L1 已有 / L2 零采集可加（数据已在库）/ L3 需加工（有原文，需计算）/ L4 需先补数据 —— 与侧栏徽章一一对应": "L1 available / L2 addable without new collection / L3 requires processing / L4 requires more data; badges match the sidebar",
    "尚未补齐的模块与缺口（诚实清单）": "Outstanding Modules and Gaps",
    "这 6 项在页面上都以\"缺口页\"形式存在：给真实数字与补数路径，不填假数据": "These six items appear as gap views with measured values and collection paths; no placeholder data are used",
    "层级": "Level",
    "复算方法（从页面数字回到 SQL）": "Recomputation Methods",
    "所有数字都可复算：页面给出的口径与这里的 SQL 一一对应": "All values are reproducible from the definitions and SQL below",
    "闸门 30 条": "30-record threshold",
    "样本不足": "Insufficient sample",
    "因子权重": "Factor Weights",
    "负面/声量/敏感/扩散": "Negative / volume / sensitivity / diffusion",
    "四个因子加权求和；得分越高越靠前 · 灰色事件为样本不足未入级": "Weighted sum of four factors; higher scores rank first. Grey events are ungraded because of insufficient sample size.",
    "每个事件的 100 分里，各因子分别贡献了多少": "Contribution of each factor to every 0–100 event score",
    "负面占比取绝对值（一半负面本身就说明问题）；其余三项取本流域内 min-max 归一": "Negative share is used as reported; the other three factors are min–max normalized within this snapshot.",
    "未入级事件不参与 min-max 归一，避免小样本把大事件的归一值压扁": "Ungraded events are excluded from min–max normalization.",
    "分值区间与处置口径是规则设定值，评审可直接质疑权重 —— 页面已给出全部原始量": "Score ranges and actions are rule-based; all weights and underlying values are shown.",
    "本流域事件数": "Events in this basin",
    "评论": "Comments",
    "点赞": "Likes",
    "转发": "Reposts",
    "互动": "Engagement",
    "首发": "First seen",
    "三级 · 常规监测": "Level 3 · Routine monitoring",
    "纳入月度盘点，做趋势对照": "Included in monthly review and trend comparison",
    "四级 · 低风险": "Level 4 · Low risk",
    "仅存档，不单独跟踪": "Archived only; no standalone monitoring",
    "二级 · 重点关注": "Level 2 · Priority attention",
    "一级 · 立即处置": "Level 1 · Immediate action",
    "发送": "Send",
    "当前为": "Current scope",
    "专题：回答只基于本流域数据；若问另一流域会被明确拒绝。回车或点「发送」提问。": "Answers use only this basin; requests about another basin are rejected. Press Enter or click Send.",
    "提问只返回 黄河 流域的数据；若问另一流域会被明确拒绝并引导到首页对照卡。回车或点「发送」提问。": "Questions are restricted to the Yellow River snapshot. Other basins are rejected and linked to the overview comparison."
  };


  Object.assign(MAP, {
  "\u5df2\u8fc7": "Passed",
  "\u5fae\u535a / \u5c0f\u7ea2\u4e66 / \u77e5\u4e4e": "Weibo / Xiaohongshu / Zhihu",
  "Yellow River\u6d41\u57df": "Yellow River Basin",
  "\u9752": "Blue",
  "\u6a2a\u5c4f": "Landscape",
  "\u6709\u53e3\u64ad": "Voiceover",
  "\u6a59": "Orange",
  "\u7ad6\u5c4f": "Portrait",
  "\u84dd": "Blue",
  "\u7ea2": "Red",
  "\u7eff": "Green",
  "\u8d1f\u9762\u503e\u5411\u5360\u6bd4": "Negative share",
  "\u7edd\u5bf9\u5360\u6bd4 0 ~ 100%": "Absolute share 0-100%",
  "\u4e8b\u4ef6\u58f0\u91cf": "Event volume",
  "30 ~ 196 \u6761": "30-196 records",
  "\u6d89\u5b98\u65b9\u4e3b\u4f53\u654f\u611f\u5ea6": "Official-subject sensitivity",
  "\u6269\u6563\u529b": "Diffusion strength",
  "5.3 ~ 479.5 \u8f6c\u53d1/\u7bc7": "5.3-479.5 reposts/post",
  "\u4e0d\u5165\u7ea7": "Ungraded",
  "\u6837\u672c\u4e0d\u8db3 \u00b7 \u4e0d\u5165\u7ea7": "Insufficient sample - ungraded",
  "\u2265 75 \u5206": ">= 75",
  "\u2265 60 \u5206": ">= 60",
  "\u9ec4": "Yellow",
  "\u2265 45 \u5206": ">= 45",
  "< 45 \u5206": "< 45",
  "\u2460 \u6807\u6ce8\u8bed\u6599": "1. Labelled corpus",
  "\u4ece\u4e09\u4e2a\u8bae\u9898\u5404\u62bd 300 \u6761\u6b63\u6587 + 300 \u6761\u8bc4\u8bba\u4eba\u5de5\u6807\u6ce8\u4e09\u6863": "300 posts and 300 comments per topic, manually labelled into three classes",
  "\u5f85\u505a\uff08\u9700\u4eba\u5de5\u6295\u5165\uff09": "Pending (manual annotation required)",
  "\u2461 \u9886\u57df\u5fae\u8c03": "2. Domain fine-tuning",
  "\u7528\u6807\u6ce8\u8bed\u6599\u5fae\u8c03\u60c5\u611f\u5206\u7c7b\u5934\uff0c\u6216\u6362\u7528\u4e2d\u6587\u60c5\u611f\u9884\u8bad\u7ec3\u6a21\u578b": "Fine-tune the sentiment head on labelled data or use a Chinese sentiment encoder",
  "\u5f85\u505a": "Pending",
  "\u2462 \u9608\u503c\u91cd\u6807": "3. Threshold recalibration",
  "\u6309\u6807\u6ce8\u96c6\u91cd\u65b0\u6807\u5b9a 0.4 / 0.6 \u4e24\u4e2a\u5206\u6863\u9608\u503c": "Recalibrate the 0.4 and 0.6 class thresholds",
  "\u2463 \u4ea4\u53c9\u590d\u6838": "4. Cross-check",
  "\u6821\u51c6\u540e\u4e0e\u6781\u6027\u5b50\u8bcd\u5178\u6cd5\u590d\u6838\uff0c\u76ee\u6807\u4e00\u81f4\u7387 \u2265 75%": "Recheck against the polarity lexicon after calibration; target agreement >= 75%",
  "\u5f53\u524d 39.0%": "Current 39.0%",
  "\u751f\u6001 / \u73af\u4fdd": "Ecology / environmental protection",
  "\u751f\u6001 + \u751f\u6001\u73af\u5883 + \u73af\u4fdd + \u73af\u5883\u4fdd\u62a4 + \u73af\u5883": "Ecology + ecological environment + environmental protection + conservation + environment",
  "\u7763\u5bdf / \u7763\u5bdf\u7ec4": "Inspection / inspection team",
  "\u7763\u5bdf + \u7763\u5bdf\u7ec4": "Inspection + inspection team",
  "\u751f\u6001 218 \u7bc7 / \u6587\u65c5 327 \u7bc7 / \u533b\u60a3 141 \u7bc7": "Ecology 218 posts / Tourism 327 posts / Healthcare 141 posts",
  "\u89c4\u6a21\u6700\u5927\u8005\u7528\u9762\u677f\u3001\u8d1f\u9762 \u226550% \u8005\u7528\u8b66\u793a\u5757\u3001\u9010\u6708\u547d\u4e2d\u5e26\u770b\u65f6\u95f4\u5206\u5e03\u3001\u8bae\u9898\u5bf9\u6bd4\u8bf4\u6e05\u54ea\u4e9b\u8bae\u9898\u80fd\u6a2a\u5411\u6bd4": "The panel highlights the largest event; alerts mark events with at least 50% negative share; the monthly strip shows timing; the comparison explains which topics are comparable.",
  "\u89c4\u6a21 Top1 \u7528\u5927\u53f7\u9762\u677f\u800c\u975e\u5361\u7247 \u2014\u2014 \u5f62\u6001\u672c\u8eab\u8bf4\u660e\"\u8fd9\u662f\u91cd\u70b9\"": "The largest event uses a full panel rather than a standard card.",
  "\u4e0d\u53ef\u8bfb\u4f5c\u58f0\u91cf\u8d8b\u52bf": "Not a volume trend",
  "\uff08\u547d\u4e2d\u7bc7\u6570\uff09": "(matched posts)",
  "\u73b0\u72b6\u660e\u7ec6\u8868\u53ea\u7ed9\"\u9996\u8981\u7701\u4efd\"\u4e00\u4e2a\u503c\uff0c\u8bfb\u8005\u770b\u4e0d\u5230\u5206\u5e03 \u2014\u2014 \u8fd9\u662f\u672c\u9875\u4fe1\u606f\u635f\u5931\u6700\u5927\u7684\u4e00\u5904\u3002": "The summary table gives only the leading province, so province distribution must be read from the detailed table below.",
  "\u8d1f\u9762\u5360\u6bd4 \u2265 50% \u7684 4 \u4e2a\u4e8b\u4ef6 \u00b7 \u5f62\u6001\u5373\u8bed\u4e49\uff0c\u4e0d\u4e0e\u666e\u901a\u9879\u540c\u5f62": "Four events with at least 50% negative share; the alert form does not imply that they are directly comparable.",
  "\u666f\u533a\u4f9b\u7ed9\u4e0e\u95e8\u7968\u3002\u5b9d\u9e21\u300c\u514d\u8d39\u666f\u70b9\u591a\u3001\u6027\u4ef7\u6bd4\u62c9\u6ee1\u300d\u7c7b\u653b\u7565\u662f\u672c\u7c07\u9ad8\u4e92\u52a8\u5185\u5bb9\u2026": "Scenic-area supply and ticket access. High-engagement posts range from practical guides to complaints.",
  "\u8d1f\u9762\u89e6\u53d1\u70b9\u4e0e\u957f\u6c5f\u540c\u6784\u3002\u4f46\u672c\u7c07\u91cf\u7ea7\u6700\u9ad8\u7684\u4e00\u6761\u662f\u6b63\u9762\u6848\u4f8b\uff08\u6d1b\u9633 1 \u5143\u65e0\u2026": "Negative triggers resemble those in the comparison basin, although the highest-engagement post in this cluster is positive.",
  "\u751f\u6d3b\u6c61\u6c34\u76f4\u6392\u4e0e\u6392\u6c61\u53e3\u8fdd\u89c4\u3002\u4e09\u95e8\u5ce1\u4e49\u9a6c\u5e02\u300c\u5168\u56fd\u6587\u660e\u6751\u300d\u6c61\u6c34\u76f4\u6392\u662f\u672c\u7c07\u91cf\u2026": "Direct sewage discharge and irregular outfalls. The Sanmenxia case is the most visible example in this cluster.",
  "\u6bcf\u884c\u4e00\u4e2a\u4e8b\u4ef6\u3001\u6bcf\u683c\u5f53\u6708\u547d\u4e2d\u7bc7\u6570 \u2014\u2014 \u4e00\u773c\u770b\u51fa\"\u957f\u671f\u96f6\u661f\"\u4e0e\"\u96c6\u4e2d\u7206\u53d1\"\u7684\u533a\u522b": "Each row is an event and each cell is the number of matched posts in that month.",
  "\u683c\u8272 = \u5f53\u6708\u547d\u4e2d\u7bc7\u6570\uff08\u4e0e\u300c\u4e8b\u4ef6 \u00d7 \u6708\u4efd\u300d\u70ed\u529b\u56fe\u540c\u4e00\u5957 8 \u6863\u8272\u9636\uff09": "Cell color shows monthly matched posts using the same eight-bin scale as the event-month heatmap.",
  "\u4e8b\u4ef6\u540d\u540e\u7684\u5e74\u4efd =": "The year after an event name marks",
  "\u9996\u6b21\u51fa\u73b0": "first occurrence",
  "\u5e74\u4efd\u3002": "in this snapshot.",
  "\u4e0d\u53ef\u6a2a\u5411\u6bd4\u6761\u957f\u6765\u6bd4\u58f0\u91cf": "Do not compare row length as a volume measure.",
  "\uff08\u90e8\u5206\u4e8b\u4ef6\u9996\u73b0\u4e8e 2011 \u5e74\uff0c\u4f46\u672c\u6279\u6837\u672c\u53ea\u8986\u76d6\u8fd1 18 \u4e2a\u6708\uff0c\u957f\u77ed\u53cd\u6620\u7684\u662f\"\u8fd9\u6279\u6570\u636e\u91cc\u547d\u4e2d\u591a\u5c11\u4e2a\u6708\"\uff09\u3002": "Some events first appear in 2011, but the collected sample covers about 18 months; row length therefore reflects how many months in this sample contain matches.",
  "\u5148\u8bf4\u6e05\u54ea\u4e9b\u8bae\u9898\u80fd\u6a2a\u5411\u6bd4\u3001\u54ea\u4e9b\u4e0d\u80fd \u2014\u2014 \u5426\u5219\u8bfb\u8005\u4f1a\u62ff\u91cd\u53e0\u7684\u533a\u95f4\u505a\u5bf9\u6bd4": "The comparison first states which topics can be compared and which cannot.",
  "\u6761 / 5 \u4e2a\u4e8b\u4ef6": "records / 5 events",
  "Central Ecological Inspection\uff08139 \u6761\uff09": "Central Ecological Inspection (139 records)",
  "Visitor Experience and Travel\uff08196 \u6761\uff09": "Visitor Experience and Travel (196 records)",
  "Medical Disputes and Liability Determination\uff0883 \u6761\uff09": "Medical Disputes and Liability Determination (83 records)",
  "\u8bae\u9898\u4e4b\u95f4\u4e0d\u80fd\u6574\u4f53\u6bd4\u8d1f\u9762\u5f3a\u5ea6": "Topics cannot be ranked as a whole by negative intensity.",
  "\u533a\u95f4\u5927\u5e45\u91cd\u5408 \u2192 \u4e0d\u53ef\u6bd4\uff1bEcological Governance\u2194Healthcare Disputes\u3001Cultural Tourism\u2194Healthcare Disputes \u90e8\u5206\u4ea4\u53e0 \u2192 \u53ea\u80fd\u9010\u4e8b\u4ef6\u6bd4\uff0c\u4e0d\u80fd\u6bd4\u5747\u503c\u3002\u6240\u4ee5\"\u67d0\u8bae\u9898\u6bd4\u53e6\u4e00\u8bae\u9898\u66f4\u8d1f\u9762\"\u8fd9\u7c7b\u8bf4\u6cd5\uff0c": "The intervals overlap substantially. Ecological governance and healthcare disputes overlap in part, as do cultural tourism and healthcare disputes; only event-level comparison is valid.",
  "\u5728\u672c\u6279\u6570\u636e\u91cc\u4e0d\u6210\u7acb": "is not supported in this snapshot",
  "\u6309\u8bae\u9898\u5206\u7ec4\u7684\u884c\u5f0f\u6e05\u5355\uff1b\u70b9\u4efb\u4e00\u884c\u5207\u6362\u4e0b\u65b9\u91ca\u4e49\u3001\u539f\u6587\u3001\u7701\u4efd\u5206\u5e03\u4e0e\u60c5\u611f\u6784\u6210": "Event-grouped list; select a row to view its definition, source posts, province distribution, and sentiment composition.",
  "\u884c\u5f0f\u800c\u975e\u5361\u7247\uff1a14 \u884c\u8fde\u6210\u4e00\u5f20\u8868\uff0c\u626b\u8bfb\u6210\u672c\u8fdc\u4f4e\u4e8e 14 \u5f20\u72ec\u7acb\u5361\u7247\uff1b\u70b9\u4efb\u4e00\u884c\u5207\u6362\u4e0b\u65b9\u8be6\u60c5": "The table keeps all 14 events together, making scanning easier than 14 separate cards; selecting a row updates the detail panel.",
  "5 \u4e2a\u4e8b\u4ef6 \u00b7 \u7d2f\u8ba1 306 \u6761 \u00b7 \u8d1f\u9762 10%~53.6%": "5 events - 306 cumulative records - negative 10%-53.6%",
  "4 \u4e2a\u4e8b\u4ef6 \u00b7 \u7d2f\u8ba1 630 \u6761 \u00b7 \u8d1f\u9762 24.6%~65.9%": "4 events - 630 cumulative records - negative 24.6%-65.9%",
  "5 \u4e2a\u4e8b\u4ef6 \u00b7 \u7d2f\u8ba1 242 \u6761 \u00b7 \u8d1f\u9762 8.1%~26%": "5 events - 242 cumulative records - negative 8.1%-26%",
  "\u4ee3\u8868\u539f\u6587": "Representative source text",
  "\uff08\u7c07\u5185\u4e92\u52a8\u6700\u9ad8\uff0c\u5e26\u94fe\u63a5\u53ef\u56de\u6e90\u6838\u9a8c\uff09": "(highest engagement in the cluster; links permit source verification)",
  "\u547d\u4e2d\u8bcd\u8868": "Matched-term lexicon",
  "\uff08\u4eba\u5de5\u5f52\u7eb3\uff0c\u7c07\u7684\u53ec\u56de\u4f9d\u636e\uff09": "(manually induced; basis for cluster recall)",
  "\u7701\u4efd\u5206\u5e03": "Province distribution",
  "\uff08\u547d\u4e2d\u7bc7\u6570 Top6\uff09": "(top 6 by matched posts)",
  "\u9996\u7701\u5360\u6bd4": "Leading-province share",
  "\uff08\u8de8\u7701\u6269\u6563\uff09\u3002": "(cross-province diffusion)",
  "\u5df2\u5220\u9664\u300c\u8986\u76d6\u7701\u6570\u300d\u5217": "Removed the \"provinces covered\" column",
  "\u2014\u2014 \u5b9e\u6d4b\u6052\u4e3a 3~4\uff0c\u662f\u5e38\u91cf\u5217\u4e0d\u643a\u5e26\u4fe1\u606f\u3002": "It remained at 3-4 and therefore carried no information.",
  "\u4e00\u884c\u4e3a\u4e00\u4e2a\u4e8b\u4ef6\u3001\u4e00\u5217\u4e3a\u4e00\u4e2a\u6708\u7684\u547d\u4e2d\u7bc7\u6570\uff1b\u7a7a\u767d\u683c\uff1d\u8be5\u6708\u65e0\u547d\u4e2d\u3002\u4e0e\u53f0\u8d26\u5185\u7684\u300c\u9010\u6708\u547d\u4e2d\u5e26\u300d\u540c\u8272\u9636\uff0c\u6b64\u5904\u591a\u7ed9 6 \u4e2a\u6708\u7528\u4e8e\u770b\u66f4\u957f\u7684\u8de8\u5ea6": "Each row is an event and each column is a month. Blank cells indicate no matches; the color scale matches the monthly strip above.",
  "\u8d1f\u9762\u5360\u6bd4 = \u8be5\u4e8b\u4ef6\u547d\u4e2d\u5fae\u535a\u4e2d\u88ab\u5224\u8d1f\u9762\u7684\u6bd4\u4f8b\uff1b\u53e3\u5f84\u4e0e\u98ce\u9669\u5206\u7ea7\u9875\u4e00\u81f4\u3002\u300c\u9996\u8981\u7701\u4efd\u300d\u662f": "Negative share is the proportion of matched Weibo posts classified as negative. The leading province is",
  "\u9996\u4e2a\u547d\u4e2d\u7701": "the first matched province",
  "\u4e0d\u662f\u5360\u6bd4": "not a share",
  "\u2014\u2014 \u53f0\u8d26\u884c\u5f0f\u6e05\u5355\u91cc\u7684\u300c\u9996\u7701\u5360\u6bd4\u300d\u624d\u662f\u5206\u5e03\u4fe1\u606f\uff0c\u4e24\u8005\u4e0d\u53ef\u6df7\u8bfb": "The leading-province share in the event list is the distribution measure; the two should not be conflated.",
  "\u6bcf\u6761\u90fd\u5e26\u539f\u59cb\u94fe\u63a5\uff0c\u53ef\u5728\u5e93\u5916\u6838\u9a8c\u2014\u2014\u8fd9\u662f\"\u4e8b\u4ef6\"\u4e0e\"\u8bdd\u9898\u6807\u7b7e\"\u7684\u533a\u522b\u3002\u53f0\u8d26\u5185\u70b9\u4efb\u4e00\u4e8b\u4ef6\u4ea6\u53ef\u770b\u8be5\u4e8b\u4ef6\u7684 2 \u6761\u539f\u6587": "Each event links to source posts for verification outside the database. The event list also shows two representative posts per event.",
  "\u2460 \u6837\u672c\u91cf\u4e0e\u8bae\u9898\u5206\u5e03": "1. Sample volume and topic distribution",
  "\u2461 \u4e92\u52a8\u7ed3\u6784": "2. Interaction structure",
  "\u2462 \u4e8b\u4ef6\u7c07\u547d\u4e2d\u7bc7\u6570": "3. Event-cluster matched posts",
  "\uff08\u4ee5\u300c\u7763\u5bdf\u300d\u4e3a\u4f8b\uff0c\u6309\u5fae\u535a ID \u53bb\u91cd\uff09": "(example: inspection; deduplicated by Weibo ID)",
  "\u2463 \u8bdd\u8bed\u4e3b\u4f53\u5f52\u7c7b": "4. Speaker classification",
  "\uff1a\u5206\u7c7b\u5b57\u6bb5\u5bfc\u51fa\u540e\u6309": "The exported category field is rechecked against",
  "\u7684\u89c4\u5219\u8868\u590d\u5224\uff08\u89c4\u5219\u8868\u5728\u9875\u9762\u300c\u53d1\u5e03\u6e20\u9053\u4e0e\u8bdd\u8bed\u4e3b\u4f53\u300d\u9875\u5b8c\u6574\u5217\u51fa\uff09\u3002": "the rule table on the Speaker Classification page.",
  "\u2464 \u98ce\u9669\u5f97\u5206": "5. Risk score",
  "\uff1a\u6309 40/25/20/15 \u56db\u9879\u52a0\u6743\uff0c\u539f\u59cb\u91cf\u4e0e\u5f52\u4e00\u503c\u5728\u300c\u98ce\u9669\u5206\u7ea7\u9884\u8b66\u300d\u9875\u9010\u4e8b\u4ef6\u7ed9\u51fa\u3002": "Weights are 40/25/20/15 for the four factors; raw and normalized values are shown for each event on the Risk Screening page.",
  "\u8bae\u9898\u7701\u4efd\u5206\u5e03 / \u5206\u6bcd\u5c42": "Topic-province distribution / denominator",
  "\u91c7\u96c6\u914d\u989d\u6807\u8bb0\uff08\u7701\u4efd+\u4e3b\u9898\uff09\uff0c**\u4e0d\u662f\u70ed\u5ea6**": "Collection quota marker (province + topic), not a popularity measure",
  "\u91c7\u96c6\u7aef\u5173\u952e\u8bcd\u547d\u4e2d": "Collection-stage keyword match",
  "\u914d\u989d\u6807\u8bb0\uff0c**\u4e0d\u7528\u4e8e\u5185\u5bb9\u5339\u914d\u4e0e\u4e8b\u4ef6\u5224\u5b9a**": "Quota marker; not used for content matching or event assignment"
});

  Object.assign(MAP, {
  "\u6a2a\u8f74 = SnowNLP \u6781\u6027\u5206\u533a\u95f4\uff0c\u7eb5\u8f74 = \u8be5\u533a\u95f4\u7684\u5fae\u535a\u6761\u6570 \u2014\u2014 \u4e24\u7aef\u9ad8\u3001\u4e2d\u95f4\u584c = \u5224\u4e0d\u51fa\u4e2d\u6027": "Horizontal axis: SnowNLP polarity bins; vertical axis: post count. High extremes with a collapsed middle indicate weak neutral classification.",
  "\u4e24\u79cd\u65b9\u6cd5\u5404\u81ea\u7684\u4e09\u6863\u7ed3\u6784\uff1b\u5dee\u8ddd\u8d8a\u5927\u8bf4\u660e\u9886\u57df\u8bcd\u504f\u7f6e\u8d8a\u660e\u663e": "Three-class composition under the two methods. Larger gaps indicate stronger domain-term bias.",
  "\u4e24\u4e2a\u65b9\u5411\u7684\u4e0d\u4e00\u81f4\u90fd\u5217\u51fa\u6765\u4e86\uff08\u6a21\u578b\u6b63/\u8bcd\u5178\u8d1f\u3001\u6a21\u578b\u8d1f/\u8bcd\u5178\u6b63\u7b49\uff09\uff1b\u6821\u51c6\u8981\u4fee\u7684\u5c31\u662f\u8fd9\u7c7b\u6837\u672c": "Both disagreement directions are listed. Calibration targets these cases.",
  "\u5728\u6821\u51c6\u5b8c\u6210\u524d\uff0c\u9875\u9762\u6240\u6709\u60c5\u611f\u7ed3\u8bba\u53ea\u4f5c\u7ed3\u6784\u53c2\u8003\u3001\u4e0d\u505a\u6781\u6027\u5916\u63a8": "Before calibration, sentiment results are structural references only and are not extrapolated as polarities.",
  "\u8bcd\u5178\u6cd5\u4e0d\u662f\u66ff\u4ee3\u6a21\u578b\uff0c\u53ea\u662f\u7ed9\"\u6a21\u578b\u504f\u7f6e\"\u63d0\u4f9b\u4e00\u4e2a\u53ef\u590d\u6838\u7684\u53c2\u7167": "The lexicon is not a replacement model; it provides an auditable reference for model bias.",
  "\u6e38\u5ba2\u7aef\u4f53\u9a8c\u3002\u8349\u539f\u65c5\u6e38\u653b\u7565\u3001\u897f\u5b89\u300c58 \u5143\u5927\u767d\u83dc\u6c64\u300d\u5206\u522b\u4ee3\u8868\u6b63\u9762\u4e0e\u8d1f\u9762\u4e24\u7aef\u3002": "Visitor experience: travel guides and complaints represent the positive and negative ends of this event cluster.",
  "\u26a0 \u6708\u5ea6\u5206\u5e03\u53ea\u8bfb\"\u4f55\u65f6\u5b58\u5728\"\uff0c": "Monthly distribution shows when records exist, not a volume trend. About 63% of this basin sample is concentrated in 2026 because collection was concentrated there.",
  "\u539f\u6587": "Source",
  "Yellow River\u6d41\u57df": "Yellow River Basin"
});

  Object.assign(MAP, {
  "\uff1a\u672c\u6d41\u57df\u6837\u672c 63% \u96c6\u4e2d\u5728 2026 \u5e74\uff0c\u53f3\u4fa7\u5bc6\u96c6\u662f\u91c7\u96c6\u96c6\u4e2d\u9020\u6210\u7684\u3002": "About 63% of this basin sample is concentrated in 2026; the dense right-hand side reflects collection timing, not a volume trend."
});

  let DYNAMIC = [
    [/^推荐度\s*([\d.]+)$/u, "Recommendation $1"],
    [/^首发\s*(\d{4}-\d{2}-\d{2})$/u, "First seen $1"],
    [/^(\d+)\s*篇\s*(\d+)\.$/u, "$1 posts $2."],
    [/^评论\s*([\d,]+)$/u, "Comments $1"],
    [/^点赞\s*([\d,]+)$/u, "Likes $1"],
    [/^转发\s*([\d,]+)$/u, "Reposts $1"],
    [/^互动\s*([\d,]+)$/u, "Engagement $1"],
    [/^(\d[\d,.]*)\s*个$/u, "$1"],
    [/^(\d[\d,.]*)\s*条$/u, "$1 records"],
    [/^(\d[\d,.]*)\s*篇$/u, "$1 posts"],
    [/^(\d[\d,.]*)\s*篇\s*·\s*过\s*(\d[\d,.]*)\s*篇闸门$/u, "$1 posts · meets the $2-post threshold"],
    [/^含事件词\s*(\d+)\s*个$/u, "$1 event-linked terms"],
    [/^生态\s*(\d+)\s*\/\s*文旅\s*(\d+)\s*\/\s*医患\s*(\d+)\s*篇被覆盖$/u, "Coverage: Ecology $1 / Tourism $2 / Healthcare $3 posts"],
    [/^未识别\s*([\d.]+%)$/u, "Unidentified $1"],
    [/^覆盖\s*(\d+)\s*省$/u, "$1 provinces covered"],
    [/^首现\s*(\d{4}-\d{2}-\d{2})$/u, "First seen $1"],
    [/^命\s*(\d[\d,]*)\s*条$/u, "$1 matches"],
    [/^负面\s*·\s*(\d[\d,]*)\s*条$/u, "Negative · $1 records"],
    [/^中位\s*([\d.]+%)$/u, "Median $1"],
    [/^([\d,]+)\s*条\s*·\s*过闸门$/u, "$1 records · above threshold"],
    [/^([\d,]+)\s*条\s*\/\s*(\d+)\s*个事件$/u, "$1 records / $2 events"],
    [/^([\d,]+)\s*条\s*\/\s*(\d+)\s*个事件\s*·\s*负面\s*([\d.%~-]+)$/u, "$1 records / $2 events · negative $3"],
    [/^生态治理\s*(\d+)\s*篇\s*\/\s*文旅\s*(\d+)\s*篇\s*\/\s*医患\s*(\d+)\s*篇$/u, "Ecology $1 / Tourism $2 / Healthcare $3 posts"],
    [/^(\d+)\s*文旅$/u, "$1 tourism events"],
    [/^(\d+)\s*生态\s*\/\s*(\d+)\s*医患$/u, "$1 ecology / $2 healthcare events"]
  ];

  function tr(value) {
    if (value == null) return value;
    const raw = String(value);
    const key = raw.trim();
    if (MAP[key]) return MAP[key];
    let out = key;
    for (const pair of DYNAMIC) out = out.replace(pair[0], pair[1]);
    out = out.replace(/\u4e92\u52a8\s*([\d,]+)\uff08\u8f6c\s*([\d,]+)\s*\/\s*\u8d5e\s*([\d,]+)\uff09/u, 'Engagement $1 (reposts $2 / likes $3)');
    return out;
  }

  function hasChinese(value) {
    return /[\u3400-\u9fff]/u.test(value || "");
  }

  function translateTextNodes(root) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent || parent.closest("script,style,canvas,svg,option,.raw,.txt,.srcbox,.cev,.chat-bubble")) continue;
      const raw = node.nodeValue;
      const text = (raw || "").trim();
      if (!text || !hasChinese(text)) continue;
      const translated = tr(text);
      if (translated !== text) node.nodeValue = raw.replace(text, translated);
    }
  }

  function translateAttributes() {
    document.querySelectorAll("[title],[aria-label],[placeholder]").forEach(function (el) {
      ["title", "aria-label", "placeholder"].forEach(function (attr) {
        const value = el.getAttribute(attr);
        if (!value || !hasChinese(value)) return;
        const translated = tr(value);
        if (translated !== value) el.setAttribute(attr, translated);
      });
    });
  }

  function setProfile(card, title, body) {
    if (!card || card.dataset.enProfile === "1") return;
    const sub = card.querySelector(":scope > .sub");
    const detail = card.querySelector(":scope > div:not(.sub)");
    const h3 = card.querySelector(":scope > h3");
    if (h3) h3.textContent = title;
    if (sub) sub.textContent = "At a glance";
    if (detail) detail.innerHTML = body;
    card.dataset.enProfile = "1";
  }

  function applyTopicProfiles() {
    document.querySelectorAll(".card.w1").forEach(function (card) {
      const heading = card.querySelector("h3")?.textContent || "";
      if (heading.includes("Ecological Governance")) {
        setProfile(card, "Ecological Governance ? Topic Profile",
          '<div style="line-height:1.75"><b>Focus</b>: governance actors and outcomes.<br><b>Background</b>: water-pollution control, central ecological inspections, rectification, restoration, and fishing bans across Weibo, Xiaohongshu, and Zhihu.<br><b>Key points</b><br>? <b>Sample</b>: 371 records (231 unique authors); representative terms are ecology, inspection, and environmental protection.<br>? <b>Leading event</b>: Central Ecological Inspection (139 records; 37.5%).<br>? <b>Sentiment</b>: positive share is highest (62.5%).<br>? <b>Speakers</b>: official accounts predominate (52.8%), reflecting announcements and rectification updates.</div>');
      } else if (heading.includes("Cultural Tourism")) {
        setProfile(card, "Cultural Tourism ? Topic Profile",
          '<div style="line-height:1.75"><b>Focus</b>: visitor experience and service complaints.<br><b>Background</b>: scenic-area visits, travel spending, overcharging and consumer disputes, ticket supply, and cultural-tourism integration. This topic comes from Weibo only in the current snapshot.<br><b>Key points</b><br>? <b>Sample</b>: 359 records (323 unique authors); representative terms are Shandong, scenic area, and tourism.<br>? <b>Leading event</b>: Visitor Experience and Travel (196 records; 54.6%).<br>? <b>Sentiment</b>: positive share is highest (59.6%).<br>? <b>Speakers</b>: individual accounts predominate (45.5%), mainly travel notes, guides, and complaints.</div>');
      } else if (heading.includes("Healthcare Disputes")) {
        setProfile(card, "Healthcare Disputes ? Topic Profile",
          '<div style="line-height:1.75"><b>Focus</b>: dispute emergence and responsibility attribution.<br><b>Background</b>: medical disputes, accountability, treatment and surgical risk, legal remedies, and healthcare-related incidents.<br><b>Key points</b><br>? <b>Sample</b>: 169 records (160 unique authors); representative terms are hospital, doctor-patient, and dispute.<br>? <b>Leading event</b>: Medical Disputes and Liability Determination (83 records; 49.1%).<br>? <b>Sentiment</b>: positive share is highest (73.4%).<br>? <b>Speakers</b>: individual accounts predominate (43.2%), mainly patient and public narratives.</div>');
      }
    });
  }

  function applyWordCloudNotes() {
    document.querySelectorAll(".card").forEach(function (card) {
      const heading = card.querySelector("h3")?.textContent || "";
      if (!heading.includes("word cloud") && !heading.includes("Word-Cloud")) return;
      const paragraphs = card.querySelectorAll("p");
      if (!paragraphs.length) return;
      const texts = [
        "The word cloud uses 899 Yellow River Weibo posts. After tokenization and removal of stop words, single characters, and non-Chinese fragments, it shows the 105 most frequent terms. Size reflects the number of posts containing a term; repeated mentions in one post are counted once. Colored terms map to event clusters, while grey terms provide topic, institutional, official-language, or geographic context.",
        "Ecology is organized around inspection, feedback, and rectification. Cultural tourism centers on visitor experience, ticket supply, and consumer disputes. Healthcare discussion follows individual cases and accountability; violence-related terms are rare and indicate isolated signals rather than a prevalent pattern.",
        "Coverage figures describe assignment to event clusters within the collected snapshot. They are not population estimates, and grey terms are not treated as event evidence."
      ];
      paragraphs.forEach(function (element, index) {
        if (texts[index]) element.textContent = texts[index];
      });
    });
  }

  function applyQa() {
    const exact = {
      "\u4f60\u597d\uff0c\u6211\u662f": "Hello, I am ",
      "SOPRAS\u667a\u80fd\u95ee\u7b54": "SOPRAS QA",
      "\u3002\u5f53\u524d\u4e13\u9898\u4e3a": ". Current scope: ",
      "\uff0c\u6211\u53ea\u8bfb\u53d6\u672c\u6d41\u57df\u7684\u6570\u636e\u3002": ". I use only data from this basin.",
      "\u00b7 Yellow River\u6d41\u57df\u6700\u8fd1\u6709\u54ea\u4e9b\u70ed\u70b9\u4e8b\u4ef6\uff1f": "\u00b7 What are the recent high-interest events?",
      "\u00b7 \u672c\u6d41\u57df\u58f0\u91cf\u6700\u9ad8\u7684\u7701\u4efd\u662f\u54ea\u4e2a\uff1f": "\u00b7 Which province has the highest volume?",
      "\u00b7 \u8fd9\u7c7b\u4e8b\u4ef6\u4e3a\u4ec0\u4e48\u5bb9\u6613\u5728\u7f51\u7edc\u4e0a\u5feb\u901f\u53d1\u9175\uff1f": "\u00b7 Why do such events spread quickly online?"
    };
    document.querySelectorAll(".chat-bubble").forEach(function (bubble) {
      const walker=document.createTreeWalker(bubble,NodeFilter.SHOW_TEXT);
      let node;
      while(node=walker.nextNode()){
        const text=(node.nodeValue||"").trim();
        if(exact[text]) node.nodeValue=(node.nodeValue||"").replace(text,exact[text]);
      }
    });
    const prompts=[
      "What are the recent high-interest events?",
      "Which province has the highest volume?",
      "How many Xiaohongshu discussions concern this basin?",
      "Why do such events spread quickly online?"
    ];
    document.querySelectorAll(".card").forEach(function(card){
      const h=card.querySelector("h3")?.textContent||"";
      if(!h.includes("Suggested Questions")) return;
      card.querySelectorAll(".t").forEach(function(el,index){
        if(prompts[index]) el.textContent=prompts[index];
      });
    });
  }

  function applyGeoTable() {
    const geo = {
      "北京": "Beijing", "天津": "Tianjin", "上海": "Shanghai", "重庆": "Chongqing",
      "河北": "Hebei", "山西": "Shanxi", "辽宁": "Liaoning", "吉林": "Jilin", "黑龙江": "Heilongjiang",
      "江苏": "Jiangsu", "浙江": "Zhejiang", "安徽": "Anhui", "福建": "Fujian", "江西": "Jiangxi",
      "山东": "Shandong", "河南": "Henan", "湖北": "Hubei", "湖南": "Hunan", "广东": "Guangdong",
      "海南": "Hainan", "四川": "Sichuan", "贵州": "Guizhou", "云南": "Yunnan", "陕西": "Shaanxi",
      "甘肃": "Gansu", "青海": "Qinghai", "内蒙古": "Inner Mongolia", "广西": "Guangxi",
      "西藏": "Tibet", "宁夏": "Ningxia", "新疆": "Xinjiang"
    };
    document.querySelectorAll("td,th").forEach(function (cell) {
      const key = (cell.textContent || "").trim();
      if (geo[key]) cell.textContent = geo[key];
    });
  }

  function applyMethodTables() {
    const rows = {
      "微博内容": ["Post text", "t_basin_article", "Frequency / event clusters / sentiment / lexicon", "Stop words and single characters are removed before tokenization; repeated terms in one post are counted once."],
      "发布时间": ["Publish time", "t_basin_article", "Year / month / year-month matrix", "Parsed from a text field; the final month is incomplete."],
      "点赞数 / 评论数 / 转发数": ["Likes / comments / reposts", "t_basin_article", "Interaction structure / diffusion", "Integer aggregation; missing values are 0; not aligned with Douyin totals."],
      "分类": ["Category", "t_basin_article", "Speaker classification", "Mixed field classified with a controlled vocabulary; unknown values remain labelled."],
      "作者ID / 作者昵称": ["Author ID / display name", "t_basin_article", "Key nodes / first recorded author", "De-identified before storage; only edge characters are retained."],
      "发布地区": ["Author region", "t_basin_article", "Author-IP location map", "Author-IP definition; more than 40% missing in measurement and explicitly labelled."],
      "评论内容 / 评论时间": ["Comment text / time", "t_basin_comment", "Comment insights / time periods", "Only 59 comments are available; threshold status is labelled."],
      "性别": ["Gender", "t_basin_comment", "Comment gender composition", "Normalized m/f values; unknown is a separate category."],
      "流域总览": ["Basin overview", "Overview", "L1", "Retained", "All t_basin_article fields"],
      "Author-IP Location Map": ["Author-IP Map", "Overview", "L1", "Retained", "Published region (author IP)"],
      "Temporal Trends": ["Temporal Trends", "Propagation and Diffusion", "L2", "Added", "Publish time (81/87 monthly points)"],
      "Topic Profiles": ["Topic Profiles", "Topics and Word Frequency", "L1", "Retained + expanded", "Topic × term × province × sentiment"],
      "Word Frequency and Word Cloud": ["Word Frequency and Cloud", "Topics and Word Frequency", "L1", "Batch 1 revised", "Post tokens + event-cluster lexicon"],
      "High-Impact Content": ["High-Impact Content", "Content and Comments", "L1", "Retained + expanded", "Likes / comments / reposts"],
      "Comment Insights": ["Comment Insights", "Content and Comments", "L1", "Retained + expanded", "t_basin_comment (36 / 19 records)"],
      "Opinion Clustering": ["Opinion Clustering", "Content and Comments", "L3", "Implemented (three-source merge)", "Weibo comments were insufficient; three-source comments were clustered, with cluster-exclusive terms used as labels."],
      "Speaker Classification": ["Speaker Classification", "Propagation and Diffusion", "L2", "Restored", "Category field (mixed; controlled classification required)"],
      "Interaction and Diffusion": ["Interaction and Diffusion", "Propagation and Diffusion", "L2", "Restored", "Reposts / comments / likes"],
      "Key Propagation Nodes": ["Key Propagation Nodes", "Propagation and Diffusion", "L3", "Restored", "Author ID/name + three interaction metrics"],
      "Event Monitoring": ["Event Monitoring", "Events and Warning", "L3", "Restored (event clusters)", "Event-cluster lexicon + post matches"],
      "Event-Province Propagation Intensity": ["Event-Province Intensity", "Events and Warning", "L3", "Added 2026-10-02", "Matched keyword → event type × province matrix + winsorized repost mean"],
      "Risk Screening": ["Risk Screening", "Events and Warning", "L3", "Restored (rule-based)", "Event cluster × sentiment × interaction"],
      "Methodology and Data Conventions": ["Methods and Conventions", "Methods", "L1", "Retained + expanded", "Site-wide definitions + gap list"],
      "Sentiment Model Calibration": ["Sentiment Calibration", "Methods", "L4", "Restored (calibration view)", "SnowNLP measurement bias + lexicon cross-check"]
    };
    document.querySelectorAll("tr").forEach(function (row) {
      const cells = row.querySelectorAll("th,td");
      if (!cells.length) return;
      const key = (cells[0].textContent || "").trim();
      if (!rows[key]) return;
      rows[key].forEach(function (value, index) {
        if (cells[index]) cells[index].textContent = value;
      });
    });
  }

  function applyFooter() {
    document.querySelectorAll(".foot").forEach(function (el) {
      const text = el.textContent || "";
      if (!hasChinese(text)) return;
      const match = text.match(/数据快照：([^·]+)/);
      el.textContent = "Data snapshot: " + (match ? match[1].trim() : "current snapshot") +
        " · Definitions are supplied by unified_data.json. All figures and charts use the same source. Labels: " +
        "Real = measured from databases/files; Demo = interface prototype.";
    });
  }

  function applyMethodNarratives() {
    document.querySelectorAll(".card").forEach(function (card) {
      const h3=card.querySelector("h3"); const heading=h3?.textContent||"";
      if(heading.includes("Data Sources and Scope")){
        const body=card.querySelector(":scope > div:not(.sub)");
        if(body) body.innerHTML='<div style="line-height:1.85"><b>Tables</b>: t_basin_article (899 records) and t_basin_comment (59 records).<br><b>Filter</b>: basin = Yellow River; topic ? {ecological governance, cultural tourism, healthcare disputes}.<br><b>Geography</b>: post text uses the target province assigned during collection; comments use the author-IP province.<br><b>De-identification</b>: display names, user IDs, and profile links are processed before storage.</div>';
      }
      if(heading.includes("Two Known Limitations")){
        const body=card.querySelector(":scope > div:not(.sub)");
        if(body) body.innerHTML='<div style="line-height:1.85"><p><b>Comment coverage</b>: the Weibo comment table has 59 records and no cultural-tourism comments; it supports distribution descriptions only, not trend extrapolation.</p><p><b>Model calibration</b>: SnowNLP is a general-purpose model and treats many domain terms as extremes (negative 33.0%; neutral 3.6%). Its positive-negative ratio is structural context, not a validated attitude measure.</p></div>';
      }
      if(heading.includes("Definition Red Lines")){
        const body=card.querySelector(":scope > div:not(.sub)");
        if(body) body.innerHTML='<div style="line-height:1.85"><p>? <b>Cross-platform</b>: likes, comments, and reposts use different platform mechanics, so only structural shares are compared.</p><p>? <b>Geography</b>: target province, content location, and author-IP location are reported separately and are never pooled.</p><p>? <b>Shared-source provinces</b>: Qinghai and Sichuan belong to both the Yangtze and Yellow River basins and carry dual basin labels from collection onward.</p></div>';
      }
      if(heading.includes("Recomputation Methods")){
        const sub=card.querySelector(":scope > .sub");
        if(sub) sub.textContent="All values can be recomputed from the definitions and the SQL patterns below";
      }
    });
  }

  function localizeChartLabels() {
    if (!window.echarts) return;
    const labels = {
      "\u8d1f\u9762\u5360\u6bd4 40": "Negative share 40",
      "\u58f0\u91cf 25": "Volume 25",
      "\u654f\u611f\u5ea6 20": "Sensitivity 20",
      "\u6269\u6563 15": "Diffusion 15"
    };
    document.querySelectorAll(".ch").forEach(function (el) {
      const chart = echarts.getInstanceByDom(el);
      if (!chart || chart.__signalTraceLabelsLocalized) return;
      const option = chart.getOption();
      const series = option.series || [];
      const legends = option.legend || [];
      const needsUpdate = series.some(function (item) { return labels[item.name]; }) ||
        legends.some(function (item) { return (item.data || []).some(function (name) { return labels[name]; }); });
      if (!needsUpdate) return;
      chart.setOption({
        legend: legends.map(function (item) {
          return {
            data: (item.data || []).map(function (name) { return labels[name] || name; })
          };
        }),
        series: series.map(function (item) {
          return { name: labels[item.name] || item.name };
        })
      });
      chart.__signalTraceLabelsLocalized = true;
    });
  }

  function resizeCharts() {
    if (!window.echarts) return;
    document.querySelectorAll(".ch").forEach(function (el) {
      const chart = echarts.getInstanceByDom(el);
      if (chart) chart.resize();
    });
  }

  function run() {
    document.documentElement.lang = "en";
    document.body.classList.add("lang-en");
    if (window.BASINSCOPE_EN_MODE === false) return;
    translateTextNodes(document.body);
    translateAttributes();
    applyTopicProfiles();
    applyWordCloudNotes();
    applyQa();
    applyGeoTable();
    applyMethodTables();
    applyMethodNarratives();
    applyFooter();
    resizeCharts();
    localizeChartLabels();
  }

  function boot() {
    run();
    [250, 800, 1800, 3500, 6000, 10000].forEach(function (ms) {
      window.setTimeout(run, ms);
    });
    const observer = new MutationObserver(function () { window.setTimeout(run, 30); });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
