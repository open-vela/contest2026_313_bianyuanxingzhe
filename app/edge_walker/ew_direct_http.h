/* SPDX-License-Identifier: Apache-2.0 */
#ifndef EW_DIRECT_HTTP_H
#define EW_DIRECT_HTTP_H
#include <stddef.h>
typedef struct {
  char method[8], path[96], token[40], id[49];
  size_t header_bytes, body_bytes;
} ew_direct_request_t;
/* 0=incomplete, 1=complete, negative=reject. No allocation or I/O. */
int ew_direct_request(const char *data, size_t size, ew_direct_request_t *out);
/* HTTP response framing; removes chunk framing only after a complete message.
 * Body contents such as CLOSED/OK never act as modem events. */
int ew_direct_response(char *data, size_t *size, int connection_closed);
#endif
