# Generate low-latency source copies from the upstream local/sync-v3.19 sources.
# The original source files remain untouched so this branch can be rebased/synced
# against upstream easily. Every replacement is checked: if upstream changes the
# hot path, configuration fails instead of silently applying a stale patch.

set(LOW_LATENCY_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated/low_latency")
file(MAKE_DIRECTORY "${LOW_LATENCY_GEN_DIR}")

function(_ll_replace_once var_name old_text new_text label)
    set(_src "${${var_name}}")
    string(FIND "${_src}" "${old_text}" _pos)
    if(_pos EQUAL -1)
        message(FATAL_ERROR "Low-latency patch '${label}' no longer matches upstream source")
    endif()

    string(REPLACE "${old_text}" "${new_text}" _patched "${_src}")
    if(_patched STREQUAL _src)
        message(FATAL_ERROR "Low-latency patch '${label}' made no change")
    endif()
    set(${var_name} "${_patched}" PARENT_SCOPE)
endfunction()

# ---- USB HID input hot path -------------------------------------------------
file(READ "${CMAKE_CURRENT_LIST_DIR}/src/usb_gamepad.c" _ll_usb)

# Consume a fresh pending report when it is submitted to USB. The upstream
# implementation leaves pending_active=true after a successful submission, so
# every IN completion immediately re-arms the previous report. That creates a
# one-transfer stale-report pipeline. Keep the endpoint idle when there is no
# newer Bluetooth state instead.
set(_old_usb_submit [=[    usb_in_buf[0] = DS5_USB_REPORT_ID_INPUT;
    memcpy(usb_in_buf + 1, (const void *)pending_payload,
           DS5_USB_INPUT_PAYLOAD_LEN);
    ep_in_busy = true;
    int ret = usbd_ep_start_write(0, USB_GAMEPAD_EP_IN, usb_in_buf, 64);
    if (ret < 0) {
        ep_in_busy = false;]=])
set(_new_usb_submit [=[    /* Claim this fresh report before arming the endpoint. */
    ep_in_busy = true;
    pending_active = false;
    usb_in_buf[0] = DS5_USB_REPORT_ID_INPUT;
    memcpy(usb_in_buf + 1, (const void *)pending_payload,
           DS5_USB_INPUT_PAYLOAD_LEN);
    int ret = usbd_ep_start_write(0, USB_GAMEPAD_EP_IN, usb_in_buf, 64);
    if (ret < 0) {
        ep_in_busy = false;
        /* Retry the latest state if CherryUSB could not queue the transfer. */
        pending_active = true;]=])
_ll_replace_once(_ll_usb "${_old_usb_submit}" "${_new_usb_submit}" "fresh-report USB IN")

# HS realtime mode: 2^(2-1) * 125 us = 250 us host polling interval.
# Bluetooth remains the limiting report source (~750 Hz), so this reduces USB
# phase wait without generating duplicate reports after the fresh-report fix.
set(_old_hs_interval "default: interval = 3; break;")
set(_new_hs_interval "default: interval = 2; break;")
_ll_replace_once(_ll_usb "${_old_hs_interval}" "${_new_hs_interval}" "HS realtime bInterval")

set(LOW_LATENCY_USB_GAMEPAD_SOURCE "${LOW_LATENCY_GEN_DIR}/usb_gamepad.c")
file(WRITE "${LOW_LATENCY_USB_GAMEPAD_SOURCE}" "${_ll_usb}")

# ---- Bluetooth -> USB handoff -----------------------------------------------
file(READ "${CMAKE_CURRENT_LIST_DIR}/src/main.c" _ll_main)

# FreeRTOS xQueueOverwrite copies the item synchronously. Avoid copying the
# whole Bluetooth input report into a temporary stack array first.
set(_old_input_copy [=[        uint8_t report[DS5_BT_INPUT_REPORT_SIZE];
        memcpy(report, data, DS5_BT_INPUT_REPORT_SIZE);
        xQueueOverwrite(input_queue, report);]=])
set(_new_input_copy [=[        /* Depth-1 queue keeps only the newest controller state. */
        xQueueOverwrite(input_queue, data);]=])
_ll_replace_once(_ll_main "${_old_input_copy}" "${_new_input_copy}" "BT input redundant memcpy")

set(LOW_LATENCY_MAIN_SOURCE "${LOW_LATENCY_GEN_DIR}/main.c")
file(WRITE "${LOW_LATENCY_MAIN_SOURCE}" "${_ll_main}")

message(STATUS "Low-latency source patch enabled")
message(STATUS "  main:        ${LOW_LATENCY_MAIN_SOURCE}")
message(STATUS "  usb_gamepad: ${LOW_LATENCY_USB_GAMEPAD_SOURCE}")
