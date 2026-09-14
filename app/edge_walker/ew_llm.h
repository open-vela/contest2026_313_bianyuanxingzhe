/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2026 Edge Walker Team (contest2026_313_bianyuanxingzhe) */

/****************************************************************************
 * 边缘行者 · 智能体对话（读 /data/ai_agent 配置，HTTPS 调 MiMo）
 ****************************************************************************/

#ifndef EDGE_WALKER_EW_LLM_H
#define EDGE_WALKER_EW_LLM_H

#ifdef __cplusplus
extern "C" {
#endif

/* 阻塞调用。reply 写入 out（UTF-8）。返回 0 成功。 */
int ew_llm_ask(const char *prompt, char *out, unsigned out_sz);

#ifdef __cplusplus
}
#endif

#endif
