#ifndef LV_CONF_H
#define LV_CONF_H
/* A bounded synthetic LVGL heap, NOT the board's total available memory. */
#define LV_COLOR_DEPTH 16
#define LV_USE_OS 0
#define LV_USE_STDLIB_MALLOC 0
#define LV_MEM_SIZE (512 * 1024U)
#define LV_DEF_REFR_PERIOD 33
#define LV_USE_DRAW_SW 1
#define LV_DRAW_SW_DRAW_UNIT_CNT 1
#define LV_USE_NUTTX 0
#define LV_USE_LOG 0
#define LV_USE_ASSERT_NULL 1
#define LV_USE_ASSERT_MALLOC 1
#define LV_ASSERT_HANDLER_INCLUDE <stdlib.h>
#define LV_ASSERT_HANDLER abort();
#endif

