import os
from collections import deque

import numpy as np

from .box import Box
from src.setup import get_hardware_mode

HARDWARE_MODE = get_hardware_mode()

if HARDWARE_MODE == "310b":
    import acl

    from acllite.acllite_model import AclLiteModel
    from acllite.acllite_resource import AclLiteResource

    acl_resource = AclLiteResource()
    acl_resource.init()
elif HARDWARE_MODE == "normal":
    import onnxruntime as ort
elif HARDWARE_MODE == "rk3588":
    from rknn.api import RKNN
else:
    raise ValueError(f"不支持的硬件模式: {HARDWARE_MODE}")

# 初始化模型
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if HARDWARE_MODE == "310b":
    MODEL_PATH = os.path.join(BASE_DIR, 'models', 'tennis.om')
    model = AclLiteModel(MODEL_PATH)
elif HARDWARE_MODE == "normal":
    MODEL_PATH = os.path.join(BASE_DIR, 'models', 'tennis.onnx')
    session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
elif HARDWARE_MODE == "rk3588":
    MODEL_PATH = os.path.join(BASE_DIR, 'models', 'tennis.rknn')
    rknn = RKNN()
    rknn.load_rknn(MODEL_PATH)
    rknn.init_runtime(target="rk3588")
else:
    raise ValueError(f"不支持的硬件模式: {HARDWARE_MODE}")

IMG_SIZE = 640
_MORPH_KERNEL_5 = np.ones((5, 5), dtype=bool)


def yolo_infer(frame):
    if frame is None or frame.size == 0:
        print("无效的图像输入")
        return []

    return _detect_ball(frame)


def get_red_bucket_local(frame):
    hsv = _bgr_to_hsv(frame)

    mask = _in_range(
        hsv,
        np.array([0, 180, 180], dtype=np.uint8),
        np.array([12, 255, 255], dtype=np.uint8),
    ) | _in_range(
        hsv,
        np.array([175, 200, 200], dtype=np.uint8),
        np.array([180, 255, 255], dtype=np.uint8),
    )

    boxes = []
    for component in _connected_components(mask):
        if component["area"] > 5000:
            boxes.append(
                Box(
                    int(component["x"]),
                    int(component["y"]),
                    int(component["w"]),
                    int(component["h"]),
                )
            )

    return boxes


def get_black_bucket_local(frame):
    hsv = _bgr_to_hsv(frame)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.float32) * 1.5, 0, 255).astype(np.uint8)

    mask = _in_range(
        hsv,
        np.array([0, 0, 0], dtype=np.uint8),
        np.array([180, 255, 80], dtype=np.uint8),
    )
    mask = _binary_open(mask, _MORPH_KERNEL_5)
    mask_before_erode = mask.copy()
    mask = _binary_erode(mask, _MORPH_KERNEL_5, iterations=4)

    candidates = []
    for component in _connected_components(mask):
        x = component["x"]
        y = component["y"]
        w = component["w"]
        h = component["h"]
        area = component["area"]

        if area < 1000:
            continue

        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < 1 or aspect_ratio > 4:
            continue

        total_pixels = w * h
        roi = mask[y:y + h, x:x + w]
        black_ratio = float(roi.sum()) / total_pixels if total_pixels > 0 else 0.0
        if black_ratio < 0.7:
            roi_before = mask_before_erode[y:y + h, x:x + w]
            black_ratio_before = float(roi_before.sum()) / total_pixels if total_pixels > 0 else 0.0
            if black_ratio_before < 0.7:
                continue

        rectangularity = area / total_pixels if total_pixels > 0 else 0.0
        candidates.append((area, rectangularity, x, y, w, h))

    if not candidates:
        return []

    candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
    _, _, x, y, w, h = candidates[0]
    return [Box(int(x), int(y), int(w), int(h))]


