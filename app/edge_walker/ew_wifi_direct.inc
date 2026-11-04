/* SPDX-License-Identifier: Apache-2.0 */
/* Included by the UART owner implementation after at_begin/at_wake helpers.
 * This optional experiment owns g_at_mu for its lifetime. All RX, AT commands,
 * phone responses and SSL link 4 are handled by this single thread. */
#include "ew_esp_stream.h"
#include "ew_direct_http.h"
#include "ew_snapshot.h"
#include "ew_llm.h"
#include "ew_direct_page.h"

#define D_OK 1u
#define D_ERROR 2u
#define D_PROMPT 4u
#define D_SENT 8u
typedef struct {
  char bytes[4097];
  size_t length;
  uint32_t started;
  int connected, busy;
  unsigned generation;
} direct_link_t;
typedef struct {
  char id[49], text[513], reply[512];
  int operation, ok, used, running;
  uint32_t elapsed;
} direct_cached_t;
static struct {
  pthread_mutex_t mu;
  pthread_t owner;
  volatile int state, stop;
  int fd, fault, ssl_closed, model_busy;
  unsigned flags, port, requests, auth_failures;
  unsigned long sequence;
  char code[40], ip[24];
  ew_esp_stream_t parser;
  direct_link_t links[4];
  char ssl[3072];
  size_t ssl_length;
  uint32_t partial_started;
  char wire[8192];
  direct_cached_t cache[8];
  unsigned cache_next;
} g_direct = { .mu=PTHREAD_MUTEX_INITIALIZER, .fd=-1 };

