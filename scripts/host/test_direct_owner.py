"""Run the actual direct UART owner against a deterministic virtual modem."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class DirectOwnerTests(unittest.TestCase):
    def test_real_owner_dispatch_and_concurrent_control(self):
        program=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <errno.h>
#include <pthread.h>
#include "ew_wifi_at.h"
#include "ew_net_state.h"
#include "ew_llm.h"
#include "ew_safety.h"
static unsigned now_ms, waiting_length, waiting_link, model_calls, injected, ssl_pending, control_response_pending;
static unsigned write_calls, eagain_every, stall_write;
static char rx[50000], sent[5][8192],tx[256];static size_t rx_n,rx_pos,sent_n,tx_n;
static uint32_t monotonic_ms(void){return now_ms;}
static void queue(const char *s){size_t n=strlen(s);assert(rx_n+n<sizeof(rx));memcpy(rx+rx_n,s,n);rx_n+=n;}
static void ipd(unsigned id,const char *data){char h[60];snprintf(h,sizeof(h),"+IPD,%u,%u:",id,(unsigned)strlen(data));queue(h);queue(data);}
static void incoming(unsigned id,const char *method,const char *path,const char *rid,const char *body) {
 char h[2000];snprintf(h,sizeof(h),"%u,CONNECT\r\n",id);queue(h);
 snprintf(h,sizeof(h),"%s %s HTTP/1.1\r\nX-EW-Key: abcdef0123456789\r\nX-EW-ID: %s\r\nContent-Length: %u\r\n\r\n%s",method,path,rid,(unsigned)strlen(body),body);ipd(id,h);
}
static int fixture_read(int fd,void *data,size_t size) {
 size_t n;(void)fd;now_ms+=2;
 if(rx_pos==rx_n) {
  rx_n=rx_pos=0;
  if(ssl_pending) {
   if(injected<10) {
    if(!control_response_pending) {
     char id[32];snprintf(id,sizeof(id),"nested_%u",injected++);
     incoming(1,"POST","/api/profile",id,"standard");control_response_pending=1;
    }
   } else {ipd(4,"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{\"ok\":true}");queue("4,CLOSED\r\n");ssl_pending=0;}
  }
 }
 n=rx_n-rx_pos;if(n>size)n=size;if(n>31)n=31; /* fragmented real +IPD parser */
 if(!n){errno=EAGAIN;return -1;}
 memcpy(data,rx+rx_pos,n);rx_pos+=n;return (int)n;
}
static ssize_t fixture_write(int fd,const void *buffer,size_t size) {
 const char *data=buffer;size_t n=size;unsigned link,count;(void)fd;
 write_calls++;
 if(stall_write || (eagain_every && write_calls%eagain_every==0)){errno=EAGAIN;return -1;}
 if(n>17)n=17; /* Exercise real short writes, not only full chunks. */
 if(waiting_length) {
  assert(sent_n+n<sizeof(sent[0]));memcpy(sent[waiting_link]+sent_n,data,n);sent_n+=n;sent[waiting_link][sent_n]=0;
  if(sent_n==waiting_length) {
   if(waiting_link==4){ssl_pending=1;assert(strstr(sent[4],"api-key: tp-fixture"));}
   waiting_length=0;sent_n=0;queue("\r\nSEND OK\r\n");
  }
  return (ssize_t)n;
 }
 assert(tx_n+n<sizeof(tx));memcpy(tx+tx_n,data,n);tx_n+=n;tx[tx_n]=0;
 if(tx_n>=2 && tx[tx_n-2]=='\r' && tx[tx_n-1]=='\n') {
  tx[tx_n-2]=0;tx_n=0;
  if(sscanf(tx,"AT+CIPSEND=%u,%u",&link,&count)==2) {waiting_link=link;waiting_length=count;queue("\r\nOK\r\n>");}
  else if(sscanf(tx,"AT+CIPCLOSE=%u",&link)==1) {char line[40];snprintf(line,sizeof(line),"%u,CLOSED\r\nOK\r\n",link);queue(line);if(link==1)control_response_pending=0;}
  else queue("\r\nOK\r\n");
 }
 return (ssize_t)n;
}
static int at_begin(void){return 99;}
static void at_end(int fd){(void)fd;}
static int at_wake_light(int fd){(void)fd;return 0;}
static int query_sta_ip(int fd,char *ip,unsigned n){(void)fd;snprintf(ip,n,"192.168.43.11");return 0;}
static int at_tx(int fd,const char *cmd,char *out,unsigned size,int idle,int total,int want) {
 (void)fd;(void)cmd;(void)idle;(void)total;(void)want;snprintf(out,size,"OK\r\n");return 4;
}
static int fixture_usleep(unsigned delay){now_ms+=delay/1000;return 0;}
#define read fixture_read
#define write fixture_write
#define usleep fixture_usleep
#include "ew_wifi_direct.inc"
#undef read
#undef write
#undef usleep
void ew_safety_snapshot(ew_safety_snapshot_t *out){memset(out,0,sizeof(*out));out->running=1;out->ever_frame=1;out->updated_ms=now_ms;out->sniff.frames_ok=1;}
ew_llm_result_t ew_llm_ask(const char *text,char *out,unsigned size) {
 char response[3072];ew_wifi_http_result_t r;(void)text;model_calls++;
 r=direct_ssl_post("token-plan-cn.xiaomimimo.com",443,"/v1/chat/completions","tp-fixture","{}",response,sizeof(response));
 assert(r==EW_WIFI_HTTP_OK);assert(strstr(response,"{\"ok\":true}"));
 snprintf(out,size,"MODEL_FIXTURE");return EW_LLM_OK;
}
static void process(void) {
 unsigned guard=0;
 while(rx_pos<rx_n && guard++<2000){direct_pump();direct_clients(1);}
 assert(guard<2000);
}
int main(void) {
 char ip[24];
 g_direct.fd=99;g_direct.owner=pthread_self();g_direct.state=2;strcpy(g_direct.ip,"192.168.43.11");strcpy(g_direct.code,"abcdef0123456789");
 ew_esp_stream_init(&g_direct.parser,1,direct_event,0);
 assert(direct_cached_probe(ip,sizeof(ip))&&!strcmp(ip,"192.168.43.11"));
 assert(ew_wifi_direct_start("short",8769)<0);
 incoming(0,"GET","/api/state","state","");process();assert(strstr(sent[0],"200 Result")&&strstr(sent[0],"device_wifi"));
 eagain_every=5;incoming(0,"GET","/","","");process();eagain_every=0;
 assert(strlen(EW_DIRECT_PAGE)>4500 && strlen(sent[0])>5000 && strstr(sent[0],EW_DIRECT_PAGE));
 incoming(0,"POST","/api/profile","change","early");process();assert(ew_sensitivity_get()==EW_SENSITIVITY_EARLY);
 ew_sensitivity_set(EW_SENSITIVITY_STANDARD);
 incoming(0,"POST","/api/profile","change","early");process();assert(ew_sensitivity_get()==EW_SENSITIVITY_STANDARD); /* cached mutation */
 incoming(0,"POST","/api/profile","change","standard");process();assert(strstr(sent[0],"409 Result"));
 incoming(0,"POST","/api/ask","model","question");process();
 assert(model_calls==1 && injected==10 && ew_sensitivity_get()==EW_SENSITIVITY_STANDARD);
 assert(strstr(sent[0],"MODEL_FIXTURE")&&strstr(sent[1],"200 Result"));
 incoming(0,"POST","/api/ask","model","question");process();assert(model_calls==1);
 assert(!g_direct.fault);ew_wifi_direct_status();
 {uint32_t started=now_ms;stall_write=1;assert(direct_bulk_write("x",1)<0);stall_write=0;
  assert((uint32_t)(now_ms-started)>=5000 && (uint32_t)(now_ms-started)<5010);}
 queue("+IPD,2,100:abc");process();assert(g_direct.partial_started);
 now_ms+=5001;direct_pump();assert(g_direct.fault);ew_wifi_direct_stop();
 puts("PASS actual UART owner: >5KB short writes, EAGAIN recovery, bounded 5s TX timeout, profile readback, ID dedup, reserved SSL link and concurrent controls");return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='ew_direct_owner_') as directory:
            work=Path(directory);(work/'test.c').write_text(program)
            exe=work/'test.exe';src=ROOT/'app/edge_walker'
            compile_result=subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(src),str(work/'test.c'),str(src/'ew_direct_http.c'),str(src/'ew_esp_stream.c'),str(src/'ew_snapshot.c'),str(src/'ew_ld2451.c'),'-lpthread','-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stdout+compile_result.stderr)
            subprocess.run([str(exe)],check=True,timeout=15)

if __name__=='__main__':unittest.main(verbosity=2)

