import warnings
warnings.filterwarnings("ignore")

# 词云相关重依赖：海外 LITE 精简环境缺失时优雅降级，不影响系统启动
try:
    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    from PIL import Image
    from matplotlib import pyplot as plt
    from wordcloud import WordCloud

    _WC_AVAILABLE = True
    _WC_ERROR = ""
except Exception as _wc_err:
    _WC_AVAILABLE = False
    _WC_ERROR = str(_wc_err)
    np = matplotlib = plt = WordCloud = None


def genWordCloudPic(text, outImg):
    """
    生成纯文本词云，无模板，不缓存，只认你传进来的文字
    """
    if not _WC_AVAILABLE:
        print(f"[LITE] 词云组件不可用（{_WC_ERROR}），跳过词云生成: {outImg}")
        return None
    wc = WordCloud(
        width=1000,
        height=800,
        background_color="white",
        colormap="Blues",
        font_path="msyh.ttc",
        max_words=100,
        min_font_size=6,
        prefer_horizontal=1,
        collocations=False,
    )

    wc.generate_from_text(text)

    plt.figure(figsize=(10, 8), dpi=150)
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.savefig(f"./static/{outImg}", bbox_inches="tight", pad_inches=0)
    plt.close()
