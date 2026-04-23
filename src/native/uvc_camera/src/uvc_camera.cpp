#include "uvc_camera_c_api.h"

#include <libuvc/libuvc.h>
#include <libusb.h>

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {

struct ModeCandidate {
    uvc_frame_format format;
    int width;
    int height;
    int fps;
};

class UvcCamera {
public:
    UvcCamera(int preferred_width, int preferred_height, int preferred_fps, int vendor_id, int product_id)
        : preferred_width_(preferred_width),
          preferred_height_(preferred_height),
          preferred_fps_(preferred_fps),
          vendor_id_(vendor_id),
          product_id_(product_id) {}

    ~UvcCamera() {
        Stop();
    }

    bool Start() {
        if (streaming_) {
            return true;
        }

        uvc_error_t result = uvc_init(&ctx_, nullptr);
        if (result != UVC_SUCCESS) {
            SetError("uvc_init failed");
            return false;
        }

        result = OpenPreferredDevice();
        if (result != UVC_SUCCESS) {
            return false;
        }

        libusb_device_handle* usb_handle = uvc_get_libusb_handle(devh_);
        if (usb_handle != nullptr) {
            int detach_result = libusb_set_auto_detach_kernel_driver(usb_handle, 1);
            if (detach_result != LIBUSB_SUCCESS && detach_result != LIBUSB_ERROR_NOT_SUPPORTED) {
                SetError("libusb_set_auto_detach_kernel_driver failed");
                return false;
            }
        }

        const std::vector<ModeCandidate> candidates = {
            {UVC_FRAME_FORMAT_YUYV, preferred_width_, preferred_height_, preferred_fps_},
            {UVC_FRAME_FORMAT_YUYV, preferred_width_, preferred_height_, 10},
            {UVC_FRAME_FORMAT_YUYV, 640, 480, 30},
            {UVC_FRAME_FORMAT_MJPEG, preferred_width_, preferred_height_, preferred_fps_},
            {UVC_FRAME_FORMAT_MJPEG, 640, 480, 30},
        };

        for (const auto& candidate : candidates) {
            uvc_stream_ctrl_t ctrl;
            result = uvc_get_stream_ctrl_format_size(
                devh_,
                &ctrl,
                candidate.format,
                candidate.width,
                candidate.height,
                candidate.fps
            );
            if (result != UVC_SUCCESS) {
                continue;
            }

            result = uvc_start_streaming(devh_, &ctrl, &UvcCamera::FrameCallback, this, 0);
            if (result == UVC_SUCCESS) {
                active_width_ = candidate.width;
                active_height_ = candidate.height;
                streaming_ = true;
                return true;
            }
        }

        SetError("Failed to configure a supported libuvc stream mode");
        return false;
    }

    void Stop() {
        if (streaming_ && devh_ != nullptr) {
            uvc_stop_streaming(devh_);
        }
        streaming_ = false;

        if (devh_ != nullptr) {
            uvc_close(devh_);
            devh_ = nullptr;
        }
        if (dev_ != nullptr) {
            uvc_unref_device(dev_);
            dev_ = nullptr;
        }
        if (ctx_ != nullptr) {
            uvc_exit(ctx_);
            ctx_ = nullptr;
        }

        std::lock_guard<std::mutex> lock(frame_mutex_);
        latest_frame_.clear();
        frame_counter_ = 0;
        last_read_frame_counter_ = 0;
    }

    int WaitForFrame(uint8_t* buffer, int buffer_size, int timeout_ms) {
        if (!streaming_) {
            SetError("Camera is not streaming");
            return -1;
        }

        std::unique_lock<std::mutex> lock(frame_mutex_);
        const bool has_new_frame = frame_cv_.wait_for(
            lock,
            std::chrono::milliseconds(timeout_ms),
            [this] { return frame_counter_ > last_read_frame_counter_; }
        );
        if (!has_new_frame) {
            SetError("Timed out waiting for libuvc frame");
            return -1;
        }

        if (static_cast<int>(latest_frame_.size()) > buffer_size) {
            SetError("Python buffer is smaller than the latest frame");
            return -1;
        }

        std::memcpy(buffer, latest_frame_.data(), latest_frame_.size());
        last_read_frame_counter_ = frame_counter_;
        return static_cast<int>(latest_frame_.size());
    }

    int width() const {
        return active_width_;
    }

    int height() const {
        return active_height_;
    }

    int FrameBufferSize() const {
        return active_width_ * active_height_ * 3;
    }

    const char* last_error() const {
        return last_error_.c_str();
    }

private:
    uvc_error_t OpenPreferredDevice() {
        uvc_device_t** device_list = nullptr;
        uvc_error_t result = uvc_get_device_list(ctx_, &device_list);
        if (result != UVC_SUCCESS) {
            SetError("uvc_get_device_list failed: " + std::string(uvc_strerror(result)));
            return result;
        }

        uvc_error_t last_error = UVC_ERROR_NO_DEVICE;
        std::ostringstream failure_summary;

        for (int index = 0; device_list[index] != nullptr; ++index) {
            uvc_device_t* candidate = device_list[index];
            uvc_device_descriptor_t* desc = nullptr;
            result = uvc_get_device_descriptor(candidate, &desc);
            if (result != UVC_SUCCESS) {
                last_error = result;
                continue;
            }

            const bool vid_matches = (vendor_id_ == 0) || (desc->idVendor == vendor_id_);
            const bool pid_matches = (product_id_ == 0) || (desc->idProduct == product_id_);
            if (!vid_matches || !pid_matches) {
                uvc_free_device_descriptor(desc);
                continue;
            }

            uvc_device_handle_t* handle = nullptr;
            result = uvc_open(candidate, &handle);
            if (result == UVC_SUCCESS) {
                dev_ = candidate;
                uvc_ref_device(dev_);
                devh_ = handle;
                uvc_free_device_descriptor(desc);
                uvc_free_device_list(device_list, 1);
                return UVC_SUCCESS;
            }

            if (failure_summary.tellp() > 0) {
                failure_summary << "; ";
            }
            failure_summary << DescribeDevice(desc) << ": " << uvc_strerror(result);
            last_error = result;
            uvc_free_device_descriptor(desc);
        }

        uvc_free_device_list(device_list, 1);

        if (failure_summary.tellp() > 0) {
            SetError("Unable to open requested UVC device. " + failure_summary.str());
        } else if (vendor_id_ != 0 || product_id_ != 0) {
            std::ostringstream requested;
            requested << "No UVC device matched "
                      << HexId(vendor_id_) << ":" << HexId(product_id_);
            SetError(requested.str());
        } else {
            SetError("uvc_find_device failed");
        }
        return last_error;
    }

    static void FrameCallback(uvc_frame_t* frame, void* user_ptr) {
        if (user_ptr == nullptr || frame == nullptr) {
            return;
        }
        static_cast<UvcCamera*>(user_ptr)->OnFrame(frame);
    }

    void OnFrame(uvc_frame_t* frame) {
        uvc_frame_t* converted = uvc_allocate_frame(frame->width * frame->height * 3);
        if (converted == nullptr) {
            SetError("Failed to allocate libuvc conversion buffer");
            return;
        }

        uvc_error_t result = uvc_any2bgr(frame, converted);
        if (result != UVC_SUCCESS) {
            uvc_free_frame(converted);
            SetError("Failed to convert libuvc frame to BGR");
            return;
        }

        std::lock_guard<std::mutex> lock(frame_mutex_);
        active_width_ = static_cast<int>(converted->width);
        active_height_ = static_cast<int>(converted->height);
        latest_frame_.assign(
            static_cast<uint8_t*>(converted->data),
            static_cast<uint8_t*>(converted->data) + converted->data_bytes
        );
        ++frame_counter_;
        frame_cv_.notify_all();
        uvc_free_frame(converted);
    }

    void SetError(std::string message) {
        last_error_ = std::move(message);
    }

    static std::string HexId(int value) {
        std::ostringstream oss;
        oss << "0x" << std::hex << std::setw(4) << std::setfill('0') << (value & 0xffff);
        return oss.str();
    }

    static std::string DescribeDevice(const uvc_device_descriptor_t* desc) {
        std::ostringstream oss;
        if (desc->product != nullptr) {
            oss << desc->product;
        } else {
            oss << "unknown";
        }
        oss << " [" << HexId(desc->idVendor) << ":" << HexId(desc->idProduct) << "]";
        return oss.str();
    }

    int preferred_width_;
    int preferred_height_;
    int preferred_fps_;
    int vendor_id_;
    int product_id_;

    int active_width_ = 0;
    int active_height_ = 0;

    uvc_context_t* ctx_ = nullptr;
    uvc_device_t* dev_ = nullptr;
    uvc_device_handle_t* devh_ = nullptr;

    bool streaming_ = false;
    std::string last_error_ = "no error";

    std::mutex frame_mutex_;
    std::condition_variable frame_cv_;
    std::vector<uint8_t> latest_frame_;
    std::uint64_t frame_counter_ = 0;
    std::uint64_t last_read_frame_counter_ = 0;
};

}  // namespace

