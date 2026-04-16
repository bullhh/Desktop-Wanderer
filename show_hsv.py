import cv2
import numpy as np

mouse_x, mouse_y = None, None

def mouse_callback(event, x, y, flags, param):
    global mouse_x, mouse_y
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_x, mouse_y = x, y

cv2.namedWindow("frame")
cv2.setMouseCallback("frame", mouse_callback)

cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if not ret:
        break

    if mouse_x is not None and 0 <= mouse_y < frame.shape[0] and 0 <= mouse_x < frame.shape[1]:
        bgr = frame[mouse_y, mouse_x]
        hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        text = f"RGB=({bgr[2]}, {bgr[1]}, {bgr[0]}) HSV=({hsv[0]}, {hsv[1]}, {hsv[2]})"
        cv2.drawMarker(frame, (mouse_x, mouse_y), (0, 255, 0), cv2.MARKER_CROSS, 30, 2)
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
