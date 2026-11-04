/* SPDX-License-Identifier: Apache-2.0 */
#include "ew_direct_http.h"
#include <string.h>
#include <stdio.h>
#include <errno.h>

static int same(const char *a, size_t n, const char *b)
{
  size_t i;
  if (n != strlen(b)) return 0;
  for (i=0;i<n;i++) {
    unsigned x=(unsigned char)a[i], y=(unsigned char)b[i];
    if (x>='A' && x<='Z') x+=32;
    if (y>='A' && y<='Z') y+=32;
    if (x!=y) return 0;
  }
  return 1;
}
static int number(const char *p, size_t n, unsigned base, size_t *value)
{
  size_t i, v=0;
  if (!n) return -EPROTO;
  for(i=0;i<n;i++) {
    unsigned c=(unsigned char)p[i], d;
    if(c>='0' && c<='9') d=c-'0';
    else if(c>='a' && c<='f') d=c-'a'+10;
    else if(c>='A' && c<='F') d=c-'A'+10;
    else return -EPROTO;
    if(d>=base || v>(65536u-d)/base) return -EMSGSIZE;
    v=v*base+d;
  }
  *value=v; return 0;
}
static int field(char *out, size_t cap, const char *v, size_t n)
{
  size_t i;
  if(n>=cap) return -EMSGSIZE;
  for(i=0;i<n;i++) if((unsigned char)v[i]<32 || (unsigned char)v[i]>126) return -EPROTO;
  memcpy(out,v,n);out[n]=0;return 0;
}
static int headers(const char *data, size_t size, size_t *end, size_t *length,
                   int *chunked, ew_direct_request_t *request)
{
  const char *p, *line, *colon, *v, *finish;
  size_t n; int have_length=0, have_transfer=0, token=0, id=0;
  if (memchr(data,0,size)) return -EPROTO;
  finish=strstr(data,"\r\n\r\n");
  if(!finish) return size>2048 ? -EMSGSIZE:0;
  *end=(size_t)(finish-data)+4;
  if(*end>2048) return -EMSGSIZE;
  p=strstr(data,"\r\n");if(!p) return -EPROTO;p+=2;
  *length=0;*chunked=0;
  while(p<finish) {
    line=strstr(p,"\r\n");if(!line || line>finish) return -EPROTO;
    colon=memchr(p,':',(size_t)(line-p));if(!colon || p[0]==' ' || p[0]=='\t') return -EPROTO;
    v=colon+1;while(v<line && (*v==' ' || *v=='\t'))v++;
    n=(size_t)(line-v);
    if(same(p,(size_t)(colon-p),"content-length")) {
      if(have_length++ || number(v,n,10,length)) return -EPROTO;
    } else if(same(p,(size_t)(colon-p),"transfer-encoding")) {
      if(have_transfer++ || !same(v,n,"chunked")) return -EPROTO;
      *chunked=1;
    } else if(request && same(p,(size_t)(colon-p),"x-ew-key")) {
      if(token++ || field(request->token,sizeof(request->token),v,n))return -EPROTO;
    } else if(request && same(p,(size_t)(colon-p),"x-ew-id")) {
      if(id++ || field(request->id,sizeof(request->id),v,n))return -EPROTO;
    }
    p=line+2;
  }
  if(have_length && have_transfer)return -EPROTO;
  return have_length ? 2:1;
}
int ew_direct_request(const char *data, size_t size, ew_direct_request_t *out)
{
  const char *a,*b,*line;size_t end,length,i;int chunked,rc;
  memset(out,0,sizeof(*out));
  rc=headers(data,size,&end,&length,&chunked,out);if(rc<=0)return rc;
  if(chunked || length>512 || end+length>4096)return -EMSGSIZE;
  line=strstr(data,"\r\n");a=memchr(data,' ',(size_t)(line-data));if(!a)return -EPROTO;
  b=memchr(a+1,' ',(size_t)(line-a-1));if(!b || !same(b+1,(size_t)(line-b-1),"HTTP/1.1"))return -EPROTO;
  if(field(out->method,sizeof(out->method),data,(size_t)(a-data)) ||
     field(out->path,sizeof(out->path),a+1,(size_t)(b-a-1))) return -EPROTO;
  for(i=0;out->id[i];i++)if(!((out->id[i]>='a'&&out->id[i]<='z') ||
    (out->id[i]>='A'&&out->id[i]<='Z') || (out->id[i]>='0'&&out->id[i]<='9') ||
    out->id[i]=='_' || out->id[i]=='-'))return -EPROTO;
  out->header_bytes=end;out->body_bytes=length;
  return size<end+length ? 0:size==end+length ? 1:-EPROTO;
}
int ew_direct_response(char *data, size_t *size, int closed)
{
  size_t end,length,pos,total=0,stop,chunk,output;int chunked,rc;
  if(*size<9)return closed ? -EPROTO:0;
  if(strncmp(data,"HTTP/1.",7))return -EPROTO;
  rc=headers(data,*size,&end,&length,&chunked,0);if(rc<=0)return rc;
  if(!chunked) {
    if(rc==2) {if(*size<end+length)return closed ? -EPROTO:0;*size=end+length;data[*size]=0;return 1;}
    return closed ? 1:0;
  }
  pos=end;
  /* First pass: validate every chunk/trailer before modifying the buffer. */
  for(;;) {
    const char *line=strstr(data+pos,"\r\n");
    if(!line)return closed ? -EPROTO:0;
    if(number(data+pos,(size_t)(line-data-pos),16,&chunk))return -EPROTO;
    pos=(size_t)(line-data)+2;
    if(chunk==0) {
      if(*size<pos+2)return closed ? -EPROTO:0;
      if(data[pos]!='\r' || data[pos+1]!='\n')return -EPROTO; /* no trailers in this bounded client */
      stop=pos+2;break;
    }
    if(chunk>*size-pos || *size-pos-chunk<2)return closed ? -EPROTO:0;
    if(data[pos+chunk]!='\r' || data[pos+chunk+1]!='\n')return -EPROTO;
    total+=chunk;pos+=chunk+2;
  }
  (void)stop;pos=end;output=end;
  for(;;) {
    const char *line=strstr(data+pos,"\r\n");
    if(number(data+pos,(size_t)(line-data-pos),16,&chunk))return -EPROTO;
    pos=(size_t)(line-data)+2;if(!chunk)break;
    memmove(data+output,data+pos,chunk);output+=chunk;pos+=chunk+2;
  }
  *size=end+total;data[*size]=0;return 1;
}