struct dw_uvc_camera_handle {
    explicit dw_uvc_camera_handle(
        int preferred_width,
        int preferred_height,
        int preferred_fps,
        int vendor_id,
        int product_id
    )
        : camera(preferred_width, preferred_height, preferred_fps, vendor_id, product_id) {}

    UvcCamera camera;
};

extern "C" {

dw_uvc_camera_handle* dw_uvc_camera_create(
    int preferred_width,
    int preferred_height,
    int preferred_fps,
    int vendor_id,
    int product_id
) {
    return new dw_uvc_camera_handle(preferred_width, preferred_height, preferred_fps, vendor_id, product_id);
}

int dw_uvc_camera_start(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return -1;
    }
    return handle->camera.Start() ? 0 : -1;
}

void dw_uvc_camera_stop(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return;
    }
    handle->camera.Stop();
}

void dw_uvc_camera_destroy(dw_uvc_camera_handle* handle) {
    delete handle;
}

int dw_uvc_camera_wait_for_frame(
    dw_uvc_camera_handle* handle,
    uint8_t* buffer,
    int buffer_size,
    int timeout_ms
) {
    if (handle == nullptr || buffer == nullptr || buffer_size <= 0) {
        return -1;
    }
    return handle->camera.WaitForFrame(buffer, buffer_size, timeout_ms);
}

int dw_uvc_camera_frame_width(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return 0;
    }
    return handle->camera.width();
}

int dw_uvc_camera_frame_height(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return 0;
    }
    return handle->camera.height();
}

int dw_uvc_camera_frame_buffer_size(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return 0;
    }
    return handle->camera.FrameBufferSize();
}

const char* dw_uvc_camera_last_error(dw_uvc_camera_handle* handle) {
    if (handle == nullptr) {
        return "invalid camera handle";
    }
    return handle->camera.last_error();
}

}  // extern "C"