def _detect_ball(frame):
    input_img, scale, pad_left, pad_top = _prepare_letterboxed_image(frame, IMG_SIZE)

    if HARDWARE_MODE == "310b":
        model_input = _prepare_normalized_chw_rgb(input_img)
        outputs = model.execute([model_input])
    elif HARDWARE_MODE == "normal":
        model_input = _prepare_normalized_nchw_rgb(input_img)
        outputs = session.run(None, {input_name: model_input})
    elif HARDWARE_MODE == "rk3588":
        outputs = rknn.inference(inputs=[input_img], data_format='nhwc')
    else:
        raise ValueError(f"不支持的硬件模式: {HARDWARE_MODE}")

    pred = outputs[0].squeeze().T
    if pred.ndim != 2 or pred.shape[0] == 0:
        return []

    scores = pred[:, 4:]
    class_ids = np.argmax(scores, axis=1)
    conf_scores = scores[np.arange(len(scores)), class_ids]
    mask = conf_scores > 0.70

    pred = pred[mask]
    conf_scores = conf_scores[mask]
    if pred.shape[0] == 0:
        return []

    frame_h, frame_w = frame.shape[:2]
    raw_boxes = []
    for p in pred:
        cx, cy, w, h = p[:4]
        x1 = max(0.0, (cx - 0.5 * w - pad_left) / scale)
        y1 = max(0.0, (cy - 0.5 * h - pad_top) / scale)
        x2 = min(float(frame_w), (cx + 0.5 * w - pad_left) / scale)
        y2 = min(float(frame_h), (cy + 0.5 * h - pad_top) / scale)
        raw_boxes.append([x1, y1, x2, y2])

    raw_boxes = np.array(raw_boxes, dtype=np.float32)
    keep_indices = _nms(raw_boxes, conf_scores.astype(np.float32), 0.45)

    boxes = []
    for idx in keep_indices:
        x1, y1, x2, y2 = raw_boxes[idx]
        boxes.append(Box(int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
    return boxes


def _prepare_letterboxed_image(frame, img_size):
    height, width = frame.shape[:2]
    scale = min(img_size / height, img_size / width)
    new_h = max(int(height * scale), 1)
    new_w = max(int(width * scale), 1)

    resized = _resize_bilinear(frame, new_h, new_w)
    input_img = np.full((img_size, img_size, 3), 114, dtype=np.uint8)
    pad_top = (img_size - new_h) // 2
    pad_left = (img_size - new_w) // 2
    input_img[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
    return input_img, scale, pad_left, pad_top


def _prepare_normalized_chw_rgb(image):
    rgb = image[:, :, ::-1].astype(np.float32) / 255.0
    chw = np.transpose(rgb, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def _prepare_normalized_nchw_rgb(image):
    rgb = image[:, :, ::-1].astype(np.float32) / 255.0
    chw = np.transpose(rgb, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def _resize_bilinear(image, out_h, out_w):
    in_h, in_w = image.shape[:2]
    if in_h == out_h and in_w == out_w:
        return image.copy()

    if out_h <= 0 or out_w <= 0:
        raise ValueError("Output image size must be positive.")

    y = np.linspace(0, in_h - 1, out_h)
    x = np.linspace(0, in_w - 1, out_w)
    y0 = np.floor(y).astype(np.int32)
    x0 = np.floor(x).astype(np.int32)
    y1 = np.clip(y0 + 1, 0, in_h - 1)
    x1 = np.clip(x0 + 1, 0, in_w - 1)
    wy = (y - y0).astype(np.float32)
    wx = (x - x0).astype(np.float32)

    top_left = image[y0[:, None], x0[None, :]].astype(np.float32)
    top_right = image[y0[:, None], x1[None, :]].astype(np.float32)
    bottom_left = image[y1[:, None], x0[None, :]].astype(np.float32)
    bottom_right = image[y1[:, None], x1[None, :]].astype(np.float32)

    top = top_left * (1.0 - wx)[None, :, None] + top_right * wx[None, :, None]
    bottom = bottom_left * (1.0 - wx)[None, :, None] + bottom_right * wx[None, :, None]
    resized = top * (1.0 - wy)[:, None, None] + bottom * wy[:, None, None]
    return np.clip(resized, 0, 255).astype(np.uint8)


def _nms(boxes, scores, iou_threshold):
    if boxes.size == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter_w = np.maximum(0.0, xx2 - xx1)
        inter_h = np.maximum(0.0, yy2 - yy1)
        inter = inter_w * inter_h
        union = areas[i] + areas[order[1:]] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = order[1:][iou <= iou_threshold]

    return keep


def _bgr_to_hsv(frame):
    bgr = frame.astype(np.float32) / 255.0
    b = bgr[:, :, 0]
    g = bgr[:, :, 1]
    r = bgr[:, :, 2]

    maxc = np.max(bgr, axis=2)
    minc = np.min(bgr, axis=2)
    delta = maxc - minc

    hue = np.zeros_like(maxc)
    mask = delta > 1e-8

    r_mask = mask & (maxc == r)
    g_mask = mask & (maxc == g)
    b_mask = mask & (maxc == b)

    hue[r_mask] = np.mod(((g[r_mask] - b[r_mask]) / delta[r_mask]), 6.0)
    hue[g_mask] = ((b[g_mask] - r[g_mask]) / delta[g_mask]) + 2.0
    hue[b_mask] = ((r[b_mask] - g[b_mask]) / delta[b_mask]) + 4.0
    hue = (hue * 30.0) % 180.0

    sat = np.zeros_like(maxc)
    nonzero = maxc > 1e-8
    sat[nonzero] = delta[nonzero] / maxc[nonzero]
    val = maxc

    hsv = np.stack(
        [
            np.clip(hue, 0, 179),
            np.clip(sat * 255.0, 0, 255),
            np.clip(val * 255.0, 0, 255),
        ],
        axis=2,
    )
    return hsv.astype(np.uint8)


def _in_range(image, lower, upper):
    return np.all((image >= lower) & (image <= upper), axis=2)


def _binary_erode(mask, kernel, iterations=1):
    result = mask.astype(bool)
    kernel_h, kernel_w = kernel.shape
    pad_h = kernel_h // 2
    pad_w = kernel_w // 2

    for _ in range(iterations):
        padded = np.pad(result, ((pad_h, pad_h), (pad_w, pad_w)), mode="constant", constant_values=False)
        windows = np.lib.stride_tricks.sliding_window_view(padded, kernel.shape)
        result = np.all(windows[..., kernel], axis=-1)

    return result


def _binary_dilate(mask, kernel, iterations=1):
    result = mask.astype(bool)
    kernel_h, kernel_w = kernel.shape
    pad_h = kernel_h // 2
    pad_w = kernel_w // 2

    for _ in range(iterations):
        padded = np.pad(result, ((pad_h, pad_h), (pad_w, pad_w)), mode="constant", constant_values=False)
        windows = np.lib.stride_tricks.sliding_window_view(padded, kernel.shape)
        result = np.any(windows[..., kernel], axis=-1)

    return result


def _binary_open(mask, kernel):
    return _binary_dilate(_binary_erode(mask, kernel), kernel)


def _connected_components(mask):
    mask = mask.astype(bool)
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components = []
    neighbors = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    )

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue

            queue = deque([(y, x)])
            visited[y, x] = True
            area = 0
            min_y = max_y = y
            min_x = max_x = x

            while queue:
                cy, cx = queue.popleft()
                area += 1
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)

                for dy, dx in neighbors:
                    ny = cy + dy
                    nx = cx + dx
                    if ny < 0 or ny >= height or nx < 0 or nx >= width:
                        continue
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    queue.append((ny, nx))

            components.append(
                {
                    "x": min_x,
                    "y": min_y,
                    "w": max_x - min_x + 1,
                    "h": max_y - min_y + 1,
                    "area": area,
                }
            )

    return components
