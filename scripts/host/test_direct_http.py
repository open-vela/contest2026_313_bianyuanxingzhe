"""Exercise actual bounded HTTP framing, including every split boundary."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DirectHttpTests(unittest.TestCase):
    def test_real_framing(self):
        program = r'''
#include "ew_direct_http.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 char b[5000]; size_t i,n;ew_direct_request_t request;
 const char *wire="POST /api/profile HTTP/1.1\r\nX-EW-Key: abcdef0123456789\r\nX-EW-ID: test_1\r\nContent-Length: 5\r\n\r\nearly";
 for(i=0;i<strlen(wire);i++){memcpy(b,wire,i);b[i]=0;assert(ew_direct_request(b,i,&request)==0);}
 strcpy(b,wire);assert(ew_direct_request(b,strlen(b),&request)==1);
 assert(!strcmp(request.token,"abcdef0123456789")&&!strcmp(request.id,"test_1"));
 assert(request.body_bytes==5&&!strcmp(b+request.header_bytes,"early"));
 strcat(b,"GET / HTTP/1.1\r\n\r\n");assert(ew_direct_request(b,strlen(b),&request)<0);
 strcpy(b,"POST / HTTP/1.1\r\nContent-Length: 1\r\nContent-Length: 2\r\n\r\na");assert(ew_direct_request(b,strlen(b),&request)<0);
 strcpy(b,"POST / HTTP/1.1\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\na");assert(ew_direct_request(b,strlen(b),&request)<0);
 strcpy(b,"GET / HTTP/1.1\r\nX-EW-ID: bad\"id\r\n\r\n");assert(ew_direct_request(b,strlen(b),&request)<0);
 memset(b,'x',2100);b[2100]=0;assert(ew_direct_request(b,2100,&request)<0);
 wire="HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nCLOSED";
 for(i=0;i<strlen(wire);i++){memcpy(b,wire,i);b[i]=0;n=i;assert(ew_direct_response(b,&n,0)==0);}
 strcpy(b,wire);n=strlen(b);assert(ew_direct_response(b,&n,0)==1);assert(strstr(b,"CLOSED"));
 wire="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nABC\r\n3\r\nDEF\r\n0\r\n\r\n";
 for(i=0;i<strlen(wire);i++){memcpy(b,wire,i);b[i]=0;n=i;assert(ew_direct_response(b,&n,0)==0);}
 strcpy(b,wire);n=strlen(b);assert(ew_direct_response(b,&n,0)==1);assert(!strcmp(strstr(b,"\r\n\r\n")+4,"ABCDEF"));
 strcpy(b,"HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nshort");n=strlen(b);assert(ew_direct_response(b,&n,1)<0);
 puts("PASS real HTTP fragmentation, bounded headers, request IDs, duplicate framing rejection, content length and chunk decoding");return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="ew_direct_http_") as directory:
            work=Path(directory);(work/'test.c').write_text(program)
            exe=work/'test.exe'
            subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'app/edge_walker'),str(work/'test.c'),str(ROOT/'app/edge_walker/ew_direct_http.c'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True,timeout=10)

if __name__=='__main__':unittest.main(verbosity=2)
