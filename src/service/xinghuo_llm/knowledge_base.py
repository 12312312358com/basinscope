from typing import List, Dict, Optional

class SubjectKnowledgeBase:
    THEORIES = {
        "1": {"id": "1", "name": "议程设置", "zh_name": "议程设置理论",
              "author": "McCombs & Shaw", "year": 1972,
              "desc": "媒体通过报道重点影响公众对议题重要性的认知。媒体不仅告诉人们『想什么』，也成功告诉人们『怎么想』。",
              "keywords": ["显著性", "议题", "排序", "媒体议程", "公众议程"]},
        "2": {"id": "2", "name": "沉默的螺旋", "zh_name": "沉默的螺旋理论",
              "author": "Noelle-Neumann", "year": 1974,
              "desc": "个体因恐惧孤立而倾向于附和主流意见，导致异见沉默，形成『螺旋』效应。",
              "keywords": ["孤立恐惧", "准统计感官", "意见气候", "沉默", "强势意见"]},
        "3": {"id": "3", "name": "使用与满足", "zh_name": "使用与满足理论",
              "author": "Blumler & Katz", "year": 1974,
              "desc": "受众主动选择媒介以满足自身需求，强调受众的能动性。",
              "keywords": ["需求", "动机", "选择性接触", "满足", "主动性"]},
        "4": {"id": "4", "name": "框架理论", "zh_name": "框架理论",
              "author": "Goffman", "year": 1974,
              "desc": "媒体通过选择与突出来建构议题的解读视角，影响受众对事件的理解。",
              "keywords": ["框架", "选择", "突出", "解读", "建构"]},
        "5": {"id": "5", "name": "群体极化", "zh_name": "群体极化理论",
              "author": "Sunstein", "year": 2002,
              "desc": "同质化群体讨论后观点趋向极端化，回音室效应加剧这一过程。",
              "keywords": ["极化", "极端化", "回音室", "同质化", "讨论"]},
        "6": {"id": "6", "name": "培养理论", "zh_name": "培养理论",
              "author": "Gerbner", "year": 1976,
              "desc": "长期媒介接触塑造受众对现实世界的认知，尤其是暴力与犯罪认知。",
              "keywords": ["涵化", "媒介暴力", "主流化", "共振", "长期效果"]},
        "7": {"id": "7", "name": "创新扩散", "zh_name": "创新扩散理论",
              "author": "Rogers", "year": 1962,
              "desc": "新事物通过社会系统传播的过程，包括知晓、说服、决策、实施、确认阶段。",
              "keywords": ["创新", "扩散", "采纳者", "S形曲线", "早期采纳者"]},
        "8": {"id": "8", "name": "知沟理论", "zh_name": "知沟理论",
              "author": "Tichenor et al.", "year": 1970,
              "desc": "社会经济地位较高者比低者更快获取大众媒介信息，导致知识差距扩大。",
              "keywords": ["知沟", "知识差距", "社会经济", "信息获取"]},
        "9": {"id": "9", "name": "数字鸿沟", "zh_name": "数字鸿沟",
              "author": "NTIA", "year": 1999,
              "desc": "不同群体在信息通信技术获取、使用和素养上的差距。",
              "keywords": ["数字鸿沟", "接入", "素养", "技术差距"]},
        "10": {"id": "10", "name": "第三人效果", "zh_name": "第三人效果",
               "author": "Davison", "year": 1983,
               "desc": "人们倾向于认为媒介信息对他人的影响大于对自己的影响。",
               "keywords": ["第三人", "高估", "影响", "自我"]},
        "11": {"id": "11", "name": "媒介依赖", "zh_name": "媒介依赖理论",
               "author": "Ball-Rokeach & DeFleur", "year": 1976,
               "desc": "社会越复杂，个人越依赖媒介来获取信息。",
               "keywords": ["依赖", "媒介", "信息获取", "复杂社会"]},
        "12": {"id": "12", "name": "把关人", "zh_name": "把关人理论",
               "author": "White", "year": 1950,
               "desc": "媒介组织通过对信息筛选、过滤来设置公众议程。",
               "keywords": ["把关", "筛选", "过滤", "议程"]},
        "13": {"id": "13", "name": "两级传播", "zh_name": "两级传播",
               "author": "Lazarsfeld et al.", "year": 1944,
               "desc": "信息从大众媒介经由意见领袖再流向普通受众。",
               "keywords": ["两级传播", "意见领袖", "流向", "大众媒介"]},
        "14": {"id": "14", "name": "涵化分析", "zh_name": "涵化分析",
               "author": "Gerbner", "year": 1976,
               "desc": "长期电视接触使受众对现实社会的认知与电视呈现趋同，产生主流化效果。",
               "keywords": ["涵化", "主流化", "认知", "电视"]},
        "15": {"id": "15", "name": "选择性接触", "zh_name": "选择性接触",
               "author": "Hyman & Sheatsley", "year": 1947,
               "desc": "个体倾向于接触与自身观点一致的信息，避免对立信息。",
               "keywords": ["选择性", "一致", "避免", "对立"]}
    }

    CASES = {
        "算法推荐": "算法推荐系统根据用户历史行为推送内容，可能导致信息茧房和回音室效应。典型如抖音/头条的算法逻辑。",
        "舆论反转": "舆情事件中，起初一种声音占主导，后因新证据出现舆论急剧转变，如『重庆公交坠江』事件。",
        "直播带货": "直播电商利用意见领袖效应和实时互动促进销售，典型如李佳琦、薇娅案例，涉及使用与满足理论。",
        "沉默螺旋": "网络热搜话题中，持异见用户因评论区一边倒的声浪而选择沉默，典型案例如各类社会热点事件中的舆论场。",
        "信息茧房": "算法推荐使用户长期接触同质化信息，典型案例如今日头条、抖音的个性化推荐机制。"
    }

    METHODS = {
        "内容分析": "对文本内容进行系统、客观、定量的描述性研究。步骤：确定研究问题→抽取样本→编码→统计分析。",
        "问卷调查": "通过标准化问卷收集大量样本数据，适用于态度、行为测量。注意信度效度。",
        "深度访谈": "半结构化的一对一访谈，获取深层次认知和体验，适用于探索性研究。"
    }

    @classmethod
    def search_theory(cls, keyword: str) -> List[Dict]:
        results = []
        kw = keyword.lower()
        for t in cls.THEORIES.values():
            if (kw in t["name"].lower() or kw in t["zh_name"] or
                    any(kw in k.lower() for k in t["keywords"])):
                results.append(t)
        return results

    @classmethod
    def get_theory_by_id(cls, tid: str) -> Optional[Dict]:
        return cls.THEORIES.get(tid)

    @classmethod
    def reference_format(cls, theory_id: str) -> str:
        t = cls.get_theory_by_id(theory_id)
        if not t:
            return ""
        return f"{t['author']} ({t['year']}), {t['zh_name']}, 载于《新闻传播学核心理论》."