static int direct_active(void)
{
  return __atomic_load_n(&g_direct.state,__ATOMIC_ACQUIRE)==2;
}
static int direct_cached_probe(char *ip,unsigned size)
{
  int active=direct_active();
  if(active && ip && size) {
    pthread_mutex_lock(&g_direct.mu);snprintf(ip,size,"%s",g_direct.ip);pthread_mutex_unlock(&g_direct.mu);
  }
  return active;
}
static void direct_reset_link(direct_link_t *p,int connected)
{
  unsigned next=p->generation+1;memset(p,0,sizeof(*p));p->generation=next;p->connected=connected;
}
static int direct_code_ok(const char *s)
{
  unsigned i,n=(unsigned)strlen(s);
  if(n<16 || n>32)return 0;
  for(i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z') || (s[i]>='A'&&s[i]<='Z') || (s[i]>='0'&&s[i]<='9')))return 0;
  return 1;
}
static int direct_secret_equal(const char *a,const char *b)
{
  unsigned i,d=0;size_t n=strlen(a);
  if(n!=strlen(b))return 0;
  for(i=0;i<n;i++)d|=(unsigned char)a[i]^(unsigned char)b[i];
  return d==0;
}
static int direct_escape(char *out,size_t size,const char *text)
{
  size_t n=0;unsigned c;
  while((c=(unsigned char)*text++)!=0) {
    if(n+7>=size)return -1;
    if(c=='"'||c=='\\'){out[n++]='\\';out[n++]=(char)c;}
    else if(c<32){snprintf(out+n,size-n,"\\u%04x",c);n+=6;}
    else out[n++]=(char)c;
  }
  out[n]=0;return 0;
}
static void direct_event(void *context,ew_esp_stream_event_t event,int link,
                          const unsigned char *bytes,size_t length)
{
  char line[513];int id; (void)context;
  if(event==EW_ESP_STREAM_PROMPT){g_direct.flags|=D_PROMPT;return;}
  if(event==EW_ESP_STREAM_DATA) {
    if(link==4) {
      if(length>=sizeof(g_direct.ssl)-g_direct.ssl_length){g_direct.fault=1;return;}
      memcpy(g_direct.ssl+g_direct.ssl_length,bytes,length);g_direct.ssl_length+=length;g_direct.ssl[g_direct.ssl_length]=0;
    } else if(link>=0&&link<4) {
      direct_link_t *p=&g_direct.links[link];
      if(p->busy || length>=sizeof(p->bytes)-p->length){g_direct.fault=1;return;}
      if(!p->length)p->started=monotonic_ms();
      memcpy(p->bytes+p->length,bytes,length);p->length+=length;p->bytes[p->length]=0;
    }
    return;
  }
  if(length>=sizeof(line))return;
  memcpy(line,bytes,length);line[length]=0;
  while(length && (line[length-1]=='\r'||line[length-1]=='\n'))line[--length]=0;
  if(strcmp(line,"OK")==0)g_direct.flags|=D_OK;
  else if(strcmp(line,"SEND OK")==0)g_direct.flags|=D_SENT;
  else if(strcmp(line,"ERROR")==0 || strcmp(line,"FAIL")==0 || strcmp(line,"SEND FAIL")==0 || strncmp(line,"busy",4)==0)g_direct.flags|=D_ERROR;
  else if(strcmp(line,"WIFI DISCONNECT")==0 || strcmp(line,"ready")==0)g_direct.fault=1;
  else if(sscanf(line,"%d,CLOSED",&id)==1 && strstr(line,",CLOSED")) {
    if(id==4)g_direct.ssl_closed=1;
    else if(id>=0&&id<4)direct_reset_link(&g_direct.links[id],0);
  } else if(sscanf(line,"%d,CONNECT",&id)==1 && strstr(line,",CONNECT")) {
    if(id>=0&&id<4)direct_reset_link(&g_direct.links[id],1);
  }
}
/* Read without sleeping so large UART writes can keep the ESP RX FIFO drained. */
static int direct_rx(void)
{
  unsigned char data[512];int n=read(g_direct.fd,data,sizeof(data));
  if(n>0) {
    if(ew_esp_stream_feed(&g_direct.parser,data,(size_t)n)<0)g_direct.fault=1;
    if(g_direct.parser.length || g_direct.parser.expected) {
      if(!g_direct.partial_started)g_direct.partial_started=monotonic_ms();
    } else g_direct.partial_started=0;
  } else if(n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)g_direct.fault=1;
  if(g_direct.partial_started && (uint32_t)(monotonic_ms()-g_direct.partial_started)>5000) {
    (void)ew_esp_stream_expire(&g_direct.parser);g_direct.fault=1;
  }
  return n>0;
}
static void direct_pump(void)
{
  if(!direct_rx())usleep(2000);
}
/* The legacy AT path deliberately writes one byte at a time. The direct HTTP
 * path sends multi-kilobyte pages, so use bounded chunks and service RX between
 * writes. This keeps the modem's asynchronous +IPD/CONNECT stream from filling
 * while avoiding one scheduler delay per transmitted byte. */
static int direct_bulk_write(const char *bytes,size_t length)
{
  size_t offset=0;uint32_t start=monotonic_ms();
  while(offset<length && !g_direct.fault && !g_direct.stop &&
        (uint32_t)(monotonic_ms()-start)<5000) {
    size_t chunk=length-offset;ssize_t n;
    if(chunk>64)chunk=64;
    n=write(g_direct.fd,bytes+offset,chunk);
    if(n>0) { offset+=(size_t)n;(void)direct_rx(); }
    else if(n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) { g_direct.fault=1;break; }
    else { direct_pump(); }
  }
  return offset==length && !g_direct.fault && !g_direct.stop ? 0:-1;
}
static int direct_wait(unsigned wanted,unsigned timeout)
{
  uint32_t start=monotonic_ms();
  while((uint32_t)(monotonic_ms()-start)<timeout && !g_direct.stop && !g_direct.fault) {
    if(g_direct.flags&D_ERROR)return -1;
    if(g_direct.flags&wanted)return 0;
    direct_pump();
  }
  return -1;
}
static int direct_command(const char *command,unsigned wanted,unsigned timeout)
{
  char line[192];int n=snprintf(line,sizeof(line),"%s\r\n",command);
  if(n<=0 || (unsigned)n>=sizeof(line))return -1;
  g_direct.flags=0;
  if(direct_bulk_write(line,(size_t)n))return -1;
  n=direct_wait(wanted,timeout);
  if(n) {printf("[ew-direct] command failed %.96s flags=%u\n",command,g_direct.flags);fflush(stdout);}
  return n;
}
static int direct_send(int link,const char *bytes,size_t length)
{
  char command[64];
  unsigned generation=link>=0&&link<4?g_direct.links[link].generation:0;
  snprintf(command,sizeof(command),"AT+CIPSEND=%d,%u",link,(unsigned)length);
  if(direct_command(command,D_PROMPT,3000))return -1;
  if(link>=0&&link<4 && (generation!=g_direct.links[link].generation || !g_direct.links[link].connected))return -1;
  g_direct.flags=0;
  if(direct_bulk_write(bytes,length))return -1;
  return direct_wait(D_SENT,4000);
}
static void direct_close(int link)
{
  char command[40];snprintf(command,sizeof(command),"AT+CIPCLOSE=%d",link);
  (void)direct_command(command,D_OK,2000);
  if(link>=0&&link<4)direct_reset_link(&g_direct.links[link],0);
}
static void direct_reply(int link,int code,const char *type,const char *body)
{
  int n=snprintf(g_direct.wire,sizeof(g_direct.wire),
    "HTTP/1.1 %d Result\r\nContent-Type: %s\r\nContent-Length: %u\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n%s",
    code,type,(unsigned)strlen(body),body);
  if(n>0 && (unsigned)n<sizeof(g_direct.wire)) {
    if(direct_send(link,g_direct.wire,(size_t)n))g_direct.fault=1;
  }
  direct_close(link);
}
static void direct_json(int link,int code,const char *id,int ok,unsigned elapsed,const char *data)
{
  char body[4096];int n=snprintf(body,sizeof(body),
    "{\"id\":\"%s\",\"ok\":%s,\"board_elapsed_ms\":%u,%s}",id,ok?"true":"false",elapsed,data);
  if(n<=0 || (unsigned)n>=sizeof(body)){direct_close(link);return;}
  direct_reply(link,code,"application/json; charset=utf-8",body);
}
static void direct_clients(int allow_model);
static ew_wifi_http_result_t direct_ssl_post(const char *host,unsigned port,const char *path,
                      const char *key,const char *body,char *response,unsigned capacity)
{
  char command[192],request[1800];int n,ready=0;uint32_t start;
  if(!host||!path||!key||!body||!response||capacity<16)return EW_WIFI_HTTP_INVALID;
  if(!pthread_equal(pthread_self(),g_direct.owner))return EW_WIFI_HTTP_AT_BUSY;
  if(strcmp(host,"token-plan-cn.xiaomimimo.com") || port!=443 || strcmp(path,"/v1/chat/completions"))return EW_WIFI_HTTP_INVALID;
  direct_close(4); /* Only the reserved cloud link; never a phone link. */
  g_direct.ssl_length=0;g_direct.ssl[0]=0;g_direct.ssl_closed=0;
  if(direct_command("AT+CIPSSLCCONF=4,0",D_OK,2000))return EW_WIFI_HTTP_TLS;
  snprintf(command,sizeof(command),"AT+CIPSSLCSNI=4,\"%s\"",host);
  if(direct_command(command,D_OK,2000))return EW_WIFI_HTTP_TLS;
  snprintf(command,sizeof(command),"AT+CIPSTART=4,\"SSL\",\"%s\",443",host);
  if(direct_command(command,D_OK,15000))return EW_WIFI_HTTP_TLS;
  n=snprintf(request,sizeof(request),"POST %s HTTP/1.1\r\nHost: %s\r\napi-key: %s\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: %u\r\n\r\n%s",path,host,key,(unsigned)strlen(body),body);
  if(n<=0 || (unsigned)n>=sizeof(request))return EW_WIFI_HTTP_INVALID;
  if(direct_send(4,request,(size_t)n)){memset(request,0,sizeof(request));return EW_WIFI_HTTP_SEND;}
  memset(request,0,sizeof(request));start=monotonic_ms();
  while((uint32_t)(monotonic_ms()-start)<45000 && !g_direct.fault && !g_direct.stop) {
    ready=ew_direct_response(g_direct.ssl,&g_direct.ssl_length,g_direct.ssl_closed);
    if(ready!=0)break;
    direct_pump();
    direct_clients(0); /* State/config continue while the model is running. */
  }
  if(!g_direct.ssl_closed)direct_close(4);
  if(ready!=1 || g_direct.ssl_length>=capacity)return EW_WIFI_HTTP_TIMEOUT;
  memcpy(response,g_direct.ssl,g_direct.ssl_length+1);return EW_WIFI_HTTP_OK;
}
static void direct_clients(int allow_model)
{
  unsigned i,j;char data[3500],snapshot[768],escaped[3100];
  for(i=0;i<4 && !g_direct.fault;i++) {
    direct_link_t *p=&g_direct.links[i];ew_direct_request_t request;int rc,operation=0;
    uint32_t start;unsigned generation=p->generation;direct_cached_t *cached=0;
    if(!p->length || p->busy)continue;
    rc=ew_direct_request(p->bytes,p->length,&request);
    if(rc==0){if((uint32_t)(monotonic_ms()-p->started)>5000)direct_close((int)i);continue;}
    p->busy=1;
    if(rc<0){direct_reply((int)i,400,"text/plain","Bad request");continue;}
    if(!strcmp(request.method,"GET")&&!strcmp(request.path,"/")) {
      direct_reply((int)i,200,"text/html; charset=utf-8",EW_DIRECT_PAGE);continue;
    }
    if(!strcmp(request.path,"/favicon.ico")){direct_reply((int)i,404,"text/plain","");continue;}
    if(!direct_secret_equal(request.token,g_direct.code) || !request.id[0]) {
      g_direct.auth_failures++;
      direct_json((int)i,403,"",0,0,"\"error\":\"Pairing code or request ID invalid\"");
      if(g_direct.auth_failures>=16)g_direct.fault=1;
      continue;
    }
    g_direct.requests++;start=monotonic_ms();
    if(!strcmp(request.method,"GET")&&!strcmp(request.path,"/api/state")) {
      ew_safety_snapshot_t state;ew_safety_snapshot(&state);
      if(ew_snapshot_format(snapshot,sizeof(snapshot),request.id,&state,++g_direct.sequence)<0){direct_close((int)i);continue;}
      snprintf(data,sizeof(data),"\"data\":{\"source\":\"device_wifi\",\"profile\":\"%s\",\"snapshot\":%s}",ew_sensitivity_get()==EW_SENSITIVITY_EARLY?"early":"standard",snapshot);
      direct_json((int)i,200,request.id,1,monotonic_ms()-start,data);continue;
    }
    if(!strcmp(request.method,"POST")&&!strcmp(request.path,"/api/profile"))operation=1;
    if(!strcmp(request.method,"POST")&&!strcmp(request.path,"/api/ask"))operation=2;
    if(!operation){direct_json((int)i,404,request.id,0,0,"\"error\":\"Unsupported operation\"");continue;}
    for(j=0;j<8;j++)if(g_direct.cache[j].used&&!strcmp(g_direct.cache[j].id,request.id)){cached=&g_direct.cache[j];break;}
    if(cached && (cached->operation!=operation || strlen(cached->text)!=request.body_bytes || memcmp(cached->text,p->bytes+request.header_bytes,request.body_bytes))) {
      direct_json((int)i,409,request.id,0,0,"\"error\":\"Request ID conflict\"");continue;
    }
    if(cached && cached->running){direct_json((int)i,503,request.id,0,0,"\"error\":\"Request still running\"");continue;}
    if(!cached) {
      if(operation==2 && (!allow_model || g_direct.model_busy)){direct_json((int)i,503,request.id,0,0,"\"error\":\"Model busy\"");continue;}
      if(!request.body_bytes || (operation==2 && request.body_bytes>300)) {direct_json((int)i,400,request.id,0,0,"\"error\":\"Invalid payload size\"");continue;}
      if(operation==1 && !((request.body_bytes==8&&!memcmp(p->bytes+request.header_bytes,"standard",8)) || (request.body_bytes==5&&!memcmp(p->bytes+request.header_bytes,"early",5)))) {direct_json((int)i,400,request.id,0,0,"\"error\":\"Unknown profile\"");continue;}
      for(j=0;j<8;j++) {
        cached=&g_direct.cache[g_direct.cache_next++%8];if(!cached->running)break;
      }
      if(j==8){direct_json((int)i,503,request.id,0,0,"\"error\":\"Result cache busy\"");continue;}
      memset(cached,0,sizeof(*cached));cached->used=1;cached->operation=operation;cached->running=1;
      snprintf(cached->id,sizeof(cached->id),"%s",request.id);memcpy(cached->text,p->bytes+request.header_bytes,request.body_bytes);
      if(operation==1) {
        ew_sensitivity_t profile=!strcmp(cached->text,"early")?EW_SENSITIVITY_EARLY:EW_SENSITIVITY_STANDARD;
        cached->ok=ew_sensitivity_set(profile)==0 && ew_sensitivity_get()==profile;
        snprintf(cached->reply,sizeof(cached->reply),"%s",cached->ok?(profile==EW_SENSITIVITY_EARLY?"early":"standard"):"Configuration readback failed");
      } else {
        g_direct.model_busy=1;
        cached->ok=ew_llm_ask(cached->text,cached->reply,sizeof(cached->reply))==EW_LLM_OK;
        g_direct.model_busy=0;
      }
      cached->elapsed=monotonic_ms()-start;
      cached->running=0;
    }
    if(p->generation!=generation || !p->connected)continue;
    if(direct_escape(escaped,sizeof(escaped),cached->reply)){direct_close((int)i);continue;}
    if(cached->ok)snprintf(data,sizeof(data),"\"data\":{\"%s\":\"%s\",\"source\":\"device_wifi\",\"device_confirmed\":true}",operation==1?"profile":"reply",escaped);
    else snprintf(data,sizeof(data),"\"error\":\"%s\"",escaped);
    direct_json((int)i,cached->ok?200:502,request.id,cached->ok,cached->elapsed,data);
  }
}
static void *direct_thread(void *unused)
{
  int fd,j;char response[256],ip[24];(void)unused;
  fd=at_begin();if(fd<0)goto failed;
  if(at_wake_light(fd) || query_sta_ip(fd,ip,sizeof(ip)))goto release;
  (void)at_tx(fd,"AT+CIPCLOSE",response,sizeof(response),300,600,0);
  g_direct.fd=fd;g_direct.owner=pthread_self();g_direct.fault=0;
  memset(g_direct.links,0,sizeof(g_direct.links));memset(g_direct.cache,0,sizeof(g_direct.cache));g_direct.cache_next=0;
  ew_esp_stream_init(&g_direct.parser,1,direct_event,0);
  g_direct.partial_started=0;
  if(direct_command("AT+CIPMODE=0",D_OK,2000) || direct_command("AT+CIPMUX=1",D_OK,2000) ||
     direct_command("AT+CIPDINFO=0",D_OK,2000))goto cleanup;
  /* ESP-AT 4.x renamed the per-link setting; retain the legacy fallback. */
  if(direct_command("AT+CIPRECVTYPE=5,0",D_OK,2000) && direct_command("AT+CIPRECVMODE=0",D_OK,2000))goto cleanup;
  if(direct_command("AT+CIPSERVERMAXCONN=3",D_OK,2000))goto cleanup;
  snprintf(response,sizeof(response),"AT+CIPSERVER=1,%u",g_direct.port);
  if(direct_command(response,D_OK,3000))goto cleanup;
  if(direct_command("AT+CIPSTO=60",D_OK,2000))goto cleanup;
  pthread_mutex_lock(&g_direct.mu);snprintf(g_direct.ip,sizeof(g_direct.ip),"%s",ip);pthread_mutex_unlock(&g_direct.mu);
  __atomic_store_n(&g_direct.state,2,__ATOMIC_RELEASE);
  printf("[ew-direct] ready ip=%s port=%u source=device_wifi\n",ip,g_direct.port);fflush(stdout);
  while(!g_direct.stop&&!g_direct.fault){direct_pump();direct_clients(1);}
cleanup:
  __atomic_store_n(&g_direct.state,3,__ATOMIC_RELEASE);
  /* Stop can interrupt waits, but cleanup still gets bounded command budgets. */
  g_direct.stop=0;g_direct.fault=0;
  for(j=0;j<5;j++)direct_close(j);
  (void)direct_command("AT+CIPSERVER=0",D_OK,2000);
  (void)direct_command("AT+CIPMUX=0",D_OK,2000);
release:
  at_end(fd);g_direct.fd=-1;
failed:
  __atomic_store_n(&g_direct.state,0,__ATOMIC_RELEASE);
  printf("[ew-direct] stopped; modem released\n");fflush(stdout);return 0;
}
int ew_wifi_direct_start(const char *code,unsigned port)
{
  pthread_attr_t attr;int result;
  if(!code || !direct_code_ok(code) || port!=8769)return -1;
  pthread_mutex_lock(&g_direct.mu);
  if(g_direct.state){pthread_mutex_unlock(&g_direct.mu);return -1;}
  g_direct.stop=0;g_direct.requests=0;g_direct.auth_failures=0;g_direct.sequence=0;
  snprintf(g_direct.code,sizeof(g_direct.code),"%s",code);g_direct.port=port;
  __atomic_store_n(&g_direct.state,1,__ATOMIC_RELEASE);
  pthread_attr_init(&attr);pthread_attr_setstacksize(&attr,98304);
  result=pthread_create(&g_direct.owner,&attr,direct_thread,0);pthread_attr_destroy(&attr);
  if(result)__atomic_store_n(&g_direct.state,0,__ATOMIC_RELEASE);
  else pthread_detach(g_direct.owner);
  pthread_mutex_unlock(&g_direct.mu);return result? -1:0;
}
void ew_wifi_direct_stop(void){__atomic_store_n(&g_direct.stop,1,__ATOMIC_RELEASE);}
void ew_wifi_direct_status(void)
{
  pthread_mutex_lock(&g_direct.mu);
  printf("[ew-direct] state=%d ip=%s port=%u requests=%u auth_failures=%u\n",g_direct.state,g_direct.ip,g_direct.port,g_direct.requests,g_direct.auth_failures);
  pthread_mutex_unlock(&g_direct.mu);
}
