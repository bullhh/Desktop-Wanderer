#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct dw_uvc_camera_handle dw_uvc_camera_handle;

dw_uvc_camera_handle* dw_uvc_camera_create(
    int preferred_width,
    int preferred_height,
    int preferred_fps,
    int vendor_id,
    int product_id
);
int dw_uvc_camera_start(dw_uvc_camera_handle* handle);
void dw_uvc_camera_stop(dw_uvc_camera_handle* handle);
void dw_uvc_camera_destroy(dw_uvc_camera_handle* handle);
int dw_uvc_camera_wait_for_frame(
    dw_uvc_camera_handle* handle,
    uint8_t* buffer,
    int buffer_size,
    int timeout_ms
);
int dw_uvc_camera_frame_width(dw_uvc_camera_handle* handle);
int dw_uvc_camera_frame_height(dw_uvc_camera_handle* handle);
int dw_uvc_camera_frame_buffer_size(dw_uvc_camera_handle* handle);
const char* dw_uvc_camera_last_error(dw_uvc_camera_handle* handle);

#ifdef __cplusplus
}
#endif
