/* Synthetic headless LVGL workload; no EPIC/LCDC/physical touch emulation. */
#include "lvgl.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static unsigned flushes;
static uint64_t pixels;
static uint32_t last_crc;

static void flush(lv_display_t *display, const lv_area_t *area, uint8_t *data)
{
  uint32_t hash = 2166136261u;
  size_t bytes = (size_t)(area->x2-area->x1+1) * (area->y2-area->y1+1) * 2;
  for (size_t i = 0; i < bytes; ++i) hash = (hash ^ data[i]) * 16777619u;
  last_crc = hash;
  pixels += bytes / 2;
  ++flushes;
  lv_display_flush_ready(display);
}

int main(void)
{
  lv_init();
  lv_display_t *display = lv_display_create(390, 450);
  void *buffer = lv_malloc(390u * 450u * 2u);
  assert(display && buffer);
  lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
  lv_display_set_buffers(display, buffer, NULL, 390u*450u*2u,
                         LV_DISPLAY_RENDER_MODE_FULL);
  lv_display_set_flush_cb(display, flush);
  lv_obj_t *label = lv_label_create(lv_screen_active());
  lv_label_set_text(label, "EW READY");
  lv_obj_center(label);
  lv_refr_now(display);
  uint32_t initial_crc = last_crc;
  flushes = 0;
  pixels = 0;
  for (unsigned i = 0; i < 120; ++i) {
    lv_label_set_text(label, "EW READY");
    lv_tick_inc(40);
    lv_timer_handler();
  }
  unsigned repeated_flushes = flushes;
  uint64_t repeated_pixels = pixels;
  assert(repeated_flushes >= 100 && last_crc == initial_crc);
  flushes = 0;
  pixels = 0;
  for (unsigned i = 0; i < 120; ++i) {
    /* Demonstrates a change guard; this is not an application patch. */
    if (strcmp(lv_label_get_text(label), "EW READY"))
      lv_label_set_text(label, "EW READY");
    lv_tick_inc(40);
    lv_timer_handler();
  }
  unsigned guarded_flushes = flushes;
  assert(guarded_flushes == 0 && last_crc == initial_crc);
  lv_label_set_text(label, "STRONG");
  lv_tick_inc(40);
  lv_timer_handler();
  assert(flushes > 0 && last_crc != initial_crc);
  lv_mem_monitor_t memory;
  lv_mem_monitor(&memory);
  assert(memory.total_size <= 512u * 1024u);
  printf("{\"scope\":\"synthetic_headless_lvgl\","
         "\"board_equivalent\":false,\"epic_executed\":false,"
         "\"width\":390,\"height\":450,\"rgb_bits\":16,"
         "\"iterations_per_case\":120,\"repeated_flushes\":%u,"
         "\"repeated_pixels\":%" PRIu64 ",\"guarded_flushes\":%u,"
         "\"changed_text_flushes\":%u,\"heap_budget_bytes\":%u,"
         "\"lvgl_heap_peak_bytes\":%u,\"same_pixels_verified\":true}\n",
         repeated_flushes, repeated_pixels, guarded_flushes, flushes,
         512u * 1024u, (unsigned)memory.max_used);
  lv_display_delete(display);
  lv_free(buffer);
  lv_deinit();
  return 0;
}

