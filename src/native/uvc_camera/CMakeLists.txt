cmake_minimum_required(VERSION 3.16)

project(dw_uvc_camera LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)
find_package(PkgConfig REQUIRED)

pkg_check_modules(LIBUVC QUIET libuvc)
pkg_check_modules(LIBUSB QUIET libusb-1.0)

if(NOT LIBUVC_FOUND)
  find_path(LIBUVC_INCLUDE_DIR NAMES libuvc/libuvc.h)
  find_library(LIBUVC_LIBRARY NAMES uvc libuvc)
  if(NOT LIBUVC_INCLUDE_DIR OR NOT LIBUVC_LIBRARY)
    message(FATAL_ERROR "libuvc was not found. Install libuvc development headers and libraries.")
  endif()
  set(LIBUVC_INCLUDE_DIRS ${LIBUVC_INCLUDE_DIR})
  set(LIBUVC_LIBRARIES ${LIBUVC_LIBRARY})
endif()

if(NOT LIBUSB_FOUND)
  find_path(LIBUSB_INCLUDE_DIR NAMES libusb.h PATH_SUFFIXES libusb-1.0)
  find_library(LIBUSB_LIBRARY NAMES usb-1.0 libusb-1.0)
  if(NOT LIBUSB_INCLUDE_DIR OR NOT LIBUSB_LIBRARY)
    message(FATAL_ERROR "libusb-1.0 was not found. Install libusb-1.0 development headers and libraries.")
  endif()
  set(LIBUSB_INCLUDE_DIRS ${LIBUSB_INCLUDE_DIR})
  set(LIBUSB_LIBRARIES ${LIBUSB_LIBRARY})
endif()

add_library(dw_uvc_camera SHARED
  src/uvc_camera.cpp
)

target_include_directories(dw_uvc_camera
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${LIBUVC_INCLUDE_DIRS}
    ${LIBUSB_INCLUDE_DIRS}
)

target_link_libraries(dw_uvc_camera
  PRIVATE
    ${LIBUVC_LIBRARIES}
    ${LIBUSB_LIBRARIES}
    Threads::Threads
)
