"""Compile the real board LLM code with bounded, hardware-free HTTP fixtures."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BoardLlmRuntimeTests(unittest.TestCase):
    def test_runtime_migration_request_and_error_classification(self):
        with tempfile.TemporaryDirectory(prefix="ew_llm_runtime_") as directory:
            work = Path(directory)
            (work / "nuttx").mkdir()
            (work / "nuttx/config.h").write_text("/* fixture */\n")
            config = work / "config.json"
            source = work / "fixture.c"
            source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
/* Avoid touching the device's absolute /data directories on the host. */
static int fixture_mkdir(const char *path, unsigned mode) {
  (void)path; (void)mode; return 0;
}
#define mkdir(path, mode) fixture_mkdir(path, mode)
#include "ew_llm.c"
#undef mkdir
static char captured[1600], captured_host[128];
static ew_wifi_state_t wifi = EW_WIFI_ONLINE;
static ew_net_error_t net_error;
static int auth_rejected, calls;
void ew_net_state_error(ew_net_error_t error) { net_error=error; }
ew_wifi_state_t ew_wifi_probe(int internet, char *ip, unsigned size) {
  (void)internet; (void)ip; (void)size; return wifi;
}
ew_wifi_http_result_t ew_wifi_http_ssl_post(const char *host, unsigned port,
  const char *path, const char *key, const char *body, char *reply, unsigned size) {
  assert(port==443 && strcmp(path,"/v1/chat/completions")==0);
  assert(strcmp(key,"tp-fixture-not-a-real-key")==0);
  calls++;
  snprintf(captured,sizeof(captured),"%s",body);
  snprintf(captured_host,sizeof(captured_host),"%s",host);
  snprintf(reply,size,"%s",auth_rejected ?
    "HTTP/1.1 401 Unauthorized\r\n\r\n{\"error\":{\"message\":\"unauthorized\"}}" :
    "HTTP/1.1 200 OK\r\n\r\n{\"choices\":[{\"message\":{\"content\":\"OK\"}}]}");
  return EW_WIFI_HTTP_OK;
}
static void runtime(const char *host, const char *model) {
  FILE *f=fopen(EW_LLM_CONFIG,"w"); assert(f);
  fprintf(f,"{\"llm_host\":\"%s\",\"model\":\"%s\","
          "\"api_key\":\"tp-fixture-not-a-real-key\"}",host,model);
  assert(fclose(f)==0);
}
int main(void) {
  char reply[512];
  assert(ew_llm_configure_mimo("tp-fixture-not-a-real-key",reply,sizeof(reply))==0);
  assert(ew_llm_ask("Reply only OK",reply,sizeof(reply))==EW_LLM_OK);
  assert(strcmp(reply,"OK")==0 && net_error==EW_NET_ERR_NONE);
  assert(strstr(captured,"\"model\":\"mimo-v2.6-flash\""));
  assert(strstr(captured,"\"max_completion_tokens\":384"));
  runtime(EW_MIMO_HOST,"mimo-v2.5");
  assert(ew_llm_ask("test",reply,sizeof(reply))==EW_LLM_OK);
  assert(strstr(captured,"\"model\":\"mimo-v2.6-flash\""));
  runtime(EW_MIMO_HOST,"mimo-v2.6-pro");
  assert(ew_llm_ask("test",reply,sizeof(reply))==EW_LLM_OK);
  assert(strstr(captured,"\"model\":\"mimo-v2.6-pro\""));
  runtime("other-provider.invalid","mimo-v2.5");
  assert(ew_llm_ask("test",reply,sizeof(reply))==EW_LLM_OK);
  assert(strcmp(captured_host,"other-provider.invalid")==0);
  assert(strstr(captured,"\"model\":\"mimo-v2.5\""));
  runtime(EW_MIMO_HOST,"mimo-v2.6-flash");
  auth_rejected=1;
  assert(ew_llm_ask("test",reply,sizeof(reply))==EW_LLM_ERR_AUTH);
  assert(net_error==EW_NET_ERR_AUTH);
  wifi=EW_WIFI_IDLE;
  { int before=calls;
    assert(ew_llm_ask("test",reply,sizeof(reply))==EW_LLM_ERR_NO_WIFI);
    assert(calls==before && net_error==EW_NET_ERR_NO_WIFI);
  }
  puts("PASS real board LLM runtime: defaults, legacy migration, provider scope, budget, auth and Wi-Fi errors");
  return 0;
}
''', encoding="utf-8")
            exe = work / "fixture.exe"
            subprocess.run([
                "gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-D__NuttX__", '-DEW_LLM_CONFIG=' + json.dumps(config.as_posix()),
                "-I", str(work), "-I", str(ROOT / "app/edge_walker"),
                str(source), "-o", str(exe),
            ], check=True)
            subprocess.run([str(exe)], check=True, cwd=work, timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
