# -*- coding: utf-8 -*-
"""把一条视频抽到的关键帧拼成一张「接触印相」(contact sheet) 单图，供人工快速看图。

用途：Step 7「值不值验证」需要人**眼**看画面 → 单图比 20 张散图更好过目。
原始视频仍不落盘：帧已在内存（fetch 阶段），本模块只把**内存里的 JPEG 帧**拼成一张新图。
"""
import io

from PIL import Image, ImageDraw


def make_sheet(frames, out_path, cols=4, cell_w=240, max_frames=12,
               title=None, label=True):
    """frames: [(pts, jpeg_bytes), ...]；返回 out_path，若无可解码帧返回 None。"""
    imgs = []
    for pts, b in frames[:max_frames]:
        try:
            im = Image.open(io.BytesIO(b)).convert('RGB')
        except Exception:
            continue
        im.thumbnail((cell_w, cell_w * 3))
        imgs.append((pts, im))
    if not imgs:
        return None

    cell_h = max(im.height for _, im in imgs)
    n = len(imgs)
    rows = (n + cols - 1) // cols
    pad = 4
    lab_h = 14 if label else 0
    top = 22 if title else pad
    W = cols * cell_w + (cols + 1) * pad
    H = top + rows * (cell_h + lab_h) + (rows + 1) * pad

    canvas = Image.new('RGB', (W, H), (250, 250, 250))
    d = ImageDraw.Draw(canvas)
    if title:
        d.text((pad, 4), str(title)[:80], fill=(20, 20, 20))
    for i, (pts, im) in enumerate(imgs):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = top + pad + r * (cell_h + lab_h + pad)
        canvas.paste(im, (x, y))
        if label:
            d.text((x + 2, y + cell_h + 1), 'pts=%s' % pts, fill=(90, 90, 90))
    canvas.save(out_path, 'JPEG', quality=85)
    return out_path
